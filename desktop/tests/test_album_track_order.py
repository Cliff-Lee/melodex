from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from melodex.album_track_order import album_order_diagnostics, album_track_order_key


def test_single_disc_order_accepts_slash_totals_and_missing_disc_tags():
    tracks = [
        {"title": "Twelve", "track_number": "12/12"},
        {"title": "Two", "track_number": 2},
        {"title": "One", "tracknumber": "1/12"},
    ]

    ordered = sorted(tracks, key=album_track_order_key)

    assert [track["title"] for track in ordered] == ["One", "Two", "Twelve"]
    summary = album_order_diagnostics(ordered)
    assert summary["track_count"] == 3
    assert summary["disc_numbered_tracks"] == 0
    assert summary["track_numbered_tracks"] == 3
    assert summary["ordering_valid"] is True


def test_multi_disc_order_is_disc_then_track_not_input_or_title_order():
    tracks = [
        {"title": "Disc two first", "disc_number": "2/2", "track_number": "1/8"},
        {"title": "Disc one second", "disc_number": 1, "track_number": 2},
        {"title": "Disc one first", "discnumber": "1/2", "tracknumber": "1/8"},
        {"title": "Disc two second", "disc_number": 2, "track_number": 2},
    ]

    ordered = sorted(tracks, key=album_track_order_key)

    assert [track["title"] for track in ordered] == [
        "Disc one first",
        "Disc one second",
        "Disc two first",
        "Disc two second",
    ]
    summary = album_order_diagnostics(ordered)
    assert summary["disc_numbered_tracks"] == 4
    assert summary["track_numbered_tracks"] == 4
    assert summary["ordering_valid"] is True


def test_missing_numbers_sort_after_tagged_tracks_and_are_not_reported_valid():
    tracks = [
        {"title": "Missing"},
        {"title": "Two", "track_number": 2},
        {"title": "One", "track_number": 1},
    ]

    ordered = sorted(tracks, key=album_track_order_key)

    assert [track["title"] for track in ordered] == ["One", "Two", "Missing"]
    summary = album_order_diagnostics(ordered)
    assert summary["track_numbered_tracks"] == 2
    assert summary["ordering_valid"] is False


def test_malformed_and_duplicate_tags_are_safe_and_invalid():
    tracks = [
        {"title": "Malformed", "disc_number": "side B", "track_number": "A1"},
        {"title": "Duplicate one", "disc_number": 1, "track_number": 1},
        {"title": "Duplicate two", "disc_number": "1/2", "track_number": "01/10"},
        {"title": "Valid next", "disc_number": 1, "track_number": 2},
    ]

    ordered = sorted(tracks, key=album_track_order_key)
    summary = album_order_diagnostics(ordered)

    assert [track["title"] for track in ordered][-1] == "Malformed"
    assert summary["malformed_disc_numbers"] == 1
    assert summary["malformed_track_numbers"] == 1
    assert summary["duplicate_positions"] == 1
    assert summary["ordering_valid"] is False
