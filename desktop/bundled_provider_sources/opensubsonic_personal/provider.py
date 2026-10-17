"""Melodex R1-3B: opt-in OpenSubsonic server adapter (stdlib only).

Provides MPP 1.0 preview search, get_track, health and stream resolution.
No credentials are persisted by this subprocess. Supplied by the host per RPC.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

PROVIDER_ID = "org.melodex.opensubsonic.personal"
VERSION = "0.1.1"
CLIENT = "Melodex"
API_VERSION = "1.14.0"
MAX_RESPONSE_BYTES = 2_000_000
TIMEOUT_SECONDS = 10.0


class ProviderError(Exception):
    """Public, deliberately secret-free provider error."""


def _bool(value: object) -> bool:
    return value is True or str(value or "").lower() in {"true", "yes", "1", "on"}


def _config(params: dict[str, Any]) -> dict[str, str]:
    raw = params.get("_melodex_config") or {}
    if not isinstance(raw, dict):
        raise ProviderError("Invalid provider configuration")
    server = str(raw.get("server_url") or "").strip().rstrip("/")
    if not server or any(ord(c) < 32 for c in server):
        raise ProviderError("Configure a server URL in Melodex Sources")
    parsed = urllib.parse.urlsplit(server)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ProviderError("Invalid server port") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or (port is not None and port <= 0):
        raise ProviderError("Server URL must be HTTP or HTTPS with a hostname")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProviderError("Server URL cannot contain credentials, query parameters or fragments")
    if parsed.scheme.lower() == "http" and not _bool(raw.get("allow_insecure_http")):
        raise ProviderError("HTTP disabled. Enable the explicit insecure HTTP option only for a trusted server")
    if server.lower().endswith("/rest"):
        server = server[:-5]
    if any(c.isspace() for c in server):
        raise ProviderError("Invalid server URL")
    username = str(raw.get("username") or "").strip()
    password = str(raw.get("password") or "")
    if not username or not password:
        raise ProviderError("Configure a Subsonic username and password in Melodex Sources")
    return {"server": server, "username": username, "password": password}


def _server_id(cfg: dict[str, str]) -> str:
    # Scope IDs to both server and account, not a rotating auth password.
    scope = json.dumps([cfg["server"], cfg["username"]], ensure_ascii=False)
    return hashlib.sha256(scope.encode("utf-8")).hexdigest()[:16]


def _track_id(song_id: object, cfg: dict[str, str]) -> str:
    raw = str(song_id or "").strip()
    if not raw or len(raw) > 512:
        raise ProviderError("Invalid server track ID")
    return _server_id(cfg) + ":" + raw


def _native_id(value: object, cfg: dict[str, str]) -> str:
    prefix = _server_id(cfg) + ":"
    track_id = str(value or "")
    if not track_id.startswith(prefix):
        raise ProviderError("Track belongs to another server or is missing an identity")
    song_id = track_id[len(prefix):]
    if not song_id or len(song_id) > 512:
        raise ProviderError("Invalid server track ID")
    return song_id


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _url(endpoint: str, cfg: dict[str, str], arguments: dict[str, str] | None = None) -> str:
    if endpoint not in {"ping", "search3", "getSong", "stream"}:
        raise ProviderError("Unsupported server operation")
    salt = secrets.token_hex(12)
    token = hashlib.md5((cfg["password"] + salt).encode("utf-8")).hexdigest()
    params = {
        "u": cfg["username"], "t": token, "s": salt,
        "v": API_VERSION, "c": CLIENT, "f": "json",
    }
    params.update(arguments or {})
    return cfg["server"] + "/rest/" + endpoint + ".view?" + urllib.parse.urlencode(params)


def _request_json(endpoint: str, cfg: dict[str, str], arguments: dict[str, str] | None = None) -> dict[str, Any]:
    url = _url(endpoint, cfg, arguments)
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Melodex-OpenSubsonic/0.1"})
    try:
        with _OPENER.open(req, timeout=TIMEOUT_SECONDS) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # Never log URL, body, or urllib exception: URL embeds an auth token.
        if 300 <= exc.code < 400:
            raise ProviderError("Server redirected an authenticated API request; verify the configured URL") from None
        raise ProviderError(f"Server returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProviderError("Could not reach the configured music server") from None
    if len(data) > MAX_RESPONSE_BYTES:
        raise ProviderError("Server response exceeds the safe size limit")
    try:
        payload = json.loads(data)
    except (ValueError, UnicodeError):
        raise ProviderError("Server returned invalid JSON") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("subsonic-response"), dict):
        raise ProviderError("Not a valid Subsonic JSON response")
    outer = payload["subsonic-response"]
    if outer.get("status") != "ok":
        error = outer.get("error") or {}
        raw_code = error.get("code") if isinstance(error, dict) else None
        if type(raw_code) is int and 0 <= raw_code <= 999:
            code = str(raw_code)
        else:
            code = "unknown"
        raise ProviderError(f"Music server refused the operation (Subsonic code {code})")
    return outer


def _song(row: Any, cfg: dict[str, str]) -> dict[str, Any] | None:
    if not isinstance(row, dict) or not row.get("id"):
        return None
    song_id = _track_id(row["id"], cfg)
    try:
        duration = max(0, int(row.get("duration") or 0))
    except (ValueError, TypeError, OverflowError):
        duration = 0
    return {
        "type": "track", "provider_id": PROVIDER_ID,
        "provider_track_id": song_id,
        "title": str(row.get("title") or "Unknown track"),
        "artist": str(row.get("artist") or "Unknown artist"),
        "album": str(row.get("album") or ""),
        "duration": duration,
    }


def respond(request: dict[str, Any]) -> dict[str, Any]:
    method = str(request.get("method") or "")
    params = request.get("params") or {}
    if not isinstance(params, dict):
        raise ProviderError("Invalid request parameters")
    if method == "provider.info":
        return {
            "id": PROVIDER_ID, "name": "Navidrome / OpenSubsonic",
            "version": VERSION, "protocol_version": "1.0",
            "description": "Play your own authenticated Subsonic music library",
            "capabilities": ["search", "track", "playback"],
        }
    if method == "provider.health":
        try:
            cfg = _config(params)
            _request_json("ping", cfg)
            return {"status": "ready", "message": "Music server is reachable and authentication succeeded"}
        except ProviderError as exc:
            return {"status": "unavailable", "message": str(exc)}
    cfg = _config(params)
    if method == "catalog.search":
        query = str(params.get("query") or "").strip()
        if not query:
            return {"items": [], "next_cursor": None}
        try:
            limit = max(1, min(100, int(params.get("limit") or 25)))
        except (ValueError, TypeError):
            limit = 25
        outer = _request_json("search3", cfg, {
            "query": query, "songCount": str(limit),
            "albumCount": "0", "artistCount": "0",
        })
        raw = outer.get("searchResult3") or {}
        if not isinstance(raw, dict):
            raise ProviderError("Unexpected search response")
        songs = raw.get("song") or []
        if not isinstance(songs, list):
            raise ProviderError("Unexpected track data")
        return {"items": [s for row in songs[:limit] if (s := _song(row, cfg))], "next_cursor": None}
    if method == "catalog.get_track":
        song_id = _native_id(params.get("provider_track_id") or params.get("track_id") or "", cfg)
        outer = _request_json("getSong", cfg, {"id": song_id})
        song = _song(outer.get("song"), cfg)
        if song is None:
            raise ProviderError("Track not found")
        return song
    if method in {"playback.resolve", "playback.refresh"}:
        song_id = _native_id(params.get("provider_track_id") or params.get("track_id") or "", cfg)
        return {
            "kind": "http", "url": _url("stream", cfg, {"id": song_id}),
            "headers": {}, "cookies": {}, "seekable": True,
            "cache_policy": "session", "request_timeout_seconds": 15,
        }
    raise ProviderError("Unsupported provider operation")


def serve() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        request: dict[str, Any] | None = None
        try:
            incoming = json.loads(line)
            if not isinstance(incoming, dict):
                raise ProviderError("Invalid JSON-RPC request")
            request = incoming
            result = respond(request)
            response = {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
        except Exception as exc:
            safe = str(exc) if isinstance(exc, ProviderError) else "Provider request failed"
            response = {"jsonrpc": "2.0", "id": (request or {}).get("id"),
                        "error": {"code": -32000, "message": safe}}
        print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    serve()
