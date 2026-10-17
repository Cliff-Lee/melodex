"""R1-3B: token-safe playback errors and HTTP Range gateway regression tests."""
from __future__ import annotations

from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from melodex.playback_gateway import PlaybackGateway


def test_upstream_exception_does_not_expose_private_stream_url():
    gateway = PlaybackGateway()
    private_url = "https://music.example/rest/stream.view?t=MY_PRIVATE_SUBSONIC_TOKEN&s=SALT"
    try:
        loopback_url = gateway.register({
            "kind": "http", "url": private_url,
            "_playback_allowed_hosts": ["music.example"],
        })
        with patch.object(gateway, "_request_upstream", side_effect=RuntimeError(
            "Failed while requesting " + private_url
        )):
            with pytest.raises(HTTPError) as caught:
                urlopen(loopback_url, timeout=3)
            body = caught.value.read().decode("utf-8", errors="replace")
            assert caught.value.code == 502
            assert "Upstream playback request failed" in body
            assert "MY_PRIVATE_SUBSONIC_TOKEN" not in body
            assert "SALT" not in body
            assert "stream.view" not in body
        assert gateway.diagnostics_snapshot()["failures"] == 1
    finally:
        gateway.close()


def test_gateway_still_passes_range_to_upstream_and_returns_partial_content():
    gateway = PlaybackGateway()
    called = []

    class FakeResponse:
        status_code = 206
        headers = {
            "Content-Range": "bytes 4-7/10",
            "Content-Length": "4",
            "Accept-Ranges": "bytes",
            "Content-Type": "audio/mpeg",
        }

        def iter_content(self, chunk_size):
            assert chunk_size > 0
            yield b"ABCD"

        def close(self):
            return None

    def upstream(method, url, headers, allowed, timeout, stream):
        called.append((method, url, dict(headers), allowed, stream))
        return FakeResponse()

    try:
        loopback_url = gateway.register({
            "kind": "http", "url": "https://music.example/rest/stream.view?t=private",
            "_playback_allowed_hosts": ["music.example"],
        })
        request = Request(loopback_url, headers={"Range": "bytes=4-7"})
        with patch.object(gateway, "_request_upstream", side_effect=upstream):
            with urlopen(request, timeout=3) as response:
                assert response.status == 206
                assert response.headers.get("Content-Range") == "bytes 4-7/10"
                assert response.read() == b"ABCD"
        assert called and called[0][2]["Range"] == "bytes=4-7"
        assert called[0][3] == ["music.example"]
    finally:
        gateway.close()
