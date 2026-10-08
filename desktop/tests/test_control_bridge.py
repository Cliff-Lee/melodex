from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import stat
import urllib.error
import urllib.request

from melodex.bridge_server import ProviderBridge
from melodex.control_client import MelodexControlClient


@dataclass
class Info:
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    capabilities: list[str] = None
    permissions: dict = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = ["search", "playback"]
        if self.permissions is None:
            self.permissions = {"network_hosts": []}


class FakeProvider:
    def __init__(self, pid: str):
        self.info = Info(pid, pid.title())


class FakeManager:
    def __init__(self, media: Path):
        self.media = media
        self.providers = {"local": FakeProvider("local"), "web": FakeProvider("web")}

    def provider_order(self):
        return ["local", "web"]

    def installation_record(self, plugin_id):
        if plugin_id == "web":
            return {
                "id": "web",
                "method": "registry",
                "registry_verified": True,
                "package_sha256": "abc",
                "version": "1.0.0",
            }
        return {}

    def search(self, query, provider_id="all", limit=50):
        return [{"provider_id": "web", "track_id": "1", "artist": "Example", "title": query, "stream_url": "https://example.invalid/a.mp3"}]

    def recommend(self, seed, provider_id="all", limit=25):
        return [{
            "provider_id": "recs",
            "track_id": "r1",
            "artist": "Recommended Artist",
            "title": "Recommended Song",
            "album": "",
            "metadata": {"playable": False, "seed": dict(seed)},
        }]

    def browse(self, provider_id, kind="featured", limit=50):
        return self.search("Featured", provider_id, limit)

    def resolve(self, track):
        if track.get("provider_id") == "local":
            return {"provider_id": "local", "track_id": str(self.media), "artist": "Local", "title": "Song", "local_path": str(self.media)}
        return {"provider_id": "web", "track_id": "1", "artist": track.get("artist", "Example"), "title": track.get("title", "Song"), "album": track.get("album", ""), "stream_url": "https://example.invalid/a.mp3"}

    def resolve_playlist(self, tracks):
        return {"requested": len(tracks), "tracks": [self.resolve(x) for x in tracks], "unresolved": []}

    def inspect_resolution(self, track, limit=20):
        candidate = {"provider_id":"web","track_id":"1","artist":track.get("artist","Example"),"title":track.get("title","Song"),"album":track.get("album",""),"stream_url":"https://example.invalid/a.mp3"}
        return {"requested":dict(track),"minimum_score":0.62,"preferred":None,"blocked_count":0,"candidates":[{"track":candidate,"score":0.97,"provider_id":"web","provider_rank":1,"title_score":1.0,"artist_score":1.0,"album_score":1.0,"version_penalty":0.0,"duration_adjustment":0.0,"duration_delta":None,"preferred":False,"candidate_key":"web:1","flags":[],"reasons":["exact title","exact artist"]}][:limit]}

    def prefer_resolution(self, requested, candidate):
        self.preferred = (dict(requested), dict(candidate))

    def block_resolution(self, requested, candidate):
        self.blocked = (dict(requested), dict(candidate))

    def clear_resolution_preference(self, requested):
        self.preferred = None

    def clear_resolution_blocks(self, requested):
        self.blocked = None


class FakeController:
    def __init__(self):
        self.actions = []
        self.queue = []

    def __call__(self, action, args):
        self.actions.append((action, dict(args)))
        if action == "status":
            return {"playing": bool(self.queue), "queue": list(self.queue), "current_track": self.queue[0] if self.queue else None, "index": 0 if self.queue else -1}
        if action == "set_queue":
            self.queue = list(args.get("tracks") or [])
        elif action == "append_queue":
            self.queue.extend(list(args.get("tracks") or []))
        return {"action": action}


def test_control_bridge_and_client(tmp_path: Path):
    media = tmp_path / "song.mp3"; media.write_bytes(b"0123456789")
    state = tmp_path / "bridge.json"
    controller = FakeController()
    bridge = ProviderBridge(FakeManager(media), "127.0.0.1", 0, token="secret", controller=controller, state_path=state)
    bridge.start()
    try:
        client = MelodexControlClient.from_state(state, timeout=3)
        assert client.health()["control"] is True
        providers = client.providers()
        assert providers[0]["id"] == "local"
        assert providers[1]["installation"]["registry_verified"] is True
        assert providers[1]["permissions"]["network_hosts"] == []
        assert client.search("Needle")[0]["title"] == "Needle"
        recs = client.recommendations("Massive Attack", "Teardrop")
        assert recs[0]["title"] == "Recommended Song"
        assert recs[0]["metadata"]["playable"] is False
        resolved = client.resolve("Artist", "Track")
        assert resolved["provider_id"] == "web"
        assert "local_path" not in resolved
        inspected = client.resolve_candidates("Artist", "Track")
        assert inspected["candidates"][0]["score"] == 0.97
        candidate = inspected["candidates"][0]["track"]
        assert client.prefer_match(inspected["requested"], candidate)["ok"] is True
        assert client.block_match(inspected["requested"], candidate)["ok"] is True
        assert client.reset_match_memory(inspected["requested"])["ok"] is True
        played = client.play("Artist", "Track")
        assert played["ok"] is True
        assert controller.actions[-1][0] == "set_queue"
        queued = client.queue_tracks([{"artist": "A", "title": "One"}, {"artist": "B", "title": "Two"}], replace=False)
        assert queued["matched"] == 2
        assert controller.actions[-1][0] == "append_queue"
        assert len(client.status()["queue"]) == 3
        assert client.control("next")["ok"] is True
    finally:
        bridge.stop()
    assert not state.exists()


def test_client_follows_bridge_restart(tmp_path: Path):
    media = tmp_path / "song.mp3"; media.write_bytes(b"x")
    state = tmp_path / "bridge.json"
    manager = FakeManager(media)
    controller = FakeController()
    first = ProviderBridge(manager, "127.0.0.1", 0, token="one", controller=controller, state_path=state)
    first.start()
    client = MelodexControlClient.from_state(state, timeout=3)
    assert client.health()["ok"] is True
    first.stop()
    second = ProviderBridge(manager, "127.0.0.1", 0, token="two", controller=controller, state_path=state)
    second.start()
    try:
        # Same client instance re-reads bridge.json on every request.
        assert client.health()["ok"] is True
    finally:
        second.stop()



def _bridge_http(url: str, method: str = "GET", payload: dict | None = None, token: str = ""):
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_paired_device_token_persists_and_can_be_revoked(tmp_path: Path):
    media = tmp_path / "song.mp3"
    media.write_bytes(b"track")
    state = tmp_path / "bridge.json"
    manager = FakeManager(media)
    controller = FakeController()
    first = ProviderBridge(manager, "127.0.0.1", 0, token="desktop-one", controller=controller, state_path=state)
    first.start()
    try:
        code = first.new_pairing_code()
        pair_url = f"http://127.0.0.1:{first.port}/v1/pair"
        status, paired = _bridge_http(
            pair_url,
            "POST",
            {"code": code, "device_name": "  Android phone  "},
        )
        assert status == 200
        assert paired["ok"] is True
        assert paired["device_name"] == "Android phone"
        token = paired["token"]
        device_id = paired["device_id"]

        status, providers = _bridge_http(
            f"http://127.0.0.1:{first.port}/v1/providers",
            token=token,
        )
        assert status == 200
        assert providers["providers"][0]["id"] == "local"

        status, _ = _bridge_http(pair_url, "POST", {"code": code, "device_name": "second"})
        assert status == 401

        paired_state = tmp_path / "bridge.paired-devices.json"
        assert paired_state.exists()
        assert token not in paired_state.read_text("utf-8")
        assert len(json.loads(paired_state.read_text("utf-8"))["devices"]) == 1
        if os.name != "nt":
            assert stat.S_IMODE(paired_state.stat().st_mode) & 0o077 == 0
    finally:
        first.stop()

    second = ProviderBridge(manager, "127.0.0.1", 0, token="desktop-two", controller=controller, state_path=state)
    second.start()
    try:
        status, _ = _bridge_http(f"http://127.0.0.1:{second.port}/v1/providers", token=token)
        assert status == 200

        status, response = _bridge_http(
            f"http://127.0.0.1:{second.port}/v1/unpair",
            "POST",
            {"device_id": device_id},
            token=token,
        )
        assert status == 200
        assert response["ok"] is True
        status, _ = _bridge_http(f"http://127.0.0.1:{second.port}/v1/providers", token=token)
        assert status == 401
    finally:
        second.stop()


def test_pairing_code_rejects_expired_code(tmp_path: Path):
    media = tmp_path / "song.mp3"
    media.write_bytes(b"track")
    bridge = ProviderBridge(FakeManager(media), "127.0.0.1", 0, token="desktop", state_path=tmp_path / "bridge.json")
    bridge.start()
    try:
        code = bridge.new_pairing_code()
        bridge._pairing_expires_at = 0
        status, response = _bridge_http(
            f"http://127.0.0.1:{bridge.port}/v1/pair",
            "POST",
            {"code": code, "device_name": "phone"},
        )
        assert status == 401
        assert "expired" in response["error"]
        assert bridge.paired_devices() == []
    finally:
        bridge.stop()
