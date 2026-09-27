from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import requests

from melodex.playback_gateway import PlaybackGateway


class _Handler(BaseHTTPRequestHandler):
    payload = b"0123456789abcdef"

    def log_message(self, _format, *args):
        return

    def do_GET(self):  # noqa: N802
        cookie = self.headers.get("Cookie", "")
        if self.headers.get("X-Test") != "ok" or "session=abc" not in cookie:
            self.send_response(403)
            self.end_headers()
            return
        value = self.headers.get("Range")
        if value == "bytes=2-5":
            body = self.payload[2:6]
            self.send_response(206)
            self.send_header("Content-Range", "bytes 2-5/16")
        else:
            body = self.payload
            self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_gateway_forwards_headers_cookies_and_range():
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    gateway = PlaybackGateway()
    try:
        url = gateway.register(
            {
                "url": f"http://127.0.0.1:{upstream.server_address[1]}/audio",
                "headers": {"X-Test": "ok"},
                "cookies": {"session": "abc"},
                "_playback_allowed_hosts": ["127.0.0.1"],
            }
        )
        response = requests.get(url, headers={"Range": "bytes=2-5"}, timeout=3)
        assert response.status_code == 206
        assert response.content == b"2345"
        assert response.headers["Content-Range"] == "bytes 2-5/16"
    finally:
        gateway.close()
        upstream.shutdown()
        upstream.server_close()
