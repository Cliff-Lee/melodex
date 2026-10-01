from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from melodex.album_wall_model import build_album_wall, layout_album_positions


def _track(path: str, artist: str, album: str, title: str, number: int, year: int = 2000):
    return {
        "provider_id": "local",
        "track_id": path,
        "local_path": path,
        "artist": artist,
        "album": album,
        "title": title,
        "track_number": number,
        "year": year,
    }


def test_album_wall_groups_tracks_and_uses_music_map_centroid():
    catalog = [
        _track("/a/01.mp3", "Example", "First", "One", 1, 1998),
        _track("/a/02.mp3", "Example", "First", "Two", 2, 1998),
        _track("/b/01.mp3", "Elsewhere", "Second", "Three", 1, 2004),
    ]
    model = {
        "nodes": [
            {"ref": "r1", "x": -0.8, "y": 0.2, "taste": 0.8, "rediscovery": 0.1, "plays": 5},
            {"ref": "r2", "x": -0.4, "y": 0.4, "taste": 0.6, "rediscovery": 0.5, "plays": 3},
        ]
    }
    ref_map = {"r1": catalog[0], "r2": catalog[1]}
    wall = build_album_wall(catalog, model, ref_map)
    albums = {a["title"]: a for a in wall["albums"]}

    first = albums["First"]
    assert first["track_count"] == 2
    assert [t["title"] for t in first["tracks"]] == ["One", "Two"]
    assert round(first["sound_x"], 3) == -0.6
    assert round(first["sound_y"], 3) == 0.3
    assert round(first["familiarity"], 3) == 0.7
    assert first["rediscovery"] == 0.5
    assert first["year"] == 1998

    second = albums["Second"]
    assert second["analysed_tracks"] == 0
    assert -1.0 <= second["fallback_x"] <= 1.0
    assert -1.0 <= second["fallback_y"] <= 1.0


def test_unanalysed_album_positions_are_stable():
    catalog = [
        _track("/a/01.mp3", "Example", "First", "One", 1),
        _track("/b/01.mp3", "Elsewhere", "Second", "Two", 1),
    ]
    first = build_album_wall(catalog)
    second = build_album_wall(catalog)
    first_xy = [(a["key"], a["fallback_x"], a["fallback_y"]) for a in first["albums"]]
    second_xy = [(a["key"], a["fallback_x"], a["fallback_y"]) for a in second["albums"]]
    assert first_xy == second_xy


def test_album_wall_layout_has_no_tile_collisions_across_lenses():
    catalog = [
        _track(f"/music/{i:03}.mp3", f"Artist {i:03}", f"Album {i:03}", "Track", 1, 1970 + i % 50)
        for i in range(140)
    ]
    wall = build_album_wall(catalog)
    for lens in ("sound", "familiarity", "time", "shelves"):
        positions = layout_album_positions(wall, lens)
        assert len(positions) == 140
        assert len(set(positions.values())) == 140
