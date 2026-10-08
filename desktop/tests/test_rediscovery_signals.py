from __future__ import annotations

import pytest

from melodex.mind import MindEngine
from melodex.rediscovery_signals import build_rediscovery_signals
from melodex.user_state import UserState


def _album_track(number: int, *, artist: str = "Northbound", album: str = "Night Drive"):
    return {
        "provider_id": "local",
        "track_id": f"{artist}-{album}-{number}",
        "rel": f"local:{artist}/{album}/{number}",
        "artist": artist,
        "album_artist": artist,
        "album": album,
        "year": 2024,
        "title": f"Track {number}",
        "track_no": f"{number}/8",
    }


def test_fresh_install_uses_album_position_as_a_rediscovery_signal():
    catalog = [_album_track(number) for number in range(1, 9)]
    signals = build_rediscovery_signals(catalog, {})
    opener = signals[UserState.track_key(catalog[0])]
    deep_cut = signals[UserState.track_key(catalog[-1])]

    assert opener["album_track_count"] == 8
    assert opener["album_played_tracks"] == 0
    assert opener["library_score"] == pytest.approx(0.32)
    assert deep_cut["deep_cut"] == 1.0
    assert deep_cut["library_score"] > opener["library_score"]
    assert deep_cut["reason"] == "deep cut in your library"


def test_history_connects_unplayed_catalog_tracks_to_a_known_artist():
    known_track = _album_track(1, album="Older Album")
    current_album = [_album_track(number, album="New Album") for number in range(1, 5)]
    history = {
        UserState.track_key(known_track): {
            "artist": "Northbound",
            "plays": 7,
        }
    }

    signals = build_rediscovery_signals(current_album, history)
    candidate = signals[UserState.track_key(current_album[-1])]

    assert candidate["artist_familiarity"] > 0.0
    assert candidate["artist_played_tracks"] == 1
    assert candidate["reason"] == "unplayed track from an artist you know"


def test_metadata_sparse_catalog_keeps_a_neutral_fallback():
    track = {
        "provider_id": "local",
        "track_id": "unknown-1",
        "rel": "local:unknown-1",
        "artist": "Unknown",
        "title": "Untitled",
        "track_no": "sideways",
    }

    signal = build_rediscovery_signals([track], {})[UserState.track_key(track)]

    assert signal["library_score"] == 0.0
    assert signal["reason"] == ""


def test_rediscover_mode_uses_metadata_fallback_without_play_history():
    track = _album_track(8)
    mind = MindEngine(None, None)

    score, reason = mind.score(
        track,
        {},
        "rediscover",
        0.35,
        1_800_000_000.0,
        {},
        {
            "library_score": 0.8,
            "reason": "deep cut in your library",
        },
    )

    assert score == pytest.approx(0.6)
    assert reason == "deep cut in your library"
