from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "bundled_provider_sources"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_librivox_manifest_allows_regional_archive_cdn_hosts():
    manifest = json.loads(
        (ROOT / "librivox" / "manifest.json").read_text("utf-8")
    )
    hosts = set((manifest.get("permissions") or {}).get("network_hosts") or [])
    assert "archive.org" in hosts
    assert "*.archive.org" in hosts
    assert "*.us.archive.org" not in hosts


def test_wikimedia_resolve_sends_descriptive_user_agent():
    module = _load(
        "wikimedia_playback_headers",
        ROOT / "wikimedia_commons_audio" / "provider.py",
    )
    module._cache.clear()
    module._cache["123"] = {
        "provider_track_id": "123",
        "track_id": "123",
        "title": "Fixture",
        "artist": "Fixture",
        "metadata": {
            "media_url": "https://upload.wikimedia.org/example.ogg",
            "mime": "audio/ogg",
        },
    }

    resource = module._resolve("123")

    assert resource["url"] == "https://upload.wikimedia.org/example.ogg"
    assert resource["headers"]["User-Agent"].startswith(
        "Melodex-Wikimedia-Commons-Audio/"
    )
    assert "github.com/Cliff-Lee/melodex" in resource["headers"]["User-Agent"]
    assert resource["headers"]["Accept-Encoding"] == "identity"
