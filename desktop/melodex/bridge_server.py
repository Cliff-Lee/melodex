from __future__ import annotations

import json
import mimetypes
import os
import secrets
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class ProviderBridge:
    """Small authenticated LAN bridge used by mobile/remote Melodex clients.

    Catalog operations use a Bearer token. For local media playback the resolve
    response returns a bridge media URL containing the same token as a query
    parameter because basic media players cannot always attach custom headers.
    Keep the bridge on a trusted LAN or behind HTTPS/VPN.
    """

    def __init__(self, manager, host: str = "127.0.0.1", port: int = 8766, token: str = ""):
        self.manager = manager
        self.host = host
        self.port = int(port)
        self.token = token or secrets.token_urlsafe(24)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def _query(self):
                u = urllib.parse.urlparse(self.path)
                return u, urllib.parse.parse_qs(u.query)

            def _auth(self) -> bool:
                u, q = self._query()
                if u.path == "/health":
                    return True
                auth = self.headers.get("Authorization", "")
                query_token = q.get("token", [""])[0]
                return auth == f"Bearer {bridge.token}" or secrets.compare_digest(query_token, bridge.token)

            def _send(self, code: int, payload: Any, ctype="application/json"):
                body = payload if isinstance(payload, (bytes, bytearray)) else json.dumps(payload, ensure_ascii=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

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

            def do_HEAD(self):
                return self.do_GET()

            def do_GET(self):
                if not self._auth():
                    return self._send(401, {"error":"unauthorized"})
                u, q = self._query()
                try:
                    if u.path == "/health":
                        return self._send(200, {"ok": True, "service": "melodex-provider-bridge"})
                    if u.path == "/v1/providers":
                        return self._send(200, {"providers":[{"id":p.info.id,"name":p.info.name,"description":p.info.description,"capabilities":p.info.capabilities} for p in bridge.manager.providers.values()]})
                    if u.path == "/v1/search":
                        text = q.get("q", [""])[0]
                        pid = q.get("provider", ["all"])[0]
                        return self._send(200, {"items": bridge.manager.search(text, pid, 100)})
                    if u.path == "/v1/browse":
                        pid = q.get("provider", ["local"])[0]
                        kind = q.get("kind", ["featured"])[0]
                        return self._send(200, {"items": bridge.manager.browse(pid, kind, 100)})
                    if u.path == "/v1/resolve":
                        pid = q.get("provider", [""])[0]
                        tid = q.get("id", [""])[0]
                        if pid and tid:
                            target = {"provider_id":pid,"track_id":tid,"rel":f"{pid}:{tid}"}
                        else:
                            target = {
                                "artist": q.get("artist", [""])[0],
                                "title": q.get("title", [""])[0],
                                "album": q.get("album", [""])[0],
                            }
                        resolved = bridge.manager.resolve(target)
                        if resolved.get("local_path"):
                            host = self.headers.get("Host") or f"127.0.0.1:{bridge.port}"
                            actual_pid = str(resolved.get("provider_id") or pid)
                            actual_tid = str(resolved.get("track_id") or tid)
                            media_q = urllib.parse.urlencode({"provider": actual_pid, "id": actual_tid, "token": bridge.token})
                            resolved = dict(resolved)
                            resolved["stream_url"] = f"http://{host}/v1/media?{media_q}"
                            # Never send an absolute server filesystem path to a remote client.
                            resolved.pop("local_path", None)
                        return self._send(200, resolved)
                    if u.path == "/v1/media":
                        pid = q.get("provider", [""])[0]
                        tid = q.get("id", [""])[0]
                        resolved = bridge.manager.resolve({"provider_id":pid,"track_id":tid,"rel":f"{pid}:{tid}"})
                        local = str(resolved.get("local_path") or "")
                        if not local:
                            url = str(resolved.get("stream_url") or "")
                            if not url:
                                return self._send(404, {"error":"media unavailable"})
                            self.send_response(302)
                            self.send_header("Location", url)
                            self.end_headers()
                            return
                        return self._stream_file(Path(local))
                    return self._send(404, {"error":"not found"})
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception as exc:
                    return self._send(500, {"error": str(exc)})

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = int(self._server.server_port)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
