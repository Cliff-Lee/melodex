#!/usr/bin/env python3
"""Qualify cold-start queue quality without reading media or requiring Qt."""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from melodex.first_play_policy import light_shuffle  # noqa: E402


def _track(index: int, artist: str, album: str, *, title: str | None = None) -> dict[str, Any]:
    return {
        "track_id": f"/synthetic/{index:06d}.flac",
        "local_path": f"/synthetic/{index:06d}.flac",
        "artist": artist,
        "album": album,
        "title": title or f"Track {index}",
    }


def quality_profiles() -> dict[str, list[dict[str, Any]]]:
    return {
        "one_track": [_track(0, "Artist A", "Album A")],
        "small_mixed": [
            _track(i, f"Artist {i % 5}", f"Album {i % 5}")
            for i in range(10)
        ],
        "duplicate_heavy": [
            _track(i, f"Artist {i % 3}", f"Album {i % 2}", title="Same title")
            for i in range(80)
        ],
        "badly_tagged": [
            _track(
                i,
                "Unknown artist" if i % 3 else f"Artist {i % 6}",
                "" if i % 2 else f"Album {i % 10}",
            )
            for i in range(80)
        ],
        "single_artist": [
            _track(i, "One Artist", f"Album {i % 6}") for i in range(40)
        ],
        # Interleaved records model breadth-first discovery across directories.
        "broad_interleaved": [
            _track(i, f"Artist {i % 12}", f"Album {i % 12}-{i // 12}")
            for i in range(120)
        ],
        # A clustered source checks that a short local window stays local.
        "artist_clustered": [
            _track(i, f"Artist {i // 8}", f"Album {i // 2}")
            for i in range(160)
        ],
    }


def _known(value: object, unknown: set[str]) -> str:
    normalized = str(value or "").strip().casefold()
    return "" if normalized in unknown else normalized


def qualify(*, seeds: int = 32, window_size: int = 5) -> dict[str, Any]:
    if seeds < 1:
        raise ValueError("seeds must be positive")
    profiles = quality_profiles()
    reports: list[dict[str, Any]] = []
    all_preserved = True

    for name, tracks in profiles.items():
        artist_coverage: list[int] = []
        album_coverage: list[int] = []
        first_five_last_index: list[int] = []
        preserved = True
        positions = {
            str(track["track_id"]): index
            for index, track in enumerate(tracks)
        }
        for seed in range(seeds):
            queue = light_shuffle(
                tracks,
                rng=random.Random(seed),
                window_size=window_size,
            )
            queue_ids = [str(track.get("track_id") or "") for track in queue]
            if len(queue_ids) != len(tracks) or sorted(queue_ids) != sorted(positions):
                preserved = False
            first_five = queue[:5]
            artist_coverage.append(
                len(
                    {
                        value
                        for track in first_five
                        if (value := _known(
                            track.get("artist"),
                            {"unknown", "unknown artist"},
                        ))
                    }
                )
            )
            album_coverage.append(
                len(
                    {
                        value
                        for track in first_five
                        if (value := _known(
                            track.get("album"), {"unknown", "unknown album"}
                        ))
                    }
                )
            )
            first_five_last_index.append(
                max((positions.get(track_id, 0) for track_id in queue_ids[:5]), default=0)
            )
        all_preserved = all_preserved and preserved
        reports.append(
            {
                "profile": name,
                "pool_tracks": len(tracks),
                "all_tracks_preserved": preserved,
                "median_known_artists_first_five": statistics.median(artist_coverage),
                "median_known_albums_first_five": statistics.median(album_coverage),
                "median_latest_discovery_position_first_five": statistics.median(
                    first_five_last_index
                ),
            }
        )

    by_name = {row["profile"]: row for row in reports}
    broad = by_name["broad_interleaved"]
    single = by_name["single_artist"]
    gates = {
        "preserve_every_playable_track": all_preserved,
        "broad_pool_uses_available_artist_breadth": (
            broad["median_known_artists_first_five"] >= 4
        ),
        "single_artist_uses_album_breadth": (
            single["median_known_albums_first_five"] >= 3
        ),
        "all_profiles_keep_first_five_near_discovery_front": all(
            row["median_latest_discovery_position_first_five"] <= 24
            for row in reports
        ),
    }
    return {
        "campaign": "P14d",
        "scope": "in-memory queue ordering only; no Qt, filesystem, tags, artwork, or audio",
        "seeds": seeds,
        "window_size": window_size,
        "passed": all(gates.values()),
        "gates": gates,
        "profiles": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=32)
    parser.add_argument("--window-size", type=int, default=5)
    args = parser.parse_args()
    report = qualify(seeds=args.seeds, window_size=args.window_size)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
