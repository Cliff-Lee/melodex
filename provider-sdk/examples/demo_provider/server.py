"""Minimal MPP demo provider.

The catalog is fictional and playback URLs intentionally use the reserved
`.invalid` domain, so this example demonstrates the protocol without depending
on an external music service.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

CATALOG = [
    {
        "type": "track",
        "provider_id": "org.melodex.demo",
        "provider_track_id": "demo-1",
        "artist": "Demo Artist",
        "title": "Night Drive",
        "album": "Protocol Tests",
        "duration_ms": 240000,
    },
    {
        "type": "track",
        "provider_id": "org.melodex.demo",
        "provider_track_id": "demo-2",
        "artist": "Demo Artist",
        "title": "Morning Glass",
        "album": "Protocol Tests",
        "duration_ms": 198000,
    },
]
TOKEN = "demo-token"


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: object) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _auth(self) -> bool:
        if self.headers.get("Authorization") == f"Bearer {TOKEN}":
            return True
        self._json(
            401,
            {
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "Bearer token required",
                    "retryable": False,
                }
            },
        )
        return False

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/v1/health":
            return self._json(200, {"status": "ready"})
        if not self._auth():
            return None
        if path == "/v1/provider":
            return self._json(
                200,
                {
                    "id": "org.melodex.demo",
                    "name": "Melodex Demo Provider",
                    "version": "0.1.0",
                    "protocol_version": "1.0",
                    "capabilities": ["search", "track", "playback"],
                },
            )
        if path.startswith("/v1/tracks/"):
            track_id = path.rsplit("/", 1)[-1]
            for row in CATALOG:
                if row["provider_track_id"] == track_id:
                    return self._json(200, row)
            return self._json(
                404,
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Track not found",
                        "retryable": False,
                    }
                },
            )
        return self._json(
            404,
            {
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Unknown endpoint",
                    "retryable": False,
                }
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if not self._auth():
            return None
        length = int(self.headers.get("Content-Length", "0") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json(
                400,
                {
                    "error": {
                        "code": "INVALID_REQUEST",
                        "message": "Invalid JSON",
                        "retryable": False,
                    }
                },
            )
        if path == "/v1/search":
            query = str(body.get("query", "")).casefold()
            items = [
                item
                for item in CATALOG
                if query in f"{item['artist']} {item['title']} {item['album']}".casefold()
            ]
            return self._json(
                200,
                {"items": items[: int(body.get("limit", 25))], "next_cursor": None},
            )
        if path == "/v1/playback/resolve":
            track_id = str(body.get("provider_track_id", ""))
            if not any(item["provider_track_id"] == track_id for item in CATALOG):
                return self._json(
                    404,
                    {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Track not found",
                            "retryable": False,
                        }
                    },
                )
            return self._json(
                200,
                {
                    "kind": "http",
                    "url": f"https://media.example.invalid/{track_id}.mp3",
                    "headers": {},
                    "mime_type": "audio/mpeg",
                    "expires_at": None,
                    "seekable": True,
                    "cache_policy": "session",
                },
            )
        return self._json(
            404,
            {
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Unknown endpoint",
                    "retryable": False,
                }
            },
        )

    def log_message(self, fmt: str, *args: object) -> None:
        print(fmt % args)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8877), Handler)
    print("Demo MPP provider: http://127.0.0.1:8877  token=demo-token")
    server.serve_forever()
