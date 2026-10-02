#!/usr/bin/env python3
"""Benchmark Melodex's persistent library metadata index."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from melodex.library_index import LocalLibraryIndex


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracks", type=int, default=12_700)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    track_count = max(0, int(args.tracks))

    with tempfile.TemporaryDirectory(prefix="melodex-index-benchmark-") as temp:
        data = Path(temp)
        root = Path("/synthetic/Synology/Music")
        index = LocalLibraryIndex(data / "library-index.sqlite3")
        index.sync_roots([root])

        tracks = [
            {
                "provider_id": "local",
                "track_id": str(root / f"Artist {i % 600:04d}" / f"{i:06d}.flac"),
                "local_path": str(root / f"Artist {i % 600:04d}" / f"{i:06d}.flac"),
                "rel": f"local:{root / f'Artist {i % 600:04d}' / f'{i:06d}.flac'}",
                "artist": f"Artist {i % 600:04d}",
                "album": f"Album {i % 1200:04d}",
                "title": f"Track {i:06d}",
                "track_number": (i % 20) + 1,
                "disc_number": 1,
                "year": 1980 + (i % 47),
                "duration": 180.0 + (i % 180),
                "source": "local",
            }
            for i in range(track_count)
        ]
        snapshot = {
            "tracks": tracks,
            "index_tracks": tracks,
            "root_states": [{"path": str(root), "available": True}],
            "metrics": {"tracks_indexed": track_count},
            "cancelled": False,
        }

        started = time.perf_counter()
        index.replace_scan([root], snapshot)
        write_seconds = time.perf_counter() - started

        started = time.perf_counter()
        loaded = index.load_tracks([root])
        read_seconds = time.perf_counter() - started

        payload = {
            "tracks": track_count,
            "tracks_loaded": len(loaded),
            "write_seconds": round(write_seconds, 6),
            "read_seconds": round(read_seconds, 6),
            "database_bytes": (data / "library-index.sqlite3").stat().st_size,
            "ready": index.roots_ready([root]),
        }

        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("Melodex persistent library index benchmark")
            print("-----------------------------------------")
            print(f"Tracks:          {payload['tracks']:,}")
            print(f"Write:           {payload['write_seconds']:.3f} s")
            print(f"Startup read:    {payload['read_seconds']:.3f} s")
            print(f"Database size:   {payload['database_bytes'] / 1024 / 1024:.2f} MiB")
            print(f"Ready:           {payload['ready']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
