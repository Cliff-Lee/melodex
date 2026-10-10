from __future__ import annotations

from melodex.music_map_region import local_tracks_for_region


def _key(track: dict[str, object]) -> str:
    return str(track.get("local_path") or track.get("track_id") or "")


def test_region_session_restricts_candidates_to_actual_local_members():
    mapped = [
        {"local_path": "/music/a.flac", "artist": "Shared Artist"},
        {"local_path": "/music/b.flac", "artist": "Second Artist"},
        {"local_path": "/music/a.flac", "artist": "Duplicate"},
    ]
    catalogue = [
        {"local_path": "/music/other.flac", "artist": "Shared Artist"},
        {"local_path": "/music/a.flac", "artist": "Shared Artist"},
        {"local_path": "/music/b.flac", "artist": "Second Artist"},
        {"local_path": "/music/a.flac", "artist": "Duplicate"},
        {"artist": "Unknown", "title": "No local file"},
    ]
    chosen = local_tracks_for_region(mapped, catalogue, _key)
    assert [row["local_path"] for row in chosen] == [
        "/music/a.flac", "/music/b.flac",
    ]
    assert "/music/other.flac" not in [row["local_path"] for row in chosen]
    assert local_tracks_for_region(mapped, catalogue, _key, max_tracks=1) == chosen[:1]


def test_region_session_does_not_guess_missing_or_stale_music():
    assert local_tracks_for_region(
        [{"artist": "A", "title": "Song"}],
        [{"local_path": "/library/song.flac", "artist": "A", "title": "Song"}],
        _key,
    ) == []
    assert local_tracks_for_region(
        [{"local_path": "/old/path.flac"}],
        [{"local_path": "/new/path.flac"}],
        _key,
    ) == []
    assert local_tracks_for_region(
        [{"local_path": "/a.flac"}],
        [{"artist": "A", "title": "A"}],
        _key,
    ) == []


def test_region_filter_preserves_catalogue_order_and_limits_output():
    mapped = [{"local_path": f"/music/{i}.flac"} for i in range(20)]
    catalogue = list(reversed(mapped))
    out = local_tracks_for_region(mapped, catalogue, _key, max_tracks=6)
    assert [row["local_path"] for row in out] == [
        f"/music/{i}.flac" for i in range(19, 13, -1)
    ]
