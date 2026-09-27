from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .paths import app_data_dir
from .redaction import redact_for_llm


class ControlError(RuntimeError):
    pass


class MelodexControlClient:
    """HTTP client for the private local control bridge inside a running Melodex app."""

    def __init__(self, base_url: str, token: str, timeout: float = 90.0, state_path: Path | None = None):
        self.base_url = str(base_url).rstrip("/")
        self.token = str(token)
        self.timeout = float(timeout)
        self.state_path = Path(state_path) if state_path else None

    @staticmethod
    def _read_state(path: Path) -> tuple[str, str]:
        try:
            data = json.loads(path.read_text("utf-8"))
        except FileNotFoundError as exc:
            raise ControlError("Melodex is not running (control bridge state file was not found).") from exc
        except Exception as exc:
            raise ControlError(f"Could not read Melodex control state: {exc}") from exc
        host = str(data.get("host") or "127.0.0.1")
        if host in {"0.0.0.0", "::", "[::]"}:
            host = "127.0.0.1"
        port = int(data.get("port") or 0)
        token = str(data.get("token") or "")
        if not port or not token:
            raise ControlError("Melodex control state is incomplete. Restart Melodex.")
        return f"http://{host}:{port}", token

    @classmethod
    def from_state(cls, state_path: Path | None = None, timeout: float = 90.0) -> "MelodexControlClient":
        path = Path(state_path or (app_data_dir() / "bridge.json"))
        base_url, token = cls._read_state(path)
        return cls(base_url, token, timeout=timeout, state_path=path)

    def _refresh_state(self) -> None:
        if not self.state_path:
            return
        self.base_url, self.token = self._read_state(self.state_path)

    def _request(self, method: str, path: str, payload: Any = None, params: dict[str, Any] | None = None) -> Any:
        # Re-read the tiny state file so a long-running MCP server follows a
        # Melodex GUI restart or bridge rebind without needing its own restart.
        self._refresh_state()
        url = self.base_url + path
        if params:
            cleaned = {k: v for k, v in params.items() if v not in (None, "")}
            if cleaned:
                url += "?" + urllib.parse.urlencode(cleaned, doseq=True)
        body = None
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read()
                if not raw:
                    return {}
                return redact_for_llm(json.loads(raw.decode("utf-8")))
        except urllib.error.HTTPError as exc:
            try:
                raw = exc.read().decode("utf-8", errors="replace")
                detail = json.loads(raw).get("error") or raw
            except Exception:
                detail = str(exc)
            raise ControlError(f"Melodex control request failed ({exc.code}): {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ControlError(f"Could not reach the running Melodex app at {self.base_url}: {exc}") from exc

    def health(self) -> dict[str, Any]:
        return dict(self._request("GET", "/health") or {})

    def status(self) -> dict[str, Any]:
        return dict(self._request("GET", "/v1/status") or {})

    def providers(self) -> list[dict[str, Any]]:
        result = self._request("GET", "/v1/providers") or {}
        return list(result.get("providers") or [])

    def search(self, query: str, provider: str = "all", limit: int = 20) -> list[dict[str, Any]]:
        result = self._request("GET", "/v1/search", params={"q": query, "provider": provider, "limit": max(1, min(100, int(limit)))}) or {}
        return list(result.get("items") or [])

    def resolve(self, artist: str, title: str, album: str = "") -> dict[str, Any]:
        return dict(self._request("GET", "/v1/resolve", params={"artist": artist, "title": title, "album": album}) or {})

    def resolve_candidates(self, artist: str, title: str, album: str = "", limit: int = 20) -> dict[str, Any]:
        return dict(self._request("GET", "/v1/resolve-candidates", params={"artist": artist, "title": title, "album": album, "limit": max(1, min(50, int(limit)))}) or {})

    def prefer_match(self, requested: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        return dict(self._request("POST", "/v1/resolver/prefer", {"requested": requested, "candidate": candidate}) or {})

    def block_match(self, requested: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        return dict(self._request("POST", "/v1/resolver/block", {"requested": requested, "candidate": candidate}) or {})

    def reset_match_memory(self, requested: dict[str, Any], clear_preference: bool = True, clear_blocks: bool = True) -> dict[str, Any]:
        return dict(self._request("POST", "/v1/resolver/reset", {"requested": requested, "clear_preference": bool(clear_preference), "clear_blocks": bool(clear_blocks)}) or {})

    def play(self, artist: str, title: str, album: str = "") -> dict[str, Any]:
        return dict(self._request("POST", "/v1/play", {"artist": artist, "title": title, "album": album}) or {})

    def queue_tracks(self, tracks: list[dict[str, Any]], replace: bool = True, autoplay: bool = True) -> dict[str, Any]:
        return dict(self._request("POST", "/v1/queue", {"tracks": tracks, "mode": "replace" if replace else "append", "autoplay": bool(autoplay)}) or {})

    def control(self, action: str, **args: Any) -> dict[str, Any]:
        return dict(self._request("POST", "/v1/control", {"action": action, "args": args}) or {})


def mcp_http_token_path() -> Path:
    return app_data_dir() / "mcp-http-token.txt"


def load_or_create_mcp_http_token(path: Path | None = None) -> str:
    import secrets

    token_path = Path(path or mcp_http_token_path())
    try:
        token = token_path.read_text("utf-8").strip()
        if token:
            return token
    except FileNotFoundError:
        pass
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    token_path.write_text(token + "\n", "utf-8")
    try:
        os.chmod(token_path, 0o600)
    except OSError:
        pass
    return token
