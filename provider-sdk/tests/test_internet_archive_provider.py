from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROVIDER_PATH = ROOT / "official-providers" / "internet-archive" / "provider.py"


def load_provider():
    spec = importlib.util.spec_from_file_location("melodex_ia_provider", PROVIDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_metadata():
    return {
        "metadata": {
            "title": "Example Concert",
            "creator": "Example Artist",
            "date": "2001-04-05",
            "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
        },
        "files": [
            {
                "name": "track01.wav",
                "format": "WAVE",
                "title": "First Track",
                "track": "1",
                "length": "3:30",
                "source": "original",
            },
            {
                "name": "track01_vbr.mp3",
                "format": "VBR MP3",
                "title": "First Track",
                "track": "1",
                "length": "3:30",
                "original": "track01.wav",
                "source": "derivative",
            },
            {
                "name": "track01.ogg",
                "format": "Ogg Vorbis",
                "title": "First Track",
                "track": "1",
                "length": "3:30",
                "original": "track01.wav",
                "source": "derivative",
            },
        ],
    }


def test_preferred_files_collapse_derivatives():
    provider = load_provider()
    files = provider._preferred_audio_files(sample_metadata()["files"])
    assert len(files) == 1
    assert files[0]["name"] == "track01_vbr.mp3"


def test_tracks_for_identifier_preserves_source_and_license(monkeypatch):
    provider = load_provider()
    monkeypatch.setattr(provider, "_metadata", lambda _identifier: sample_metadata())
    tracks = provider._tracks_for_identifier("example-item", 10)
    assert len(tracks) == 1
    assert tracks[0]["title"] == "First Track"
    assert tracks[0]["artist"] == "Example Artist"
    assert tracks[0]["year"] == 2001
    assert tracks[0]["source_page"].endswith("/example-item")
    assert tracks[0]["license_url"].startswith("https://creativecommons.org/")


def test_playback_resolve_uses_public_download_and_user_agent(monkeypatch):
    provider = load_provider()
    monkeypatch.setattr(provider, "_metadata", lambda _identifier: sample_metadata())
    track_id = "example-item::track01_vbr.mp3"
    resource = provider.resolve_playback(track_id)
    assert resource["url"] == "https://archive.org/download/example-item/track01_vbr.mp3"
    assert resource["headers"] == {}
    assert resource["mime_type"] == "audio/mpeg"


def test_restricted_item_returns_no_tracks(monkeypatch):
    provider = load_provider()
    data = sample_metadata()
    data["metadata"]["access-restricted-item"] = "true"
    monkeypatch.setattr(provider, "_metadata", lambda _identifier: data)
    assert provider._tracks_for_identifier("restricted", 10) == []
