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


def test_album_wall_groups_mixed_artists_by_local_album_folder():
    catalog = [
        _track("/compilation/01.mp3", "Artist A", "Shared Album", "One", 1, 2005),
        _track("/compilation/02.mp3", "Artist B", "Shared Album", "Two", 2, 2005),
        _track("/other/01.mp3", "Artist C", "Shared Album", "Three", 1, 2005),
    ]
    wall = build_album_wall(catalog)
    assert wall["album_count"] == 2
    compilation = next(a for a in wall["albums"] if a["track_count"] == 2)
    assert compilation["artist"] == "Various Artists"
    assert [t["title"] for t in compilation["tracks"]] == ["One", "Two"]



def test_album_wall_keeps_separate_local_editions_of_same_album():
    catalog = [
        {
            **_track("/library/original/01.mp3", "Artist", "Same Album", "One", 1, 1999),
            "album_artist": "Artist",
        },
        {
            **_track("/library/remaster/01.mp3", "Artist", "Same Album", "One", 1, 2009),
            "album_artist": "Artist",
        },
    ]
    wall = build_album_wall(catalog)
    assert wall["album_count"] == 2


def test_album_wall_collapses_common_multidisc_subfolders():
    catalog = [
        {
            **_track("/library/Box Set/CD1/01.mp3", "Artist", "Box Set", "Disc One", 1, 2010),
            "album_artist": "Artist",
            "disc_number": 1,
        },
        {
            **_track("/library/Box Set/Disc 2/01.mp3", "Artist", "Box Set", "Disc Two", 1, 2010),
            "album_artist": "Artist",
            "disc_number": 2,
        },
    ]
    wall = build_album_wall(catalog)
    assert wall["album_count"] == 1
    album = wall["albums"][0]
    assert album["track_count"] == 2
    assert [t["title"] for t in album["tracks"]] == ["Disc One", "Disc Two"]


def test_time_lens_orders_undated_after_dated():
    catalog = [
        _track('/dated1/01.mp3', 'A', 'Old', 'One', 1, 1980),
        _track('/dated2/01.mp3', 'B', 'New', 'Two', 1, 2020),
        {**_track('/undated/01.mp3', 'C', 'Mystery', 'Three', 1, 2000), 'year': 0},
    ]
    wall = build_album_wall(catalog)
    for album in wall['albums']:
        if album['title'] == 'Mystery':
            album['year'] = 0
    positions = layout_album_positions(wall, 'time')
    by_title = {album['title']: positions[album['key']] for album in wall['albums']}
    assert by_title['Old'][0] <= by_title['New'][0]
    assert by_title['Mystery'][0] > max(by_title['Old'][0], by_title['New'][0])


def test_sound_layout_is_compact_for_medium_library():
    catalog = [
        _track(f'/music/{i}/01.mp3', f'Artist {i}', f'Album {i}', 'Track', 1, 2000 + i % 20)
        for i in range(75)
    ]
    wall = build_album_wall(catalog)
    positions = layout_album_positions(wall, 'sound')
    xs = [x for x, _ in positions.values()]
    ys = [y for _, y in positions.values()]
    assert max(xs) - min(xs) < 2400
    assert max(ys) - min(ys) < 1800


def test_album_wall_merges_obvious_tribute_compilation_across_artist_folders():
    catalog = [
        _track("/artists/A/01.mp3", "Artist A", "Electronic Love - A Tribute to Depeche Mode", "One", 1, 2008),
        _track("/artists/B/02.mp3", "Artist B", "Electronic Love - A Tribute to Depeche Mode", "Two", 2, 2008),
        _track("/artists/C/03.mp3", "Artist C", "Electronic Love - A Tribute to Depeche Mode", "Three", 3, 2008),
    ]
    wall = build_album_wall(catalog)
    assert wall["album_count"] == 1
    album = wall["albums"][0]
    assert album["artist"] == "Various Artists"
    assert album["track_count"] == 3
    assert [t["title"] for t in album["tracks"]] == ["One", "Two", "Three"]


def test_album_artist_metadata_groups_same_release_but_year_keeps_editions_separate():
    catalog = [
        {
            **_track("/one/01.mp3", "Guest A", "Shared Release", "One", 1, 2001),
            "album_artist": "Main Artist",
        },
        {
            **_track("/two/02.mp3", "Guest B", "Shared Release", "Two", 2, 2001),
            "album_artist": "Main Artist",
        },
        {
            **_track("/remaster/01.mp3", "Main Artist", "Shared Release", "One", 1, 2015),
            "album_artist": "Main Artist",
        },
    ]
    wall = build_album_wall(catalog)
    assert wall["album_count"] == 2
    original = next(a for a in wall["albums"] if a["year"] == 2001)
    remaster = next(a for a in wall["albums"] if a["year"] == 2015)
    assert original["track_count"] == 2
    assert remaster["track_count"] == 1
