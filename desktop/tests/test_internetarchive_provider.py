from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_provider():
    path = (
        Path(__file__).resolve().parents[1]
        / "bundled_provider_sources"
        / "internetarchive_audio"
        / "provider.py"
    )
    spec = importlib.util.spec_from_file_location("melodex_test_internetarchive", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_search_does_not_fetch_item_metadata(monkeypatch):
    provider = _load_provider()
    calls = []

    def fake_json(url, *, params=None, timeout=12.0):
        calls.append((url, params))
        return {
            "response": {
                "docs": [
                    {
                        "identifier": "example-audio",
                        "title": "Example Audio",
                        "creator": "Example Artist",
                    }
                ]
            }
        }

    monkeypatch.setattr(provider, "_json", fake_json)
    rows = provider._search("example", 10)

    assert len(rows) == 1
    assert rows[0]["provider_track_id"] == "example-audio"
    assert rows[0]["title"] == "Example Audio"
    assert len(calls) == 1
    assert calls[0][0] == provider.SEARCH


def test_resolve_fetches_metadata_lazily_and_selects_mp3(monkeypatch):
    provider = _load_provider()
    provider._CACHE.clear()
    provider._META_CACHE.clear()

    provider._CACHE["example-audio"] = provider._search_track(
        {
            "identifier": "example-audio",
            "title": "Example Audio",
            "creator": "Example Artist",
        }
    )

    def fake_json(url, *, params=None, timeout=12.0):
        assert url.endswith("/metadata/example-audio")
        return {
            "metadata": {
                "title": "Example Audio",
                "creator": "Example Artist",
                "description": "Fixture",
            },
            "files": [
                {"name": "example.flac", "format": "Flac", "size": "9000"},
                {
                    "name": "example.mp3",
                    "format": "VBR MP3",
                    "source": "original",
                    "size": "5000",
                },
            ],
        }

    monkeypatch.setattr(provider, "_json", fake_json)
    resource = provider._resolve("example-audio")

    assert resource["kind"] == "http"
    assert resource["url"].endswith("/example-audio/example.mp3")
    assert resource["seekable"] is True
    assert resource["cache_policy"] == "session"


def test_metadata_is_cached_after_first_resolve(monkeypatch):
    provider = _load_provider()
    provider._CACHE.clear()
    provider._META_CACHE.clear()
    calls = []

    def fake_json(url, *, params=None, timeout=12.0):
        calls.append(url)
        return {
            "metadata": {"title": "Cached Item", "creator": "Archive"},
            "files": [{"name": "audio.mp3", "format": "VBR MP3", "size": "10"}],
        }

    monkeypatch.setattr(provider, "_json", fake_json)

    provider._resolve("cached-item")
    provider._resolve("cached-item")

    assert len(calls) == 1
