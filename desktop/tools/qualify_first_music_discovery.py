#!/usr/bin/env python3
"""P13a scanner-only baseline for first directory/audio discovery.

This drives the real LocalFilesProvider scanner against the same in-memory
virtual filesystem used by the large-library qualification. It measures first
directory, first audio filename, completed scan and provider catalog readiness.
It does not start Qt or an audio device, so it must not be used as TTFA evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
for directory in (ROOT, TOOLS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from melodex.first_music_metrics import FirstMusicTimeline
from melodex.providers.local_files import LocalFilesProvider
from qualify_large_library import VirtualLibrary, virtual_filesystem


def run_case(
    track_count: int,
    *,
    stat_delay_ms: float = 0.0,
    directory_delay_ms: float = 0.0,
    metadata_delay_ms: float = 0.0,
    tracks_per_directory: int = 20,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="melodex-p13a-discovery-") as temp:
        root = Path(temp) / "virtual-music"
        root.mkdir()
        virtual = VirtualLibrary(
            root,
            track_count,
            tracks_per_directory=tracks_per_directory,
            stat_delay_ms=stat_delay_ms,
            directory_delay_ms=directory_delay_ms,
            metadata_delay_ms=metadata_delay_ms,
        )
        provider = LocalFilesProvider([root], scan_on_init=False)
        timeline = FirstMusicTimeline()
        source_id = timeline.begin_source(selection_started=True)
        timeline.mark("source_selected", source_id=source_id)
        timeline.mark("source_probe_started", source_id=source_id)
        started = time.perf_counter()

        def progress(payload: dict[str, Any]) -> None:
            if int(payload.get("directories_seen") or 0) > 0:
                timeline.mark("first_directory_result", source_id=source_id)
            if int(payload.get("audio_files_seen") or 0) > 0:
                timeline.mark("first_audio_file_discovered", source_id=source_id)

        with virtual_filesystem(virtual):
            snapshot = provider.scan_snapshot(
                [root],
                progress=progress,
                collect_tracks=True,
            )
            timeline.mark("source_probe_finished", source_id=source_id)
            timeline.mark("background_scan_finished", source_id=source_id)
            track_count_ready = provider.apply_scan_snapshot(snapshot)
            if track_count_ready > 0:
                timeline.mark("first_playable_track_ready", source_id=source_id)

        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        summary = timeline.summary()
        source = summary["journeys"]["sources"][0]
        return {
            "tracks_requested": int(track_count),
            "tracks_ready": int(track_count_ready),
            "stat_delay_ms": float(stat_delay_ms),
            "directory_delay_ms": float(directory_delay_ms),
            "metadata_delay_ms": float(metadata_delay_ms),
            "scan_elapsed_ms": elapsed_ms,
            "source_selected_to_first_directory_ms": source[
                "source_selected_to_first_directory_ms"
            ],
            "source_selected_to_first_audio_file_ms": source[
                "source_selected_to_first_audio_file_ms"
            ],
            "source_selected_to_first_playable_track_ms": source[
                "source_selected_to_first_playable_track_ms"
            ],
            "source_selected_to_full_scan_ms": source[
                "source_selected_to_scan_finished_ms"
            ],
            "ttfa_measured": False,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", default="1000,12700,100000")
    parser.add_argument("--tracks-per-directory", type=int, default=20)
    parser.add_argument("--stat-delay-ms", type=float, default=0.0)
    parser.add_argument("--directory-delay-ms", type=float, default=0.0)
    parser.add_argument("--metadata-delay-ms", type=float, default=0.0)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profiles = [max(0, int(value.strip())) for value in args.profiles.split(",") if value.strip()]
    if not profiles:
        raise ValueError("at least one profile is required")
    rows = [
        run_case(
            count,
            stat_delay_ms=args.stat_delay_ms,
            directory_delay_ms=args.directory_delay_ms,
            metadata_delay_ms=args.metadata_delay_ms,
            tracks_per_directory=args.tracks_per_directory,
        )
        for count in profiles
    ]
    payload = {
        "campaign": "P13a",
        "scope": "scanner discovery and provider readiness only; no Qt, GUI, decoder or audio device",
        "profiles": rows,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("P13a scanner-only first-music baseline")
        for row in rows:
            print(
                f"{row['tracks_requested']:>7,} tracks | "
                f"first directory {row['source_selected_to_first_directory_ms']} ms | "
                f"first audio file {row['source_selected_to_first_audio_file_ms']} ms | "
                f"track ready {row['source_selected_to_first_playable_track_ms']} ms | "
                f"scan {row['scan_elapsed_ms']} ms"
            )
        print("No TTFA/audio result is measured by this scanner-only run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
