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
