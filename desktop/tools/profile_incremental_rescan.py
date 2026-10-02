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
    parser.add_argument("--json", action="store_true")
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


def run_probe(*, tracks: int = 12_700, metadata_delay_ms: float = 0.0) -> dict[str, object]:
    count = max(0, int(tracks))
    delay = max(0.0, float(metadata_delay_ms)) / 1000.0

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

    return {
        "tracks": count,
        "first_scan_seconds": round(first_seconds, 6),
        "first_metadata_reads": int(first_reads),
        "unchanged_rescan_seconds": round(second_seconds, 6),
        "rescan_metadata_reads": int(second_reads),
        "metadata_reused": int(second["changes"]["unchanged"]),
        "index_rows_rewritten": int(second_persist["tracks_written"]),
        "index_rows_reused": int(second_persist["tracks_reused"]),
        "index_commit_seconds": round(persist_seconds, 6),
        "rescan_first_ratio": (
            round(second_seconds / first_seconds, 6)
            if first_seconds > 0
            else None
        ),
    }


def main() -> int:
    args = parse_args()
    payload = run_probe(
        tracks=args.tracks,
        metadata_delay_ms=args.metadata_delay_ms,
    )

    if args.json:
        import json
        print(json.dumps(payload, indent=2))
        return 0

    print("Melodex incremental library benchmark")
    print("------------------------------------")
    print(f"Tracks:                  {int(payload['tracks']):,}")
    print(f"First scan:              {float(payload['first_scan_seconds']):.3f} s")
    print(f"First metadata reads:    {int(payload['first_metadata_reads']):,}")
    print(f"Unchanged rescan:        {float(payload['unchanged_rescan_seconds']):.3f} s")
    print(f"Rescan metadata reads:   {int(payload['rescan_metadata_reads']):,}")
    print(f"Metadata reused:         {int(payload['metadata_reused']):,}")
    print(f"Index rows rewritten:    {int(payload['index_rows_rewritten']):,}")
    print(f"Index rows reused:       {int(payload['index_rows_reused']):,}")
    print(f"Index commit:            {float(payload['index_commit_seconds']):.3f} s")
    ratio = payload.get("rescan_first_ratio")
    if ratio is not None:
        print(f"Rescan / first scan:     {float(ratio):.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
