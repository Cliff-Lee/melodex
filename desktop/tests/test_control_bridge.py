from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from melodex.bridge_server import ProviderBridge
from melodex.control_client import MelodexControlClient


@dataclass
class Info:
    id: str
    name: str
    description: str = ""
    capabilities: list[str] = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = ["search", "playback"]


class FakeProvider:
    def __init__(self, pid: str):
        self.info = Info(pid, pid.title())


class FakeManager:
    def __init__(self, media: Path):
        self.media = media
        self.providers = {"local": FakeProvider("local"), "web": FakeProvider("web")}

    def provider_order(self):
        return ["local", "web"]

    def search(self, query, provider_id="all", limit=50):
        return [{"provider_id": "web", "track_id": "1", "artist": "Example", "title": query, "stream_url": "https://example.invalid/a.mp3"}]

    def browse(self, provider_id, kind="featured", limit=50):
        return self.search("Featured", provider_id, limit)

    def resolve(self, track):
        if track.get("provider_id") == "local":
            return {"provider_id": "local", "track_id": str(self.media), "artist": "Local", "title": "Song", "local_path": str(self.media)}
        return {"provider_id": "web", "track_id": "1", "artist": track.get("artist", "Example"), "title": track.get("title", "Song"), "album": track.get("album", ""), "stream_url": "https://example.invalid/a.mp3"}

    def resolve_playlist(self, tracks):
        return {"requested": len(tracks), "tracks": [self.resolve(x) for x in tracks], "unresolved": []}


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
        assert client.providers()[0]["id"] == "local"
        assert client.search("Needle")[0]["title"] == "Needle"
        resolved = client.resolve("Artist", "Track")
        assert resolved["provider_id"] == "web"
        assert "local_path" not in resolved
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
