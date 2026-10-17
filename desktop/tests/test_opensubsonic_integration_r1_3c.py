"""R1-3C: an installed OpenSubsonic provider through the real MPP host and gateway.

Purely local, disposable fake music server. No real server or credentials required.
This is transport-level qualification, not actual Qt audio-output qualification.
"""
from __future__ import annotations

import hashlib
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

import pytest

from melodex.playback_gateway import PlaybackGateway
from melodex.provider import ProviderInstaller

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bundled_provider_sources" / "opensubsonic_personal"
PROVIDER_ID = "org.melodex.opensubsonic.personal"
AUDIO = b"0123456789abcdef"


@pytest.fixture
def fake_subsonic_server():
    calls: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, _format, *_args):
            # Subsonic auth tokens occur in query strings: never log URLs.
            return

        def do_HEAD(self):
            self._reply(head_only=True)

        def do_GET(self):
            self._reply(head_only=False)

        def _reply(self, *, head_only: bool):
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            token = (params.get("t") or [""])[0]
            salt = (params.get("s") or [""])[0]
            user = (params.get("u") or [""])[0]
            valid = (
                user == "listener"
                and salt
                and token == hashlib.md5(("correct-password" + salt).encode()).hexdigest()
            )
            operation = parsed.path.rsplit("/", 1)[-1]
            calls.append({"operation": operation, "valid": valid,
                          "range": self.headers.get("Range")})
            if not valid:
                return self._json_response({
                    "subsonic-response": {"status": "failed",
                        "error": {"code": 40, "message": "Wrong username or password"}}
                }, head_only=head_only)
            if operation == "ping.view":
                payload = {"subsonic-response": {"status": "ok"}}
            elif operation == "search3.view":
                payload = {"subsonic-response": {"status": "ok", "searchResult3": {
                    "song": [{"id": "track-1", "title": "Synthetic Song",
                              "artist": "Test Artist", "album": "Test Album",
                              "duration": 16}]
                }}}
            elif operation == "getSong.view":
                if params.get("id") != ["track-1"]:
                    self.send_error(404)
                    return
                payload = {"subsonic-response": {"status": "ok", "song": {
                    "id": "track-1", "title": "Synthetic Song", "artist": "Test Artist",
                    "album": "Test Album", "duration": 16,
                }}}
            elif operation == "stream.view":
                if params.get("id") != ["track-1"]:
                    self.send_error(404)
                    return
                requested = self.headers.get("Range")
                range_header = None
                if requested == "bytes=4-7":
                    status, body = 206, AUDIO[4:8]
                    range_header = "bytes 4-7/16"
                elif requested == "bytes=0-4095":
                    status, body = 206, AUDIO
                    range_header = "bytes 0-15/16"
                else:
                    status, body = 200, AUDIO
                self.send_response(status)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(len(body)))
                if status == 206:
                    self.send_header("Content-Range", range_header)
                self.end_headers()
                if not head_only:
                    self.wfile.write(body)
                return
            else:
                self.send_error(404)
                return
            return self._json_response(payload, head_only=head_only)

        def _json_response(self, payload, *, head_only: bool):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head_only:
                self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", calls
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


@pytest.fixture
def installed_provider(tmp_path):
    package = tmp_path / "r1-3c.mdxprovider"
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ("manifest.json", "provider.py", "README.md", "LICENSE", "SOURCE_POLICY.md"):
            archive.write(SOURCE / name, name)
    installer = ProviderInstaller(tmp_path / "plugins")
    folder = installer.install(package)
    manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
    assert manifest["id"] == PROVIDER_ID
    found = installer.load_installed()
    provider = next(row for row in found if row.info.id == PROVIDER_ID)
    try:
        yield provider
    finally:
        for item in found:
            item.close()


def test_installed_provider_auth_search_lookup_gateway_seek_and_refresh(
    fake_subsonic_server, installed_provider
):
    server_url, calls = fake_subsonic_server
    provider = installed_provider
    provider.configure({
        "server_url": server_url, "username": "listener",
        "password": "correct" + "-password", "allow_insecure_http": True,
    })
    assert provider.health_check()["status"] == "ready"
    songs = provider.search("Synthetic", limit=5)
    assert len(songs) == 1
    track = songs[0]
    assert track["provider_id"] == PROVIDER_ID
    assert track["title"] == "Synthetic Song"
    assert "correct-password" not in json.dumps(track)
    assert "t=" not in json.dumps(track)
    assert "s=" not in json.dumps(track)

    # Exercise the installed provider's real JSON-RPC child process, not the
    # Python adapter module imported directly into this test process.
    by_id = provider._rpc("catalog.get_track", {
        "provider_track_id": track["track_id"]
    })
    assert by_id["title"] == track["title"]
    assert by_id["provider_track_id"] == track["track_id"]

    first = provider.resolve(track)
    second = provider.refresh(track)
    assert first["url"] != second["url"]  # fresh salted auth
    assert "correct-password" not in first["url"]
    assert first["_playback_allowed_hosts"] == ["127.0.0.1", "localhost"]

    gateway = PlaybackGateway()
    try:
        playback_url = gateway.register(first)
        request = Request(playback_url, headers={"Range": "bytes=4-7"})
        with urlopen(request, timeout=5) as response:
            assert response.status == 206
            assert response.headers["Content-Range"] == "bytes 4-7/16"
            assert response.read() == b"4567"
        assert any(row["operation"] == "stream.view" and
                   row["range"] == "bytes=4-7" and row["valid"] for row in calls)
        assert gateway.diagnostics_snapshot()["bytes_served"] == 4
        assert gateway.unregister(playback_url) is True
        with pytest.raises(HTTPError) as error:
            urlopen(playback_url, timeout=5)
        assert error.value.code == 404
    finally:
        gateway.close()


def test_wrong_password_never_reveals_private_data(fake_subsonic_server, installed_provider):
    server_url, calls = fake_subsonic_server
    installed_provider.configure({
        "server_url": server_url, "username": "listener",
        "password": "incorrect" + "-password", "allow_insecure_http": True,
    })
    result = installed_provider.health_check()
    assert result["status"] == "unavailable"
    message = result["message"]
    assert "incorrect-password" not in message
    assert "rest/ping.view" not in message
    assert "t=" not in message
    with pytest.raises(RuntimeError, match="Subsonic code 40") as exc:
        installed_provider.search("Synthetic")
    assert "incorrect-password" not in str(exc.value)
    assert any(not row["valid"] for row in calls)


def test_live_probe_uses_real_host_and_gateway_without_metadata(
    fake_subsonic_server
):
    import runpy

    server_url, calls = fake_subsonic_server
    tool = runpy.run_path(str(ROOT / "tools" / "qualify_opensubsonic_live.py"),
                          run_name="r1_3c_test")
    steps = tool["qualify"](
        server=server_url, username="listener", password="correct" + "-password",
        allow_http=True, query="Synthetic",
    )
    assert all(steps.values()), steps
    assert any(row["range"] == "bytes=0-4095" and row["valid"] for row in calls)
    failed = tool["qualify"](
        server=server_url, username="listener", password="invalid" + "-secret",
        allow_http=True, query="Synthetic",
    )
    assert failed["provider_configured"] is True
    assert failed["authenticated_health"] is False
    assert failed["range_seek_206"] is False
