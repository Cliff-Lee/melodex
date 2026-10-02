from __future__ import annotations

import argparse
import gc
import json
import math
import os
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
if str(DESKTOP) not in sys.path:
    sys.path.insert(0, str(DESKTOP))

from melodex.album_wall_model import build_album_wall  # noqa: E402


DEFAULT_PROFILES = (1_000, 12_700, 50_000, 100_000)


def synthetic_catalog(
    track_count: int,
    *,
    tracks_per_album: int = 10,
    albums_per_artist: int = 4,
) -> list[dict[str, Any]]:
    """Build a deterministic local-style catalog without touching audio files."""
    track_count = max(0, int(track_count))
    tracks_per_album = max(1, int(tracks_per_album))
    albums_per_artist = max(1, int(albums_per_artist))

    catalog: list[dict[str, Any]] = []
    for index in range(track_count):
        album_index = index // tracks_per_album
        artist_index = album_index // albums_per_artist
        track_number = index % tracks_per_album + 1
        year = 1960 + (album_index % 67)
        artist = f"Artist {artist_index:05d}"
        album = f"Album {album_index:06d}"
        title = f"Track {track_number:02d}"
        path = f"/synthetic/{artist_index:05d}/{album_index:06d}/{track_number:02d}.flac"
        catalog.append(
            {
                "provider_id": "local",
                "track_id": path,
                "local_path": path,
                "artist": artist,
                "album_artist": artist,
                "album": album,
                "title": title,
                "track_number": track_number,
                "disc_number": 1,
                "year": year,
                "genre": f"Genre {artist_index % 12:02d}",
            }
        )
    return catalog


def expected_shape(
    track_count: int,
    *,
    tracks_per_album: int = 10,
    albums_per_artist: int = 4,
) -> dict[str, int]:
    tracks = max(0, int(track_count))
    tracks_per_album = max(1, int(tracks_per_album))
    albums_per_artist = max(1, int(albums_per_artist))
    albums = int(math.ceil(tracks / tracks_per_album)) if tracks else 0
    artists = int(math.ceil(albums / albums_per_artist)) if albums else 0
    return {
        "tracks": tracks,
        "albums": albums,
        "artists": artists,
    }


def profile_model(
    track_count: int,
    *,
    tracks_per_album: int = 10,
    albums_per_artist: int = 4,
    model_limit: int = 4000,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    shape = expected_shape(
        track_count,
        tracks_per_album=tracks_per_album,
        albums_per_artist=albums_per_artist,
    )
    tracemalloc.start()
    generate_started = time.perf_counter()
    catalog = synthetic_catalog(
        track_count,
        tracks_per_album=tracks_per_album,
        albums_per_artist=albums_per_artist,
    )
    generate_seconds = time.perf_counter() - generate_started

    model_started = time.perf_counter()
    model = build_album_wall(catalog, max_albums=model_limit)
    model_seconds = time.perf_counter() - model_started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    retained_tracks = int(model.get("track_count") or 0)
    result = {
        "profile_tracks": int(track_count),
        "expected_album_count": shape["albums"],
        "expected_artist_count": shape["artists"],
        "tracks_per_album": int(tracks_per_album),
        "albums_per_artist": int(albums_per_artist),
        "model_limit": int(model_limit),
        "generate_seconds": round(generate_seconds, 6),
        "album_model_seconds": round(model_seconds, 6),
        "python_peak_mib": round(peak / (1024 * 1024), 3),
        "modeled_album_count": int(model.get("album_count") or 0),
        "input_album_count": int(model.get("input_album_count") or 0),
        "albums_truncated": int(model.get("albums_truncated") or 0),
        "retained_track_count": retained_tracks,
        "tracks_truncated": int(model.get("tracks_truncated") or 0),
        "retained_track_ratio": (
            round(retained_tracks / track_count, 6) if track_count else 1.0
        ),
    }
    return result, catalog


def profile_gui(
    catalog: list[dict[str, Any]],
    *,
    revision: int,
) -> dict[str, Any]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.library_browser import LibraryBrowser
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
        }

    app = QApplication.instance() or QApplication([])
    browser = LibraryBrowser()
    browser.resize(1200, 800)
    browser.show()

    started = time.perf_counter()
    browser.set_catalog(catalog, revision=revision)
    app.processEvents()
    catalog_seconds = time.perf_counter() - started

    filter_query = ""
    if catalog:
        last = catalog[-1]
        filter_query = str(last.get("album") or last.get("title") or "")
    if filter_query:
        browser.search.setText(filter_query)
        app.processEvents()
    filter_metrics = dict(browser.last_filter_metrics)

    browser.search.clear()
    app.processEvents()
    browser.set_view("artists")
    app.processEvents()
    artist_view_metrics = dict(browser.last_view_metrics)
    artist_filter_metrics = dict(browser.last_filter_metrics)

    browser.set_view("tracks")
    app.processEvents()
    track_view_metrics = dict(browser.last_view_metrics)
    track_filter_metrics = dict(browser.last_filter_metrics)

    metrics = {
        "available": True,
        "catalog_wall_seconds": round(catalog_seconds, 6),
        "catalog": dict(browser.last_catalog_metrics),
        "last_filter": filter_metrics,
        "artist_view": artist_view_metrics,
        "artist_filter": artist_filter_metrics,
        "track_view": track_view_metrics,
        "track_filter": track_filter_metrics,
        "track_virtualization": dict(browser.last_track_virtualization_metrics),
        "artwork_priority": dict(browser.last_artwork_priority_metrics),
        "album_batch_size": int(browser._album_batch_size),
        "artist_batch_size": int(browser._artist_batch_size),
        "track_row_height": int(browser._track_row_height),
        "track_overscan_rows": int(browser._track_overscan_rows),
    }

    browser.deleteLater()
    app.processEvents()
    return metrics


def run_profiles(
    profiles: list[int] | tuple[int, ...],
    *,
    tracks_per_album: int = 10,
    albums_per_artist: int = 4,
    model_limit: int = 4000,
    gui: bool = False,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for track_count in profiles:
        row, catalog = profile_model(
            int(track_count),
            tracks_per_album=tracks_per_album,
            albums_per_artist=albums_per_artist,
            model_limit=model_limit,
        )
        if gui:
            row["gui"] = profile_gui(catalog, revision=int(track_count))
        output.append(row)
        del catalog
        gc.collect()
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate deterministic synthetic Melodex libraries and measure "
            "model/render scaling without requiring real music files."
        )
    )
    parser.add_argument(
        "--tracks",
        type=int,
        nargs="+",
        default=list(DEFAULT_PROFILES),
        help="Synthetic track counts to profile.",
    )
    parser.add_argument("--tracks-per-album", type=int, default=10)
    parser.add_argument("--albums-per-artist", type=int, default=4)
    parser.add_argument(
        "--model-limit",
        type=int,
        default=4000,
        help="Album-model limit to mirror the current My Music path.",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Also instantiate LibraryBrowser and measure filter/view costs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output file. JSON is always printed to stdout.",
    )
    args = parser.parse_args()

    result = {
        "schema": 1,
        "profiles": run_profiles(
            args.tracks,
            tracks_per_album=args.tracks_per_album,
            albums_per_artist=args.albums_per_artist,
            model_limit=args.model_limit,
            gui=args.gui,
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
