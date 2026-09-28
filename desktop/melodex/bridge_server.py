from __future__ import annotations

import json
import mimetypes
import os
import secrets
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable


class ProviderBridge:
    """Authenticated bridge for providers plus optional playback/control actions.

    The desktop app starts a loopback-only instance automatically so local MCP
    servers can control the running GUI without importing Qt into the MCP
    process. The existing LAN use case is still supported when the user
    explicitly restarts the bridge on 0.0.0.0.
    """

    def __init__(
        self,
        manager,
        host: str = "127.0.0.1",
        port: int = 8766,
        token: str = "",
        controller: Callable[[str, dict[str, Any]], Any] | None = None,
        state_path: Path | None = None,
    ):
        self.manager = manager
        self.host = host
        self.port = int(port)
        self.token = token or secrets.token_urlsafe(24)
        self.controller = controller
        self.state_path = Path(state_path) if state_path else None
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def _write_state(self) -> None:
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "host": self.host,
            "port": self.port,
            "token": self.token,
            "pid": os.getpid(),
            "started_at": time.time(),
        }
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), "utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.state_path)
        try:
            os.chmod(self.state_path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _public_track(track: dict[str, Any]) -> dict[str, Any]:
        out = dict(track)
        out.pop("local_path", None)
        return out

    def _control(self, action: str, args: dict[str, Any] | None = None) -> Any:
        if not self.controller:
            raise RuntimeError("Playback control is unavailable in this bridge instance")
        return self.controller(str(action), dict(args or {}))

    def start(self) -> None:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "MelodexBridge/0.2"

            def log_message(self, *_args):
                return

            def _query(self):
                u = urllib.parse.urlparse(self.path)
                return u, urllib.parse.parse_qs(u.query)

            def _auth(self) -> bool:
                u, q = self._query()
                if u.path in {"/health", "/openapi.json"}:
                    return True
                auth = self.headers.get("Authorization", "")
                query_token = q.get("token", [""])[0]
                return auth == f"Bearer {bridge.token}" or secrets.compare_digest(query_token, bridge.token)

            def _send(self, code: int, payload: Any, ctype: str = "application/json"):
                body = payload if isinstance(payload, (bytes, bytearray)) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            def _json_body(self, max_bytes: int = 2 * 1024 * 1024) -> dict[str, Any]:
                try:
                    length = int(self.headers.get("Content-Length", "0") or 0)
                except ValueError:
                    raise ValueError("Invalid Content-Length")
                if length < 0 or length > max_bytes:
                    raise ValueError("Request body is too large")
                raw = self.rfile.read(length) if length else b"{}"
                data = json.loads(raw.decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("JSON body must be an object")
                return data

            def _stream_file(self, path: Path):
                if not path.exists() or not path.is_file():
                    return self._send(404, {"error": "media not found"})
                size = path.stat().st_size
                start, end = 0, size - 1
                range_header = self.headers.get("Range", "")
                partial = False
                if range_header.startswith("bytes="):
                    try:
                        spec = range_header[6:].split(",", 1)[0]
                        left, right = spec.split("-", 1)
                        if left:
                            start = max(0, min(size - 1, int(left)))
                        if right:
                            end = max(start, min(size - 1, int(right)))
                        partial = True
                    except Exception:
                        start, end, partial = 0, size - 1, False
                length = max(0, end - start + 1)
                ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                self.send_response(206 if partial else 200)
                self.send_header("Content-Type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(length))
                if partial:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.end_headers()
                if self.command == "HEAD":
                    return
                with path.open("rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(128 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)

            def _remote_track(self, resolved: dict[str, Any]) -> dict[str, Any]:
                if not resolved.get("local_path"):
                    return bridge._public_track(resolved)
                host = self.headers.get("Host") or f"127.0.0.1:{bridge.port}"
                pid = str(resolved.get("provider_id") or "local")
                tid = str(resolved.get("track_id") or "")
                media_q = urllib.parse.urlencode({"provider": pid, "id": tid, "token": bridge.token})
                out = bridge._public_track(resolved)
                out["stream_url"] = f"http://{host}/v1/media?{media_q}"
                return out

            def do_HEAD(self):
                return self.do_GET()

            def do_GET(self):
                if not self._auth():
                    return self._send(401, {"error": "unauthorized"})
                u, q = self._query()
                try:
                    if u.path == "/health":
                        return self._send(200, {"ok": True, "service": "melodex-provider-bridge", "control": bool(bridge.controller)})
                    if u.path == "/openapi.json":
                        return self._send(200, openapi_document())
                    if u.path == "/v1/openai/tools":
                        return self._send(200, OPENAI_FUNCTION_TOOLS)
                    if u.path == "/v1/extensions":
                        extensions = []
                        for row in bridge.manager.extensions():
                            item = dict(row)
                            plugin_id = str(item.get("id") or "")
                            item["installation"] = (
                                bridge.manager.installation_record(plugin_id)
                                if hasattr(bridge.manager, "installation_record")
                                else {}
                            )
                            extensions.append(item)
                        return self._send(200, {"extensions": extensions})
                    if u.path == "/v1/providers":
                        order = bridge.manager.provider_order() if hasattr(bridge.manager, "provider_order") else list(bridge.manager.providers)
                        providers = []
                        for rank, pid in enumerate(order, start=1):
                            p = bridge.manager.providers[pid]
                            providers.append(
                                {
                                    "id": p.info.id,
                                    "name": p.info.name,
                                    "version": p.info.version,
                                    "description": p.info.description,
                                    "capabilities": p.info.capabilities,
                                    "permissions": p.info.permissions,
                                    "priority": rank,
                                    "installation": (
                                        bridge.manager.installation_record(pid)
                                        if hasattr(bridge.manager, "installation_record")
                                        else {}
                                    ),
                                }
                            )
                        return self._send(200, {"providers": providers})
                    if u.path == "/v1/search":
                        text = q.get("q", [""])[0]
                        pid = q.get("provider", ["all"])[0]
                        limit = max(1, min(100, int(q.get("limit", ["100"])[0] or 100)))
                        return self._send(200, {"items": [bridge._public_track(x) for x in bridge.manager.search(text, pid, limit)]})
                    if u.path == "/v1/browse":
                        pid = q.get("provider", ["local"])[0]
                        kind = q.get("kind", ["featured"])[0]
                        return self._send(200, {"items": [bridge._public_track(x) for x in bridge.manager.browse(pid, kind, 100)]})
                    if u.path == "/v1/resolve":
                        pid = q.get("provider", [""])[0]
                        tid = q.get("id", [""])[0]
                        target = {"provider_id": pid, "track_id": tid, "rel": f"{pid}:{tid}"} if pid and tid else {
                            "artist": q.get("artist", [""])[0],
                            "title": q.get("title", [""])[0],
                            "album": q.get("album", [""])[0],
                        }
                        return self._send(200, self._remote_track(bridge.manager.resolve(target)))
                    if u.path == "/v1/resolve-candidates":
                        target = {
                            "artist": q.get("artist", [""])[0],
                            "title": q.get("title", [""])[0],
                            "album": q.get("album", [""])[0],
                        }
                        limit = max(1, min(50, int(q.get("limit", ["20"])[0] or 20)))
                        info = dict(bridge.manager.inspect_resolution(target, limit) or {})
                        clean = []
                        for row in list(info.get("candidates") or []):
                            if not isinstance(row, dict):
                                continue
                            item = dict(row)
                            if isinstance(item.get("track"), dict):
                                item["track"] = bridge._public_track(item["track"])
                            clean.append(item)
                        info["candidates"] = clean
                        return self._send(200, info)
                    if u.path == "/v1/status":
                        status = dict(bridge._control("status") or {})
                        if isinstance(status.get("current_track"), dict):
                            status["current_track"] = bridge._public_track(status["current_track"])
                        status["queue"] = [bridge._public_track(x) for x in list(status.get("queue") or []) if isinstance(x, dict)]
                        return self._send(200, status)
                    if u.path == "/v1/media":
                        pid = q.get("provider", [""])[0]
                        tid = q.get("id", [""])[0]
                        resolved = bridge.manager.resolve({"provider_id": pid, "track_id": tid, "rel": f"{pid}:{tid}"})
                        local = str(resolved.get("local_path") or "")
                        if not local:
                            url = str(resolved.get("stream_url") or "")
                            if not url:
                                return self._send(404, {"error": "media unavailable"})
                            self.send_response(302)
                            self.send_header("Location", url)
                            self.end_headers()
                            return
                        return self._stream_file(Path(local))
                    return self._send(404, {"error": "not found"})
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception as exc:
                    return self._send(500, {"error": str(exc)})

            def do_POST(self):
                if not self._auth():
                    return self._send(401, {"error": "unauthorized"})
                u, _ = self._query()
                try:
                    body = self._json_body()
                    if u.path == "/v1/play":
                        resolved = bridge.manager.resolve(body)
                        bridge._control("set_queue", {"tracks": [resolved], "start": 0, "autoplay": True})
                        return self._send(200, {"ok": True, "track": self._remote_track(resolved)})
                    if u.path == "/v1/queue":
                        requested = [dict(x) for x in list(body.get("tracks") or []) if isinstance(x, dict)]
                        if not requested:
                            raise ValueError("tracks must contain at least one track")
                        result = bridge.manager.resolve_playlist(requested)
                        tracks = list(result.get("tracks") or [])
                        mode = str(body.get("mode") or "replace").lower()
                        autoplay = bool(body.get("autoplay", True))
                        if tracks:
                            action = "append_queue" if mode == "append" else "set_queue"
                            bridge._control(action, {"tracks": tracks, "start": 0, "autoplay": autoplay})
                        return self._send(200, {
                            "ok": bool(tracks),
                            "requested": int(result.get("requested") or len(requested)),
                            "matched": len(tracks),
                            "unresolved": list(result.get("unresolved") or []),
                            "tracks": [bridge._public_track(x) for x in tracks],
                        })
                    if u.path == "/v1/resolver/prefer":
                        requested = dict(body.get("requested") or {})
                        candidate = dict(body.get("candidate") or {})
                        bridge.manager.prefer_resolution(requested, candidate)
                        return self._send(200, {"ok": True})
                    if u.path == "/v1/resolver/block":
                        requested = dict(body.get("requested") or {})
                        candidate = dict(body.get("candidate") or {})
                        bridge.manager.block_resolution(requested, candidate)
                        return self._send(200, {"ok": True})
                    if u.path == "/v1/resolver/reset":
                        requested = dict(body.get("requested") or {})
                        if bool(body.get("clear_preference", True)):
                            bridge.manager.clear_resolution_preference(requested)
                        if bool(body.get("clear_blocks", True)):
                            bridge.manager.clear_resolution_blocks(requested)
                        return self._send(200, {"ok": True})
                    if u.path == "/v1/control":
                        action = str(body.get("action") or "").strip()
                        allowed = {
                            "play_pause", "next", "previous", "stop", "clear_queue", "flow_queue",
                            "love_current", "dislike_current", "keep_current", "save_moment",
                            "set_volume", "seek_ms", "open_view",
                        }
                        if action not in allowed:
                            return self._send(400, {"error": f"unsupported control action: {action}"})
                        result = bridge._control(action, dict(body.get("args") or {}))
                        return self._send(200, {"ok": True, "result": result})
                    return self._send(404, {"error": "not found"})
                except (BrokenPipeError, ConnectionResetError):
                    return
                except ValueError as exc:
                    return self._send(400, {"error": str(exc)})
                except Exception as exc:
                    return self._send(500, {"error": str(exc)})

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = int(self._server.server_port)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._write_state()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self.state_path:
            try:
                current = json.loads(self.state_path.read_text("utf-8"))
                if str(current.get("token") or "") == self.token:
                    self.state_path.unlink(missing_ok=True)
            except Exception:
                pass
