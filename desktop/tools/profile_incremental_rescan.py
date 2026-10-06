#!/usr/bin/env python3
"""Benchmark Melodex incremental rescanning with a synthetic file library.

This creates tiny placeholder files so the real scanner performs real
enumeration/stat calls while tag extraction is replaced by a controllable fake.
It measures the first scan and then an unchanged rescan using the persistent
SQLite fingerprints.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from melodex.provider_manager import ProviderManager
from melodex.providers.local_files import LocalFilesProvider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracks", type=int, default=12_700)
    parser.add_argument("--metadata-delay-ms", type=float, default=0.0)
    return parser.parse_args()


def metadata(path: Path, delay: float) -> dict[str, object]:
    if delay:
        time.sleep(delay)
    return {
        "provider_id": "local",
        "track_id": str(path),
        "rel": f"local:{path}",
        "local_path": str(path),
        "title": path.stem,
        "artist": "Synthetic Artist",
        "album": f"Album {int(path.stem.split('-')[-1]) // 10:05d}",
        "duration": 240.0,
        "source": "local",
    }


def main() -> int:
    args = parse_args()
    count = max(0, int(args.tracks))
    delay = max(0.0, float(args.metadata_delay_ms)) / 1000.0

    with tempfile.TemporaryDirectory(prefix="melodex-incremental-") as temp:
        base = Path(temp)
        root = base / "music"
        root.mkdir()
        for index in range(count):
            album = root / f"album-{index // 20:05d}"
            album.mkdir(exist_ok=True)
            (album / f"track-{index:06d}.flac").write_bytes(b"x")

        manager = ProviderManager(base / "data")
        manager.configure_local_roots([root])
        calls = {"count": 0}

        def fake_metadata(path: Path):
            calls["count"] += 1
            return metadata(path, delay)

        with patch.object(
            LocalFilesProvider,
            "_metadata",
            staticmethod(fake_metadata),
        ):
            started = time.perf_counter()
            first = manager.scan_local_roots_snapshot([root])
            first_seconds = time.perf_counter() - started
            manager.persist_local_scan_snapshot([root], first)

            first_reads = calls["count"]
            calls["count"] = 0

            started = time.perf_counter()
            second = manager.scan_local_roots_snapshot([root])
            second_seconds = time.perf_counter() - started
            second_reads = calls["count"]

            persist_started = time.perf_counter()
            second_persist = manager.persist_local_scan_snapshot([root], second)
            persist_seconds = time.perf_counter() - persist_started

        manager.close()

    print("Melodex incremental library benchmark")
    print("------------------------------------")
    print(f"Tracks:                  {count:,}")
    print(f"First scan:              {first_seconds:.3f} s")
    print(f"First metadata reads:    {first_reads:,}")
    print(
        "First storage profile:   "
        f"{first['metrics'].get('storage_profile')} "
        f"({int(first['metrics'].get('metadata_worker_limit') or 0)} workers, "
        f"{int(first['metrics'].get('metadata_max_in_flight') or 0)} max in flight)"
    )
    print(f"Unchanged rescan:        {second_seconds:.3f} s")
    print(f"Rescan metadata reads:   {second_reads:,}")
    print(f"Metadata reused:         {int(second['changes']['unchanged']):,}")
    print(
        "Directory manifest hits: "
        f"{int(second['metrics'].get('directory_manifest_hits') or 0):,}"
    )
    print(
        "Directory manifest miss: "
        f"{int(second['metrics'].get('directory_manifest_misses') or 0):,}"
    )
    print(f"Index rows rewritten:    {int(second_persist['tracks_written']):,}")
    print(f"Index rows reused:       {int(second_persist['tracks_reused']):,}")
    print(f"Index commit:            {persist_seconds:.3f} s")
    if first_seconds > 0:
        print(f"Rescan / first scan:     {second_seconds / first_seconds:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
