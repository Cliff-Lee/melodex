#!/usr/bin/env python3
"""Measure P10j cold-scan RSS without tracemalloc overhead."""

from __future__ import annotations

import argparse
import json
import resource
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from melodex.library_index import LocalLibraryIndex
from melodex.providers.local_files import LocalFilesProvider
from tools.qualify_large_library import VirtualLibrary, virtual_filesystem


def peak_rss_mib() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return value / (1024 * 1024)
    return value / 1024


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracks", type=int, default=100_000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="melodex-p10j-rss-") as temp:
        base = Path(temp)
        root = base / "virtual-music"
        root.mkdir()
        index = LocalLibraryIndex(base / "library-index.sqlite3")
        index.sync_roots([root])
        provider = LocalFilesProvider([root], scan_on_init=False)
        library = VirtualLibrary(root, max(0, int(args.tracks)))

        baseline = peak_rss_mib()
        with virtual_filesystem(library):
            started = time.perf_counter()
            snapshot = provider.scan_snapshot(
                [root],
                collect_tracks=False,
            )
            scan_seconds = time.perf_counter() - started
            after_scan = peak_rss_mib()

            started = time.perf_counter()
            persisted = index.replace_scan([root], snapshot)
            persist_seconds = time.perf_counter() - started
            after_persist = peak_rss_mib()

        payload = {
            "tracks": int(args.tracks),
            "scan_seconds": round(scan_seconds, 6),
            "persist_seconds": round(persist_seconds, 6),
            "rss_baseline_mib": round(baseline, 3),
            "rss_after_scan_peak_mib": round(after_scan, 3),
            "rss_after_persist_peak_mib": round(after_persist, 3),
            "rss_scan_increment_mib": round(max(0.0, after_scan - baseline), 3),
            "metadata_reads": int(
                snapshot.get("changes", {}).get("metadata_reads") or 0
            ),
            "queue_peak": int(
                snapshot.get("metrics", {}).get("pipeline_max_queue_depth") or 0
            ),
            "queue_capacity": int(
                snapshot.get("metrics", {}).get("pipeline_queue_capacity") or 0
            ),
            "rows_written": int(persisted.get("tracks_written") or 0),
            "scandir_enabled": bool(
                snapshot.get("metrics", {}).get("scandir_enabled")
            ),
        }

        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for key, value in payload.items():
                print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
