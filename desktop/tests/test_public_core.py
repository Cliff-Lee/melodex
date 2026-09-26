from pathlib import Path
import json, tempfile, zipfile

from melodex.providers.local_files import LocalFilesProvider
from melodex.provider import ProviderInstaller
from melodex.provider_manager import ProviderManager
from melodex.user_state import UserState
from melodex.flow import FlowEngine
from melodex.mind import MindEngine


def test_local_provider_search(tmp_path: Path):
    music = tmp_path / "music"; music.mkdir()
    (music / "Artist - Example Song.mp3").write_bytes(b"not-real-audio")
    p = LocalFilesProvider([music])
    assert len(p.tracks) == 1
    assert p.search("Example")
    assert p.resolve(p.tracks[0])["local_path"].endswith("Example Song.mp3")


def test_provider_package_install(tmp_path: Path):
    pkg = tmp_path / "demo.mdxprovider"
    manifest = {
        "schema_version": 1, "id":"org.example.demo", "name":"Demo", "version":"1.0",
        "publisher":"Test", "protocol_version":"1.0", "capabilities":["search"],
        "permissions":{"network_hosts":[],"offline_downloads":False,"local_files":False},
        "entrypoints":{"python":"provider.py"}
    }
    with zipfile.ZipFile(pkg, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("provider.py", "print('')\n")
    dest = ProviderInstaller(tmp_path / "providers").install(pkg)
    assert (dest / "manifest.json").exists()


def test_mind_builds_local_session(tmp_path: Path):
    state = UserState(tmp_path / "state.sqlite")
    flow = FlowEngine(tmp_path / "flow.sqlite")
    mind = MindEngine(state, flow)
    tracks = []
    for i in range(8):
        f = tmp_path / f"t{i}.mp3"; f.write_bytes(b"x")
        tracks.append({"provider_id":"local","track_id":str(f),"rel":f"local:{f}","local_path":str(f),"artist":f"Artist {i}","title":f"Track {i}","duration":200})
    plan = mind.build_session(tracks, lambda t: Path(t["local_path"]), minutes=20, adventure=0.4, mode="balanced")
    assert plan["tracks"]
    assert len(plan["tracks"]) <= len(tracks)
    flow.close(); state.close()


def test_public_tree_has_no_legacy_private_connector_names():
    root = Path(__file__).resolve().parents[2]
    # Keep this intentionally narrow: public source should not accidentally ship
    # source-specific private connector code from earlier private builds.
    banned = ["".join(chr(x) for x in [109,117,115,105,99,109,112,51,46,114,117]), "".join(chr(x) for x in [108,105,115,116,101,110,46,109,117,115,105,99,109,112,51,46,114,117])]
    for p in root.rglob("*"):
        if not p.is_file() or any(x in p.parts for x in {".git","__pycache__","build","dist"}):
            continue
        if p.suffix.lower() not in {".py",".md",".json",".yaml",".yml",".toml",".kt",".kts",".txt"}:
            continue
        text = p.read_text("utf-8", errors="ignore").lower()
        for term in banned:
            assert term not in text, f"private connector reference in {p}"


def test_provider_bridge_serves_local_media(tmp_path: Path):
    import requests
    from melodex.bridge_server import ProviderBridge
    mgr = ProviderManager(tmp_path / "data")
    music = tmp_path / "music"; music.mkdir()
    payload = b"0123456789abcdef"
    f = music / "test.mp3"; f.write_bytes(payload)
    mgr.set_local_roots([music])
    track = mgr.local_catalog()[0]
    bridge = ProviderBridge(mgr, "127.0.0.1", 0, token="test-token")
    bridge.start()
    try:
        base = f"http://127.0.0.1:{bridge.port}"
        r = requests.get(base + "/v1/resolve", params={"provider":"local","id":track["track_id"]}, headers={"Authorization":"Bearer test-token"}, timeout=3)
        assert r.status_code == 200
        stream_url = r.json()["stream_url"]
        m = requests.get(stream_url, headers={"Range":"bytes=2-5"}, timeout=3)
        assert m.status_code == 206
        assert m.content == payload[2:6]
    finally:
        bridge.stop(); mgr.close()
