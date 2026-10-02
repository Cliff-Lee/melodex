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


def test_openverse_resolves_media_redirect_before_playback(monkeypatch):
    monkeypatch.delenv("MELODEX_EXAMPLE_FIXTURES", raising=False)
    module = _load(
        "openverse_audio_redirect",
        EXAMPLES / "openverse_audio_provider" / "provider.py",
    )

    class FakeResponse:
        status_code = 206
        url = "https://cdn.example.net/final/audio.mp3"

        def raise_for_status(self):
            return None

        def close(self):
            return None

    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(module._SESSION, "get", fake_get)
    final = module._final_media_url(
        {"url": "https://source.example.org/media/audio"}
    )

    assert final == "https://cdn.example.net/final/audio.mp3"
    assert calls[0][1]["allow_redirects"] is True
    assert calls[0][1]["stream"] is True
    assert calls[0][1]["headers"]["Range"] == "bytes=0-0"


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


def test_sonic_neighbours_example_with_fixture():
    module = _load(
        "sonic_neighbours_example",
        EXAMPLES / "sonic_neighbours" / "plugin.py",
    )
    params = json.loads(
        (EXAMPLES / "sonic_neighbours" / "fixtures" / "request.json").read_text("utf-8")
    )
    result = module.suggest(params)
    assert result["intent"] == "similar"
    assert result["suggestions"][0]["ref"] == "t1"
    assert result["suggestions"][0]["score"] > result["suggestions"][-1]["score"]


def test_forgotten_favourites_example_with_fixture():
    module = _load(
        "forgotten_favourites_example",
        EXAMPLES / "forgotten_favourites" / "plugin.py",
    )
    params = json.loads(
        (EXAMPLES / "forgotten_favourites" / "fixtures" / "request.json").read_text("utf-8")
    )
    result = module.suggest(params)
    refs = [row["ref"] for row in result["suggestions"]]
    assert refs[0] == "t0"
    assert "t1" not in refs  # played yesterday
    assert "t3" not in refs  # explicitly disliked
    assert "days since last play" in result["suggestions"][0]["reason"]


def test_bridge_builder_example_with_fixture():
    module = _load(
        "bridge_builder_example",
        EXAMPLES / "bridge_builder" / "plugin.py",
    )
    params = json.loads(
        (EXAMPLES / "bridge_builder" / "fixtures" / "request.json").read_text("utf-8")
    )
    result = module.suggest(params)
    assert result["intent"] == "bridge"
    assert result["suggestions"][0]["ref"] == "t2"
    assert result["suggestions"][0]["score"] > 0.5


def test_musical_detours_example_with_fixture():
    module = _load(
        "musical_detours_example",
        EXAMPLES / "musical_detours" / "plugin.py",
    )
    params = json.loads(
        (EXAMPLES / "musical_detours" / "fixtures" / "request.json").read_text("utf-8")
    )
    result = module.suggest(params)
    rows = result["suggestions"]

    assert result["intent"] == "detour"
    assert [row["ref"] for row in rows] == ["t1", "t2"]
    assert rows[0]["reason"] == "Shares the pulse; moves away from energy and tone colour."
    assert rows[0]["badges"] == ["shared pulse", "new energy", "new tone"]
    assert "shared energy" in rows[1]["badges"]


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
        "org.melodex.example.sonic-neighbours",
        "org.melodex.example.forgotten-favourites",
        "org.melodex.example.bridge-builder",
        "org.melodex.example.musical-detours",
    }.issubset(ids)



def test_sonic_neighbours_preserves_explicit_zero_adventure(monkeypatch):
    module = _load(
        "sonic_neighbours_zero_adventure",
        EXAMPLES / "sonic_neighbours" / "plugin.py",
    )
    seen = []

    def fake_score(seed, candidate, adventure):
        seen.append(adventure)
        return 0.5, "ok", []

    monkeypatch.setattr(module, "_score", fake_score)
    result = module.suggest(
        {
            "intent": "similar",
            "adventure": 0.0,
            "limit": 1,
            "seed_refs": ["seed"],
            "tracks": [
                {"ref": "seed", "analysis": {"energy": 0.2}},
                {"ref": "candidate", "analysis": {"energy": 0.3}},
            ],
        }
    )
    assert result["suggestions"][0]["ref"] == "candidate"
    assert seen == [0.0]


def test_bridge_builder_preserves_explicit_zero_values(monkeypatch):
    module = _load(
        "bridge_builder_zero_values",
        EXAMPLES / "bridge_builder" / "plugin.py",
    )
    left = {
        "bpm": 100,
        "key_pc": 0,
        "key_mode": "minor",
        "energy": 0.4,
        "energy_end": 0.4,
        "spectral_centroid": 1000,
        "outro_mixability": 0.0,
    }
    right = {
        "bpm": 100,
        "key_pc": 0,
        "key_mode": "minor",
        "energy": 0.4,
        "energy_start": 0.4,
        "spectral_centroid": 1000,
        "intro_mixability": 0.0,
    }
    _score, dimensions = module._pair(left, right)
    assert dimensions["mix"] == 0.0

    seen = []

    def fake_score(start, candidate, end, adventure):
        seen.append(adventure)
        return 0.5, "ok", []

    monkeypatch.setattr(module, "_score", fake_score)
    module.suggest(
        {
            "intent": "bridge",
            "adventure": 0.0,
            "limit": 1,
            "seed_refs": ["a", "b"],
            "tracks": [
                {"ref": "a", "analysis": {}},
                {"ref": "b", "analysis": {}},
                {"ref": "c", "analysis": {}},
            ],
        }
    )
    assert seen == [0.0]


def test_wikimedia_artwork_clamps_zero_limit_and_skips_missing_url(monkeypatch):
    module = _load(
        "wikimedia_artwork_defensive",
        EXAMPLES / "wikimedia_artwork" / "plugin.py",
    )
    seen = {}

    def fake_get_json(params):
        seen.update(params)
        return {
            "query": {
                "pages": [
                    {"pageid": 1, "title": "Missing URL", "imageinfo": [{"extmetadata": {}}]},
                    {
                        "pageid": 2,
                        "title": "Good",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/example.jpg",
                                "width": 100,
                                "height": 100,
                                "mime": "image/jpeg",
                                "extmetadata": {},
                            }
                        ],
                    },
                ]
            }
        }

    monkeypatch.setattr(module, "_get_json", fake_get_json)
    result = module.artwork_lookup(
        {
            "subject": {"entity_type": "artist", "hints": {"name": "Demo"}},
            "max_results": 0,
        }
    )
    assert seen["gsrlimit"] == "1"
    assert [asset["url"] for asset in result["assets"]] == [
        "https://upload.wikimedia.org/example.jpg"
    ]


def test_wikimedia_liner_notes_rejects_invalid_wikidata_id_without_network(monkeypatch):
    module = _load(
        "wikimedia_liner_invalid_qid",
        EXAMPLES / "wikimedia_liner_notes" / "plugin.py",
    )

    def should_not_call(*args, **kwargs):
        raise AssertionError("network helper should not be called")

    monkeypatch.setattr(module, "_wikidata", should_not_call)
    result = module.context_lookup(
        {
            "subject": {
                "entity_type": "artist",
                "canonical_ids": {"wikidata_id": "../Q123"},
            }
        }
    )
    assert result["cards"] == []


def test_musicbrainz_identity_preserves_existing_canonical_ids(monkeypatch):
    module = _load(
        "musicbrainz_existing_ids",
        EXAMPLES / "musicbrainz_enrichment" / "plugin.py",
    )
    subject = {
        "entity_type": "track",
        "canonical_ids": {
            "musicbrainz_recording_id": "rec",
            "musicbrainz_artist_id": "artist",
            "musicbrainz_release_id": "release",
            "isrc": "ISRC123",
        },
        "hints": {"title": "Track", "artist": "Artist"},
    }
    result = module.identity_resolve({"subject": subject})
    ids = result["candidates"][0]["canonical_ids"]
    assert ids["musicbrainz_recording_id"] == "rec"
    assert ids["musicbrainz_artist_id"] == "artist"
    assert ids["musicbrainz_release_id"] == "release"
    assert ids["isrc"] == "ISRC123"


def test_musicbrainz_metadata_ignores_malformed_release_year(monkeypatch):
    module = _load(
        "musicbrainz_bad_date",
        EXAMPLES / "musicbrainz_enrichment" / "plugin.py",
    )
    monkeypatch.setattr(
        module,
        "_get_json",
        lambda *args, **kwargs: {
            "id": "rec",
            "title": "Track",
            "artist-credit": [{"name": "Artist"}],
            "releases": [{"title": "Album", "date": "????-01-01"}],
            "genres": [],
        },
    )
    result = module.metadata_enrich(
        {
            "subject": {
                "entity_type": "track",
                "canonical_ids": {"musicbrainz_recording_id": "rec"},
            }
        }
    )
    assert result["fields"]["title"]["value"] == "Track"
    assert "year" not in result["fields"]


def test_musicbrainz_search_clamps_explicit_zero_candidates(monkeypatch):
    module = _load(
        "musicbrainz_zero_limit",
        EXAMPLES / "musicbrainz_enrichment" / "plugin.py",
    )
    seen = {}

    def fake_get_json(path, params=None):
        seen.update(params or {})
        return {"recordings": []}

    monkeypatch.setattr(module, "_get_json", fake_get_json)
    module.identity_resolve(
        {
            "subject": {
                "entity_type": "track",
                "hints": {"title": "Track"},
            },
            "max_candidates": 0,
        }
    )
    assert seen["limit"] == 1


def test_listenbrainz_tags_accepts_list_shape_and_malformed_counts(monkeypatch):
    module = _load(
        "listenbrainz_tags_defensive",
        EXAMPLES / "listenbrainz_tags" / "plugin.py",
    )
    monkeypatch.setattr(
        module,
        "_get_json",
        lambda _mbid: [
            {
                "recording_mbid": "rec",
                "tag": {
                    "recording": [
                        {"tag": "trip hop", "count": "bad"},
                        {"tag": "ambient", "count": "4"},
                    ]
                },
            }
        ],
    )
    result = module.metadata_enrich(
        {
            "subject": {
                "entity_type": "track",
                "canonical_ids": {"musicbrainz_recording_id": "rec"},
            }
        }
    )
    counts = result["fields"]["community_tag_counts"]["value"]
    assert counts[0]["tag"] == "ambient"
    assert counts[0]["count"] == 4
    assert counts[1]["count"] == 0


def test_musicbrainz_connections_does_not_label_unrelated_place_as_recording_place(monkeypatch):
    module = _load(
        "musicbrainz_connections_places",
        EXAMPLES / "musicbrainz_connections" / "plugin.py",
    )
    monkeypatch.setattr(
        module,
        "_get_json",
        lambda _mbid: {
            "relations": [
                {
                    "type": "held at",
                    "direction": "forward",
                    "place": {"id": "venue", "name": "Concert Hall"},
                },
                {
                    "type": "recorded at",
                    "direction": "forward",
                    "place": {"id": "studio", "name": "Studio"},
                },
            ]
        },
    )
    result = module.context_lookup(
        {
            "subject": {
                "entity_type": "track",
                "canonical_ids": {"musicbrainz_recording_id": "rec"},
            }
        }
    )
    cards = {card["id"]: card for card in result["cards"]}
    assert [item["title"] for item in cards["recording-places"]["items"]] == ["Studio"]


def test_source_provider_health_checks_are_fixture_deterministic(monkeypatch):
    monkeypatch.setenv("MELODEX_EXAMPLE_FIXTURES", "1")
    cases = [
        ("radio_health", "radio_browser_provider"),
        ("openverse_health", "openverse_audio_provider"),
        ("librivox_health", "librivox_provider"),
        ("lastfm_health", "lastfm_recommendations_provider"),
    ]
    for module_name, folder in cases:
        module = _load(module_name, EXAMPLES / folder / "provider.py")
        health = module.respond({"method": "provider.health", "params": {}})
        assert health["status"] == "ready"


def test_source_provider_explicit_zero_search_limit_is_clamped(monkeypatch):
    monkeypatch.setenv("MELODEX_EXAMPLE_FIXTURES", "1")
    for module_name, folder in [
        ("radio_zero_limit", "radio_browser_provider"),
        ("openverse_zero_limit", "openverse_audio_provider"),
        ("librivox_zero_limit", "librivox_provider"),
    ]:
        module = _load(module_name, EXAMPLES / folder / "provider.py")
        result = module.respond(
            {"method": "catalog.search", "params": {"query": "demo", "limit": 0}}
        )
        assert 1 <= len(result["items"])
