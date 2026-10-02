#!/usr/bin/env python3
"""Benchmark Melodex incremental rescanning with a synthetic file library.

This creates tiny placeholder files so the real scanner performs real
enumeration/stat calls while tag extraction is replaced by a controllable fake.
It measures the first scan and then an unchanged rescan using the persistent
SQLite fingerprints.
"""

from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

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

        manager.close()

    print("Melodex incremental library benchmark")
    print("------------------------------------")
    print(f"Tracks:                  {count:,}")
    print(f"First scan:              {first_seconds:.3f} s")
    print(f"First metadata reads:    {first_reads:,}")
    print(f"Unchanged rescan:        {second_seconds:.3f} s")
    print(f"Rescan metadata reads:   {second_reads:,}")
    print(f"Metadata reused:         {int(second['changes']['unchanged']):,}")
    if first_seconds > 0:
        print(f"Rescan / first scan:     {second_seconds / first_seconds:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
