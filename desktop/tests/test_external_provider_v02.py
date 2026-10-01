from pathlib import Path

from melodex.provider import ExternalProvider


PROVIDER_CODE = '''import json
import sys
from helper import VALUE

for line in sys.stdin:
    req = json.loads(line)
    method = req["method"]
    if method == "catalog.search":
        result = {
            "items": [
                {
                    "provider_track_id": "1",
                    "title": "T",
                    "artist": VALUE,
                }
            ]
        }
    elif method == "playback.resolve":
        result = {
            "kind": "http",
            "url": "https://cdn.example/a.mp3",
            "headers": {"Referer": "https://example/"},
            "cookies": {"s": "1"},
            "seekable": True,
            "cache_policy": "session",
            "refresh_token": "r",
        }
    elif method == "playback.refresh":
        result = {
            "kind": "http",
            "url": "https://cdn.example/b.mp3",
            "headers": {},
            "cookies": {},
            "seekable": True,
            "cache_policy": "session",
        }
    else:
        result = {}
    print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}), flush=True)
'''


def test_external_provider_v02_refresh_and_vendor(tmp_path: Path):
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "helper.py").write_text("VALUE = 'Vendor Artist'\n", "utf-8")
    (tmp_path / "provider.py").write_text(PROVIDER_CODE, "utf-8")
    manifest = {
        "id": "org.example.v02",
        "name": "V02",
        "version": "1",
        "capabilities": ["search", "playback"],
        "permissions": {"network_hosts": ["cdn.example", "example"]},
        "entrypoints": {"python": "provider.py"},
    }
    provider = ExternalProvider(tmp_path, manifest)
    try:
        item = provider.search("x", 1)[0]
        assert item["artist"] == "Vendor Artist"
        resolved = provider.resolve(item)
        assert resolved["cookies"]["s"] == "1"
        refreshed = provider.refresh(resolved)
        assert refreshed["url"].endswith("b.mp3")
    finally:
        provider.close()

def test_external_provider_preserves_empty_host_policy(tmp_path: Path):
    manifest = {
        "id": "org.example.nohosts",
        "name": "No Hosts",
        "version": "1",
        "capabilities": ["playback"],
        "permissions": {"network_hosts": []},
        "entrypoints": {"python": "provider.py"},
    }
    provider = ExternalProvider(tmp_path, manifest)
    merged = provider._merge_playback(
        {"track_id": "1"},
        {"kind": "http", "url": "https://example.invalid/audio.mp3"},
    )
    assert "_playback_allowed_hosts" in merged
    assert merged["_playback_allowed_hosts"] == []


def test_external_provider_does_not_inherit_arbitrary_parent_secrets(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MELODEX_TEST_SECRET", "do-not-forward")
    code = """import json, os, sys
for line in sys.stdin:
    req = json.loads(line)
    result = {"items": [{"provider_track_id": "1", "title": os.getenv("MELODEX_TEST_SECRET", "missing"), "artist": os.getenv("MELODEX_PROVIDER_ID", "")}]}
    print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}), flush=True)
"""
    (tmp_path / "provider.py").write_text(code, "utf-8")
    manifest = {
        "id": "org.example.env",
        "name": "Env",
        "version": "1",
        "capabilities": ["search"],
        "permissions": {"network_hosts": []},
        "entrypoints": {"python": "provider.py"},
    }
    provider = ExternalProvider(tmp_path, manifest)
    try:
        item = provider.search("x", 1)[0]
        assert item["title"] == "missing"
        assert item["artist"] == "org.example.env"
    finally:
        provider.close()


def test_external_provider_receives_only_brokered_configuration(tmp_path: Path):
    code = """import json, sys
for line in sys.stdin:
    req = json.loads(line)
    params = req.get("params") or {}
    config = params.get("_melodex_config") or {}
    result = {
        "items": [{
            "provider_track_id": "1",
            "title": config.get("api_token", "missing"),
            "artist": str(config.get("region", "missing")),
        }]
    }
    print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}), flush=True)
"""
    (tmp_path / "provider.py").write_text(code, "utf-8")
    manifest = {
        "id": "org.example.config",
        "name": "Config",
        "version": "1",
        "capabilities": ["search"],
        "permissions": {"network_hosts": []},
        "configuration": [
            {"key": "api_token", "label": "API token", "type": "secret"},
            {"key": "region", "label": "Region", "type": "string"},
        ],
        "entrypoints": {"python": "provider.py"},
    }
    provider = ExternalProvider(tmp_path, manifest)
    provider.configure({"api_token": "brokered-secret", "region": "eu"})
    try:
        item = provider.search("x", 1)[0]
        assert item["title"] == "brokered-secret"
        assert item["artist"] == "eu"
    finally:
        provider.close()


def test_external_provider_recommendations_receive_brokered_secret(tmp_path: Path):
    code = """import json, sys
for line in sys.stdin:
    req = json.loads(line)
    params = req.get("params") or {}
    if req.get("method") == "recommendations.get":
        config = params.get("_melodex_config") or {}
        seed = params.get("seed") or {}
        result = {
            "items": [{
                "provider_track_id": "rec-1",
                "title": "Recommended",
                "artist": seed.get("artist", "Unknown"),
                "metadata": {
                    "configured": config.get("api_key") == "secret-key",
                    "playable": False,
                },
            }],
            "next_cursor": None,
        }
    else:
        result = {}
    print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}), flush=True)
"""
    (tmp_path / "provider.py").write_text(code, "utf-8")
    manifest = {
        "id": "org.example.recommend",
        "name": "Recommend",
        "version": "1",
        "capabilities": ["recommendations"],
        "permissions": {"network_hosts": []},
        "configuration": [
            {"key": "api_key", "label": "API key", "type": "secret", "required": True},
        ],
        "entrypoints": {"python": "provider.py"},
    }
    provider = ExternalProvider(tmp_path, manifest)
    provider.configure({"api_key": "secret-key"})
    try:
        items = provider.recommend({"artist": "Seed Artist", "title": "Seed Song"}, 5)
        assert items[0]["title"] == "Recommended"
        assert items[0]["artist"] == "Seed Artist"
        assert items[0]["metadata"]["configured"] is True
    finally:
        provider.close()


def test_external_provider_adds_exact_resolved_media_host(tmp_path: Path):
    manifest = {
        "id": "org.example.dynamic-media",
        "name": "Dynamic Media",
        "version": "1",
        "capabilities": ["playback"],
        "permissions": {"network_hosts": ["api.example"]},
        "entrypoints": {"python": "provider.py"},
    }
    provider = ExternalProvider(tmp_path, manifest)
    merged = provider._merge_playback(
        {"track_id": "1"},
        {"kind": "http", "url": "https://cdn.other.example/audio.mp3"},
    )
    assert merged["_playback_allowed_hosts"] == [
        "api.example",
        "cdn.other.example",
    ]


def test_external_provider_uses_bounded_manifest_rpc_timeout(tmp_path: Path):
    manifest = {
        "id": "org.example.slow",
        "name": "Slow upstream",
        "version": "1",
        "capabilities": ["search"],
        "permissions": {"network_hosts": []},
        "entrypoints": {"python": "provider.py"},
        "rpc_timeout_seconds": 40,
    }
    provider = ExternalProvider(tmp_path, manifest)
    assert provider.timeout == 40.0

    too_large = ExternalProvider(tmp_path, {**manifest, "rpc_timeout_seconds": 999})
    assert too_large.timeout == 60.0

    invalid = ExternalProvider(tmp_path, {**manifest, "rpc_timeout_seconds": "nope"})
    assert invalid.timeout == 12.0
