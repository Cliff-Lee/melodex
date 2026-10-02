#!/usr/bin/env python3
"""Profile My Music catalog construction with a synthetic large library."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from melodex.library_browser import LibraryBrowser


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile LibraryBrowser with a synthetic Melodex catalog."
    )
    parser.add_argument("--tracks", type=int, default=12_700)
    parser.add_argument("--artists", type=int, default=600)
    parser.add_argument("--albums", type=int, default=1_200)
    parser.add_argument(
        "--view",
        choices=("albums", "artists", "tracks"),
        default="albums",
        help="Optional view to switch to after the initial album view is built.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def synthetic_catalog(
    *,
    tracks: int,
    artists: int,
    albums: int,
) -> list[dict[str, object]]:
    total = max(0, tracks)
    artist_count = max(1, artists)
    album_count = max(1, albums)
    rows: list[dict[str, object]] = []
    for index in range(total):
        artist_index = index % artist_count
        album_index = index % album_count
        rows.append(
            {
                "provider_id": "local",
                "track_id": f"/synthetic/track-{index:06d}.flac",
                "local_path": f"/synthetic/track-{index:06d}.flac",
                "artist": f"Artist {artist_index:04d}",
                "album_artist": f"Artist {artist_index:04d}",
                "album": f"Album {album_index:05d}",
                "title": f"Track {index:06d}",
                "track_number": (index % 20) + 1,
                "disc_number": 1,
                "year": 1980 + (album_index % 47),
                "genre": f"Genre {artist_index % 12}",
                "duration": 180.0 + (index % 180),
                "source": "local",
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    app = QApplication.instance() or QApplication([])
    browser = LibraryBrowser()
    browser.resize(1200, 800)
    browser.show()
    app.processEvents()

    catalog = synthetic_catalog(
        tracks=args.tracks,
        artists=args.artists,
        albums=args.albums,
    )

    started = time.perf_counter()
    browser.set_catalog(catalog)
    app.processEvents()
    initial_with_events = time.perf_counter() - started

    switch_seconds = 0.0
    if args.view != "albums":
        switch_started = time.perf_counter()
        browser.set_view(args.view)
        app.processEvents()
        switch_seconds = time.perf_counter() - switch_started

    payload = dict(browser.last_catalog_metrics)
    payload.update(
        {
            "requested_tracks": max(0, args.tracks),
            "requested_artists": max(1, args.artists),
            "requested_albums": max(1, args.albums),
            "initial_with_events_seconds": round(initial_with_events, 6),
            "selected_view": args.view,
            "view_switch_seconds": round(switch_seconds, 6),
            "album_widgets": len(browser.cards),
            "artist_widgets": len(browser.artist_cards),
            "track_widgets": len(browser.track_rows),
        }
    )

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Melodex synthetic My Music catalog probe")
        print("---------------------------------------")
        for key in (
            "requested_tracks",
            "track_count",
            "album_count",
            "artist_count",
            "reset_seconds",
            "copy_catalog_seconds",
            "album_model_seconds",
            "album_index_seconds",
            "artist_model_seconds",
            "initial_layout_seconds",
            "artwork_request_seconds",
            "total_seconds",
            "initial_with_events_seconds",
            "selected_view",
            "view_switch_seconds",
            "album_widgets",
            "artist_widgets",
            "track_widgets",
        ):
            print(f"{key:28} {payload.get(key)}")

    browser.close()
    browser.deleteLater()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
