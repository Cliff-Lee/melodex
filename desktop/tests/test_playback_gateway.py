import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
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


class _RedirectHandler(BaseHTTPRequestHandler):
    target_url = ""
    authorization = None
    cookie = None

    def log_message(self, _format, *args):
        return

    def do_GET(self):  # noqa: N802
        type(self).authorization = self.headers.get("Authorization")
        type(self).cookie = self.headers.get("Cookie")
        self.send_response(302)
        self.send_header("Location", self.target_url)
        self.end_headers()


class _RedirectTargetHandler(BaseHTTPRequestHandler):
    hits = 0
    authorization = None
    cookie = None

    def log_message(self, _format, *args):
        return

    def do_GET(self):  # noqa: N802
        type(self).hits += 1
        type(self).authorization = self.headers.get("Authorization")
        type(self).cookie = self.headers.get("Cookie")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"should-not-be-reached")


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


def test_gateway_rejects_external_resource_with_no_declared_hosts():
    gateway = PlaybackGateway()
    try:
        with pytest.raises(ValueError, match="not declared"):
            gateway.register(
                {
                    "url": "https://example.invalid/audio.mp3",
                    "_playback_allowed_hosts": [],
                }
            )
    finally:
        gateway.close()


def test_gateway_checks_redirect_host_before_following():
    target = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectTargetHandler)
    target_thread = threading.Thread(target=target.serve_forever, daemon=True)
    target_thread.start()

    redirect = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectHandler)
    _RedirectHandler.target_url = f"http://localhost:{target.server_address[1]}/audio"
    redirect_thread = threading.Thread(target=redirect.serve_forever, daemon=True)
    redirect_thread.start()

    _RedirectTargetHandler.hits = 0
    gateway = PlaybackGateway()
    try:
        url = gateway.register(
            {
                "url": f"http://127.0.0.1:{redirect.server_address[1]}/redirect",
                "headers": {"Authorization": "Bearer test-secret"},
                "_playback_allowed_hosts": ["127.0.0.1"],
            }
        )
        response = requests.get(url, timeout=3)
        assert response.status_code == 502
        assert _RedirectTargetHandler.hits == 0
    finally:
        gateway.close()
        redirect.shutdown()
        redirect.server_close()
        target.shutdown()
        target.server_close()


def test_gateway_validates_direct_external_resource_without_starting_proxy():
    gateway = PlaybackGateway()
    try:
        url = gateway.validate_resource(
            {
                "url": "https://media.example/audio.mp3",
                "_playback_allowed_hosts": ["media.example"],
            }
        )
        assert url == "https://media.example/audio.mp3"
        assert gateway.port == 0
        with pytest.raises(ValueError, match="not declared"):
            gateway.validate_resource(
                {
                    "url": "https://other.example/audio.mp3",
                    "_playback_allowed_hosts": ["media.example"],
                }
            )
    finally:
        gateway.close()



def test_gateway_drops_credentials_when_allowed_redirect_changes_origin():
    target = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectTargetHandler)
    target_thread = threading.Thread(target=target.serve_forever, daemon=True)
    target_thread.start()

    redirect = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectHandler)
    _RedirectHandler.target_url = f"http://localhost:{target.server_address[1]}/audio"
    _RedirectHandler.authorization = None
    _RedirectHandler.cookie = None
    _RedirectTargetHandler.authorization = None
    _RedirectTargetHandler.cookie = None
    redirect_thread = threading.Thread(target=redirect.serve_forever, daemon=True)
    redirect_thread.start()

    gateway = PlaybackGateway()
    try:
        url = gateway.register(
            {
                "url": f"http://127.0.0.1:{redirect.server_address[1]}/redirect",
                "headers": {
                    "Authorization": "Bearer private-test",
                    "Cookie": "session=private-test",
                },
                "_playback_allowed_hosts": ["127.0.0.1", "localhost"],
            }
        )
        response = requests.get(url, timeout=3)
        assert response.status_code == 200
        assert _RedirectHandler.authorization == "Bearer private-test"
        assert _RedirectHandler.cookie == "session=private-test"
        assert _RedirectTargetHandler.authorization is None
        assert _RedirectTargetHandler.cookie is None
    finally:
        gateway.close()
        redirect.shutdown()
        redirect.server_close()
        target.shutdown()
        target.server_close()



class _RequiresUserAgentHandler(BaseHTTPRequestHandler):
    seen_user_agent = ""

    def log_message(self, _format, *args):
        return

    def do_GET(self):  # noqa: N802
        type(self).seen_user_agent = self.headers.get("User-Agent", "")
        if not type(self).seen_user_agent.startswith("Melodex/"):
            self.send_response(403)
            self.end_headers()
            return
        body = b"audio-bytes"
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _HeadRejectingAudioHandler(BaseHTTPRequestHandler):
    head_hits = 0
    get_hits = 0
    last_range = ""

    def log_message(self, _format, *args):
        return

    def do_HEAD(self):  # noqa: N802
        type(self).head_hits += 1
        self.send_response(405)
        self.end_headers()

    def do_GET(self):  # noqa: N802
        type(self).get_hits += 1
        type(self).last_range = self.headers.get("Range", "")
        body = b"x"
        self.send_response(206 if type(self).last_range else 200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(body)))
        if type(self).last_range:
            self.send_header("Content-Range", "bytes 0-0/12345")
        self.end_headers()
        self.wfile.write(body)


def test_gateway_adds_melodex_user_agent_when_provider_omits_one():
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _RequiresUserAgentHandler)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    gateway = PlaybackGateway()
    try:
        _RequiresUserAgentHandler.seen_user_agent = ""
        url = gateway.register(
            {
                "url": f"http://127.0.0.1:{upstream.server_address[1]}/audio",
                "_playback_allowed_hosts": ["127.0.0.1"],
            }
        )
        response = requests.get(url, timeout=3)
        assert response.status_code == 200
        assert response.content == b"audio-bytes"
        assert _RequiresUserAgentHandler.seen_user_agent.startswith("Melodex/")
    finally:
        gateway.close()
        upstream.shutdown()
        upstream.server_close()


def test_gateway_falls_back_to_tiny_get_when_audio_server_rejects_head():
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _HeadRejectingAudioHandler)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    gateway = PlaybackGateway()
    try:
        _HeadRejectingAudioHandler.head_hits = 0
        _HeadRejectingAudioHandler.get_hits = 0
        _HeadRejectingAudioHandler.last_range = ""
        url = gateway.register(
            {
                "url": f"http://127.0.0.1:{upstream.server_address[1]}/stream",
                "_playback_allowed_hosts": ["127.0.0.1"],
            }
        )
        response = requests.head(url, timeout=3)
        assert response.status_code == 206
        assert response.content == b""
        assert "Content-Length" not in response.headers
        assert "Content-Range" not in response.headers
        assert response.headers["Content-Type"] == "audio/mpeg"
        assert _HeadRejectingAudioHandler.head_hits == 1
        assert _HeadRejectingAudioHandler.get_hits == 1
        assert _HeadRejectingAudioHandler.last_range == "bytes=0-0"
    finally:
        gateway.close()
        upstream.shutdown()
        upstream.server_close()
