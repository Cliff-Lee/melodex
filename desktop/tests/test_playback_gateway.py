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



class _UserAgentHandler(BaseHTTPRequestHandler):
    seen_user_agent = None

    def log_message(self, _format, *args):
        return

    def do_GET(self):  # noqa: N802
        type(self).seen_user_agent = self.headers.get("User-Agent")
        body = b"audio"
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
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
        assert gateway.diagnostics_snapshot() == {
            "requests": 1,
            "active_requests": 0,
            "bytes_served": 4,
            "failures": 0,
        }
    finally:
        gateway.close()
        upstream.shutdown()
        upstream.server_close()



def test_gateway_diagnostics_count_failed_request_without_resource_metadata():
    gateway = PlaybackGateway()
    try:
        gateway.register(
            {
                "url": "http://127.0.0.1:1/audio",
                "_playback_allowed_hosts": ["127.0.0.1"],
            }
        )
        response = requests.get(
            f"http://127.0.0.1:{gateway.port}/not-a-playback-resource",
            timeout=3,
        )
        assert response.status_code == 404
        assert gateway.diagnostics_snapshot() == {
            "requests": 1,
            "active_requests": 0,
            "bytes_served": 0,
            "failures": 1,
        }
    finally:
        gateway.close()

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

def test_gateway_allows_regional_archive_cdn_under_archive_wildcard():
    gateway = PlaybackGateway()
    try:
        url = gateway.validate_resource(
            {
                "url": "https://dn711108.ca.archive.org/0/items/book/chapter.mp3",
                "_playback_allowed_hosts": ["archive.org", "*.archive.org"],
            }
        )
        assert url.startswith("https://dn711108.ca.archive.org/")
    finally:
        gateway.close()

def test_gateway_supplies_descriptive_user_agent_when_provider_omits_one():
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _UserAgentHandler)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    _UserAgentHandler.seen_user_agent = None
    gateway = PlaybackGateway()
    try:
        url = gateway.register(
            {
                "url": f"http://127.0.0.1:{upstream.server_address[1]}/audio",
                "_playback_allowed_hosts": ["127.0.0.1"],
            }
        )
        response = requests.get(url, timeout=3)
        assert response.status_code == 200
        assert _UserAgentHandler.seen_user_agent is not None
        assert _UserAgentHandler.seen_user_agent.startswith("Melodex-Playback-Gateway/")
    finally:
        gateway.close()
        upstream.shutdown()
        upstream.server_close()


def test_gateway_preserves_provider_user_agent():
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _UserAgentHandler)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    _UserAgentHandler.seen_user_agent = None
    gateway = PlaybackGateway()
    try:
        url = gateway.register(
            {
                "url": f"http://127.0.0.1:{upstream.server_address[1]}/audio",
                "headers": {"User-Agent": "Provider-Specific/2.0"},
                "_playback_allowed_hosts": ["127.0.0.1"],
            }
        )
        response = requests.get(url, timeout=3)
        assert response.status_code == 200
        assert _UserAgentHandler.seen_user_agent == "Provider-Specific/2.0"
    finally:
        gateway.close()
        upstream.shutdown()
        upstream.server_close()

