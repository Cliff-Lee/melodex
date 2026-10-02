#!/usr/bin/env python3
"""Synthetic large-library probe for Melodex's current local scanner.

This intentionally exercises the real LocalFilesProvider.scan() loop while
replacing filesystem enumeration and tag parsing with controllable synthetic
work. It does not create thousands of audio files and never touches a user's
music collection.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import melodex.providers.local_files as local_files
from melodex.providers.local_files import LocalFilesProvider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile the current synchronous Melodex library scanner."
    )
    parser.add_argument("--tracks", type=int, default=12_700)
    parser.add_argument("--tracks-per-directory", type=int, default=25)
    parser.add_argument(
        "--metadata-delay-ms",
        type=float,
        default=0.0,
        help="Artificial delay for each tag read.",
    )
    parser.add_argument(
        "--directory-delay-ms",
        type=float,
        default=0.0,
        help="Artificial delay before each directory is yielded.",
    )
    parser.add_argument(
        "--non-audio-per-directory",
        type=int,
        default=1,
        help="Extra non-audio files included in each synthetic directory.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def synthetic_walk(
    root: Path,
    *,
    tracks: int,
    tracks_per_directory: int,
    directory_delay: float,
    non_audio_per_directory: int,
):
    remaining = max(0, tracks)
    directory_index = 0
    per_directory = max(1, tracks_per_directory)
    while remaining:
        if directory_delay:
            time.sleep(directory_delay)
        count = min(per_directory, remaining)
        audio = [
            f"track-{directory_index:05d}-{index:03d}.flac"
            for index in range(count)
        ]
        extras = [
            f"sidecar-{directory_index:05d}-{index:03d}.txt"
            for index in range(max(0, non_audio_per_directory))
        ]
        yield str(root / f"artist-{directory_index:05d}"), [], audio + extras
        remaining -= count
        directory_index += 1


def run_probe(args: argparse.Namespace) -> dict[str, object]:
    metadata_delay = max(0.0, args.metadata_delay_ms) / 1000.0
    directory_delay = max(0.0, args.directory_delay_ms) / 1000.0

    with tempfile.TemporaryDirectory(prefix="melodex-scan-probe-") as temp:
        root = Path(temp)

        def fake_walk(_root):
            return synthetic_walk(
                root,
                tracks=max(0, args.tracks),
                tracks_per_directory=max(1, args.tracks_per_directory),
                directory_delay=directory_delay,
                non_audio_per_directory=max(0, args.non_audio_per_directory),
            )

        def fake_metadata(path: Path) -> dict[str, object]:
            if metadata_delay:
                time.sleep(metadata_delay)
            return {
                "provider_id": "local",
                "track_id": str(path),
                "rel": f"local:{path}",
                "title": path.stem,
                "artist": "Synthetic Artist",
                "album": "Synthetic Album",
                "duration": 240.0,
                "local_path": str(path),
                "source": "local",
            }

        provider = LocalFilesProvider()
        provider.roots = [root]

        with patch.object(local_files.os, "walk", fake_walk), patch.object(
            LocalFilesProvider,
            "_metadata",
            staticmethod(fake_metadata),
        ):
            provider.scan()

        return provider.last_scan_metrics


def main() -> int:
    args = parse_args()
    metrics = run_probe(args)

    if args.json:
        print(json.dumps(metrics, indent=2))
        return 0

    print("Melodex synthetic library-scan probe")
    print("------------------------------------")
    print(f"Tracks requested:      {max(0, args.tracks):,}")
    print(f"Metadata delay/file:   {max(0.0, args.metadata_delay_ms):.3f} ms")
    print(f"Directory delay:       {max(0.0, args.directory_delay_ms):.3f} ms")
    print(f"Runs on main thread:   {metrics.get('main_thread')}")
    print(f"Directories visited:   {int(metrics.get('directories_seen') or 0):,}")
    print(f"Files visited:         {int(metrics.get('files_seen') or 0):,}")
    print(f"Tracks indexed:        {int(metrics.get('tracks_indexed') or 0):,}")
    print(f"Metadata time:         {float(metrics.get('metadata_seconds') or 0):.3f} s")
    print(f"Other scan time:       {float(metrics.get('non_metadata_seconds') or 0):.3f} s")
    print(f"Total scan time:       {float(metrics.get('total_seconds') or 0):.3f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
