from __future__ import annotations

import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urljoin, urlparse

_requests = None


def _requests_api():
    global _requests
    if _requests is None:
        import requests as requests_module

        _requests = requests_module
    return _requests

_FORWARD_RESPONSE_HEADERS = {
    "accept-ranges",
    "cache-control",
    "content-length",
    "content-range",
    "content-type",
    "etag",
    "last-modified",
}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 8
_CREDENTIAL_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "cookie2",
}
_DEFAULT_USER_AGENT = (
    "Melodex-Playback-Gateway/1.0 "
    "(+https://github.com/Cliff-Lee/melodex)"
)



def _origin_key(url: str) -> tuple[str, str, int]:
    parsed = urlparse(url)
    scheme = parsed.scheme.casefold()
    host = parsed.hostname or ""
    try:
        host = host.encode("idna").decode("ascii").casefold()
    except UnicodeError:
        host = host.casefold()
    try:
        port = parsed.port
    except ValueError as exc:
        raise PermissionError("Provider supplied an invalid playback URL") from exc
    return scheme, host.rstrip("."), port or (443 if scheme == "https" else 80)


def _host_allowed(host: str, patterns: list[str]) -> bool:
    if not patterns:
        return False
    host = host.casefold().strip(".")
    for raw in patterns:
        pattern = str(raw).casefold().strip().strip(".")
        if pattern == "*":
            return True
        if pattern.startswith("*."):
            suffix = pattern[2:]
            if host == suffix or host.endswith("." + suffix):
                return True
        elif host == pattern:
            return True
    return False


def _allowed_hosts(resource: dict[str, Any]) -> list[str] | None:
    if "_playback_allowed_hosts" not in resource:
        return None
    return [str(item) for item in resource.get("_playback_allowed_hosts") or []]


class PlaybackGateway:
    """Loopback proxy for playback resources that require request state."""

    def __init__(self) -> None:
        self._resources: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return int(self._server.server_address[1]) if self._server else 0

    def _ensure_started(self) -> None:
        if self._server:
            return
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                owner._serve(self, head_only=False)

            def do_HEAD(self) -> None:  # noqa: N802
                owner._serve(self, head_only=True)

            def log_message(self, _format: str, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def validate_resource(self, resource: dict[str, Any]) -> str:
        url = str(resource.get("stream_url") or resource.get("url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Playback gateway requires an http(s) resource")
        allowed = _allowed_hosts(resource)
        if allowed is not None and not _host_allowed(parsed.hostname, allowed):
            raise ValueError(f"Playback host is not declared by provider: {parsed.hostname}")
        return url

    def register(self, resource: dict[str, Any]) -> str:
        url = self.validate_resource(resource)
        self._ensure_started()
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._resources[token] = dict(resource)
        return f"http://127.0.0.1:{self.port}/play/{token}"

    def _request_upstream(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        allowed: list[str] | None,
        timeout: float,
        stream: bool,
    ) -> Any:
        requests_api = _requests_api()
        current = url
        current_origin = _origin_key(current)
        headers = dict(headers)
        for _redirect_count in range(_MAX_REDIRECTS + 1):
            parsed = urlparse(current)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise PermissionError("Provider redirected to an invalid playback URL")
            if allowed is not None and not _host_allowed(parsed.hostname, allowed):
                raise PermissionError(
                    f"Provider redirected outside declared hosts: {parsed.hostname}"
                )

            response = requests_api.request(
                method,
                current,
                headers=headers,
                allow_redirects=False,
                stream=stream,
                timeout=timeout,
            )
            if response.status_code not in _REDIRECT_STATUSES:
                return response

            location = response.headers.get("Location")
            if not location:
                return response

            next_url = urljoin(current, location)
            next_host = urlparse(next_url).hostname or ""
            if allowed is not None and not _host_allowed(next_host, allowed):
                response.close()
                raise PermissionError(
                    f"Provider redirected outside declared hosts: {next_host}"
                )
            response.close()
            next_origin = _origin_key(next_url)
            if next_origin != current_origin:
                headers = {
                    name: value
                    for name, value in headers.items()
                    if name.casefold() not in _CREDENTIAL_HEADERS
                }
            current = next_url
            current_origin = next_origin

        raise requests_api.TooManyRedirects(
            f"Playback resource exceeded {_MAX_REDIRECTS} redirects"
        )

    def _serve(self, handler: BaseHTTPRequestHandler, head_only: bool) -> None:
        requests_api = _requests_api()
        prefix = "/play/"
        if not handler.path.startswith(prefix):
            handler.send_error(404)
            return
        token = handler.path[len(prefix) :].split("?", 1)[0]
        with self._lock:
            resource = dict(self._resources.get(token) or {})
        if not resource:
            handler.send_error(404)
            return

        url = str(resource.get("stream_url") or resource.get("url") or "")
        headers = {str(k): str(v) for k, v in dict(resource.get("headers") or {}).items()}
        headers.setdefault("User-Agent", _DEFAULT_USER_AGENT)
        cookies = dict(resource.get("cookies") or {})
        if cookies and "Cookie" not in headers:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
        incoming_range = handler.headers.get("Range")
        if incoming_range and "Range" not in headers:
            headers["Range"] = incoming_range

        timeout = float(resource.get("request_timeout_seconds") or 30.0)
        allowed = _allowed_hosts(resource)
        try:
            response = self._request_upstream(
                "HEAD" if head_only else "GET",
                url,
                headers,
                allowed,
                timeout,
                stream=not head_only,
            )
            handler.send_response(response.status_code)
            for name, value in response.headers.items():
                if name.casefold() in _FORWARD_RESPONSE_HEADERS:
                    handler.send_header(name, value)
            handler.end_headers()
            if not head_only:
                try:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            handler.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            response.close()
        except PermissionError as exc:
            handler.send_error(502, str(exc))
        except requests_api.RequestException as exc:
            handler.send_error(502, f"Upstream playback request failed: {exc}")

    def close(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        self._server = None
        self._thread = None
        with self._lock:
            self._resources.clear()
