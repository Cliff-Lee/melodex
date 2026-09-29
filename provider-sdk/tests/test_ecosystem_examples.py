from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "ecosystem"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_radio_browser_example_with_fixture(monkeypatch):
    monkeypatch.setenv("MELODEX_EXAMPLE_FIXTURES", "1")
    module = _load("radio_browser_example", EXAMPLES / "radio_browser_provider" / "provider.py")
    result = module.respond({"method": "catalog.search", "params": {"query": "jazz", "limit": 3}})
    assert result["items"][0]["title"] == "Demo Jazz Radio"
    track_id = result["items"][0]["provider_track_id"]
    play = module.respond({"method": "playback.resolve", "params": {"provider_track_id": track_id}})
    assert play["url"].endswith("jazz.mp3")
    assert play["seekable"] is False


def test_librivox_example_with_fixture(monkeypatch):
    monkeypatch.setenv("MELODEX_EXAMPLE_FIXTURES", "1")
    module = _load("librivox_example", EXAMPLES / "librivox_provider" / "provider.py")
    result = module.respond({"method": "catalog.search", "params": {"query": "Odyssey", "limit": 3}})
    assert len(result["items"]) == 2
    track_id = result["items"][0]["provider_track_id"]
    play = module.respond(
        {"method": "playback.resolve", "params": {"provider_track_id": track_id, "purpose": "offline"}}
    )
    assert play["cache_policy"] == "offline_allowed"
    assert play["url"].endswith(".mp3")


def test_musicbrainz_enrichment_with_fixture(monkeypatch):
    monkeypatch.setenv("MELODEX_EXAMPLE_FIXTURES", "1")
    module = _load("musicbrainz_example", EXAMPLES / "musicbrainz_enrichment" / "plugin.py")
    subject = {
        "entity_type": "track",
        "hints": {"title": "Night Signals", "artist": "Demo Artist", "duration_ms": 241000},
    }
    identity = module.identity_resolve({"subject": subject, "max_candidates": 5})
    assert identity["status"] == "matched"
    mbid = identity["candidates"][0]["canonical_ids"]["musicbrainz_recording_id"]
    metadata = module.metadata_enrich(
        {"subject": {"entity_type": "track", "canonical_ids": {"musicbrainz_recording_id": mbid}}}
    )
    assert metadata["fields"]["title"]["value"] == "Night Signals"
    assert metadata["fields"]["title"]["provenance"]["source_extension_id"]


def test_wikimedia_artwork_with_fixture(monkeypatch):
    monkeypatch.setenv("MELODEX_EXAMPLE_FIXTURES", "1")
    module = _load("wikimedia_example", EXAMPLES / "wikimedia_artwork" / "plugin.py")
    result = module.artwork_lookup(
        {"subject": {"entity_type": "artist", "hints": {"name": "Demo Artist"}}, "max_results": 5}
    )
    asset = result["assets"][0]
    assert asset["role"] == "portrait"
    assert "CC BY-SA" in (asset["provenance"]["license"] or "")
    assert asset["provenance"]["attribution"]



def test_openverse_audio_example_with_fixture(monkeypatch):
    monkeypatch.setenv("MELODEX_EXAMPLE_FIXTURES", "1")
    module = _load("openverse_audio_example", EXAMPLES / "openverse_audio_provider" / "provider.py")
    result = module.respond(
        {"method": "catalog.search", "params": {"query": "ambient", "limit": 3}}
    )
    track = result["items"][0]
    assert track["title"] == "Example Open Track"
    assert track["metadata"]["license"] == "BY 4.0"
    play = module.respond(
        {"method": "playback.resolve", "params": {"provider_track_id": track["provider_track_id"]}}
    )
    assert play["url"].endswith(".mp3")
    assert play["seekable"] is True


def test_cover_art_archive_example_with_fixture(monkeypatch):
    monkeypatch.setenv("MELODEX_EXAMPLE_FIXTURES", "1")
    module = _load(
        "cover_art_archive_example",
        EXAMPLES / "cover_art_archive_artwork" / "plugin.py",
    )
    subject = {
        "entity_type": "album",
        "canonical_ids": {
            "musicbrainz_release_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        },
    }
    result = module.artwork_lookup({"subject": subject, "max_results": 5})
    asset = result["assets"][0]
    assert asset["role"] == "cover"
    assert "archive.org" in asset["url"]
    assert asset["provenance"]["source_extension_id"] == "org.melodex.example.cover-art-archive"


def test_listenbrainz_tags_example_with_fixture(monkeypatch):
    monkeypatch.setenv("MELODEX_EXAMPLE_FIXTURES", "1")
    module = _load("listenbrainz_tags_example", EXAMPLES / "listenbrainz_tags" / "plugin.py")
    subject = {
        "entity_type": "track",
        "canonical_ids": {
            "musicbrainz_recording_id": "e97f805a-ab48-4c52-855e-07049142113d"
        },
    }
    result = module.metadata_enrich({"subject": subject})
    assert result["fields"]["community_tags"]["value"][0] == "trip hop"
    assert result["fields"]["community_tag_counts"]["value"][0]["count"] == 8
    health = module.respond({"method": "extension.health", "params": {"schema_version": "0.1", "check": "live"}})
    assert health["status"] == "ready"
    assert health["upstream_checked"] is True

def test_public_domain_lyrics_example():
    module = _load(
        "public_domain_lyrics_example",
        EXAMPLES / "public_domain_lyrics" / "plugin.py",
    )
    subject = {
        "entity_type": "track",
        "hints": {"title": "Auld Lang Syne", "artist": "Traditional"},
    }
    result = module.lyrics_lookup({"subject": subject})
    assert result["entries"][0]["kind"] == "plain"
    assert "auld acquaintance" in result["entries"][0]["text"].casefold()
    assert result["entries"][0]["provenance"]["source_extension_id"] == (
        "org.melodex.example.public-domain-lyrics"
    )
    synced_only = module.lyrics_lookup(
        {"subject": subject, "kinds": ["synchronized"]}
    )
    assert synced_only["entries"] == []


def test_lastfm_recommendations_example_with_fixture(monkeypatch):
    monkeypatch.setenv("MELODEX_EXAMPLE_FIXTURES", "1")
    module = _load(
        "lastfm_recommendations_example",
        EXAMPLES / "lastfm_recommendations_provider" / "provider.py",
    )
    result = module.respond(
        {
            "method": "recommendations.get",
            "params": {
                "seed": {"artist": "Massive Attack", "title": "Teardrop"},
                "limit": 5,
            },
        }
    )
    assert result["items"][0]["title"] == "Roads"
    assert result["items"][0]["artist"] == "Portishead"
    assert result["items"][0]["metadata"]["playable"] is False
    health = module.respond({"method": "provider.health", "params": {}})
    assert health["status"] == "ready"


def test_musicbrainz_connections_example_with_fixture(monkeypatch):
    monkeypatch.setenv("MELODEX_EXAMPLE_FIXTURES", "1")
    module = _load(
        "musicbrainz_connections_example",
        EXAMPLES / "musicbrainz_connections" / "plugin.py",
    )
    subject = {
        "entity_type": "track",
        "canonical_ids": {"musicbrainz_recording_id": "demo-recording"},
    }
    result = module.context_lookup({"subject": subject})
    cards = {card["id"]: card for card in result["cards"]}
    assert cards["song-connections"]["items"][0]["badge"] == "sample"
    assert any(
        item["badge"] == "remix"
        for item in cards["song-connections"]["items"]
    )
    assert cards["recording-places"]["items"][0]["title"] == "Example Studio"


def test_wikimedia_liner_notes_example_with_fixture(monkeypatch):
    monkeypatch.setenv("MELODEX_EXAMPLE_FIXTURES", "1")
    module = _load(
        "wikimedia_liner_notes_example",
        EXAMPLES / "wikimedia_liner_notes" / "plugin.py",
    )
    subject = {
        "entity_type": "track",
        "canonical_ids": {"wikidata_id": "Q123"},
    }
    result = module.context_lookup({"subject": subject})
    card = result["cards"][0]
    assert card["id"] == "liner-note"
    assert "fictional musician" in card["text"]
    assert "CC BY-SA" in card["provenance"]["license"]
    assert "wikipedia.org" in card["provenance"]["source_url"]


def test_listenbrainz_community_pulse_example_with_fixture(monkeypatch):
    monkeypatch.setenv("MELODEX_EXAMPLE_FIXTURES", "1")
    module = _load(
        "listenbrainz_community_pulse_example",
        EXAMPLES / "listenbrainz_community_pulse" / "plugin.py",
    )
    subject = {
        "entity_type": "track",
        "canonical_ids": {
            "musicbrainz_recording_id": "demo-recording",
            "musicbrainz_artist_id": "demo-artist",
        },
    }
    result = module.context_lookup({"subject": subject})
    cards = {card["id"]: card for card in result["cards"]}
    facts = {row["label"]: row["value"] for row in cards["community-pulse"]["facts"]}
    assert facts["Listens"] == 128450
    assert facts["Listeners"] == 7421
    assert cards["artist-popular-recordings"]["items"][0]["title"] == "Night Signal"
    health = module.respond(
        {
            "method": "extension.health",
            "params": {"schema_version": "0.1", "check": "live"},
        }
    )
    assert health["status"] == "ready"
    assert health["upstream_checked"] is True


def test_registry_references_all_examples():
    registry = json.loads((ROOT / "registry" / "example-registry.json").read_text(encoding="utf-8"))
    ids = {row["id"] for row in registry["plugins"]}
    assert {
        "org.melodex.example.radio-browser",
        "org.melodex.example.librivox",
        "org.melodex.example.musicbrainz",
        "org.melodex.example.wikimedia-commons",
        "org.melodex.example.openverse-audio",
        "org.melodex.example.cover-art-archive",
        "org.melodex.example.listenbrainz-tags",
        "org.melodex.example.public-domain-lyrics",
        "org.melodex.example.lastfm-recommendations",
        "org.melodex.example.musicbrainz-connections",
        "org.melodex.example.wikimedia-liner-notes",
        "org.melodex.example.listenbrainz-community-pulse",
    }.issubset(ids)
