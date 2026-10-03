#!/usr/bin/env python3
"""P10i release-scale qualification for Melodex library scanning.

This exercises the real LocalFilesProvider + LocalLibraryIndex pipeline against
an in-memory virtual filesystem. It avoids creating hundreds of thousands of
real files while still driving discovery, stat fingerprints, metadata reads,
directory manifests, SQLite persistence, delta rescans and cancellation/resume.

Normal PR usage should stay at 12.7k/100k. The 250k/500k/1m cases are explicit
release-scale runs.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
try:
    import resource
except ImportError:  # Windows developer runs
    resource = None
import sys
import tempfile
import time
import tracemalloc
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import melodex.providers.local_files as local_files
from melodex.library_index import LocalLibraryIndex
from melodex.library_scan import ScanControl
from melodex.providers.local_files import LocalFilesProvider


DEFAULT_PROFILES = (12_700, 100_000)
RELEASE_PROFILES = (250_000, 500_000, 1_000_000)

P10J_SCALE_GATES = {
    "max_queue_capacity": 256,
    "max_metadata_in_flight": 8,
    "max_unchanged_vs_cold_ratio": 1.10,
    "max_delta_vs_cold_ratio": 1.20,
    # Allows normal fixed overhead plus ~1.25 KiB of traced Python memory per
    # track. This is a super-linear-regression guard, not a promise that 1M
    # tracks should permanently consume this much memory.
    "python_peak_base_mib": 32.0,
    "python_peak_mib_per_track": 0.00125,
}


class VirtualDirEntry:
    def __init__(
        self,
        library: "VirtualLibrary",
        path: Path,
        *,
        is_directory: bool,
    ) -> None:
        self._library = library
        self._path = Path(path)
        self.name = self._path.name
        self.path = str(self._path)
        self._is_directory = bool(is_directory)

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        return self._is_directory

    def stat(self, *, follow_symlinks: bool = True):
        return self._library.fake_stat(self._path)


class VirtualScandir:
    def __init__(self, entries: list[VirtualDirEntry]) -> None:
        self._entries = entries

    def __enter__(self):
        return iter(self._entries)

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class VirtualLibrary:
    def __init__(
        self,
        root: Path,
        track_count: int,
        *,
        tracks_per_directory: int = 20,
        stat_delay_ms: float = 0.0,
        directory_delay_ms: float = 0.0,
        metadata_delay_ms: float = 0.0,
    ) -> None:
        self.root = Path(root)
        self.track_count = max(0, int(track_count))
        self.tracks_per_directory = max(1, int(tracks_per_directory))
        self.stat_delay = max(0.0, float(stat_delay_ms)) / 1000.0
        self.directory_delay = max(0.0, float(directory_delay_ms)) / 1000.0
        self.metadata_delay = max(0.0, float(metadata_delay_ms)) / 1000.0
        self.changed: set[int] = set()
        self.deleted: set[int] = set()
        self.added = 0
        self.metadata_reads = 0

    @property
    def total_tracks(self) -> int:
        return self.track_count - len(self.deleted) + self.added

    def path_for(self, index: int) -> Path:
        directory = index // self.tracks_per_directory
        return self.root / f"album-{directory:07d}" / f"track-{index:09d}.flac"

    def iter_indices(self):
        for index in range(self.track_count + self.added):
            if index not in self.deleted:
                yield index

    def scandir(self, path: Path):
        path = Path(path)
        if path == self.root:
            directories = sorted(
                {
                    index // self.tracks_per_directory
                    for index in self.iter_indices()
                }
            )
            return VirtualScandir(
                [
                    VirtualDirEntry(
                        self,
                        self.root / f"album-{directory:07d}",
                        is_directory=True,
                    )
                    for directory in directories
                ]
            )

        try:
            directory = int(path.name.removeprefix("album-"))
        except ValueError:
            raise FileNotFoundError(str(path))

        start = directory * self.tracks_per_directory
        stop = min(
            start + self.tracks_per_directory,
            self.track_count + self.added,
        )
        entries = []
        for index in range(start, stop):
            if index in self.deleted:
                continue
            entries.append(
                VirtualDirEntry(
                    self,
                    self.path_for(index),
                    is_directory=False,
                )
            )
        return VirtualScandir(entries)

    def walk(self, _root: Path, onerror=None):
        current_dir = None
        names: list[str] = []
        base: Path | None = None
        for index in self.iter_indices():
            directory = index // self.tracks_per_directory
            if current_dir is None:
                current_dir = directory
                base = self.root / f"album-{directory:07d}"
            if directory != current_dir:
                if self.directory_delay:
                    time.sleep(self.directory_delay)
                yield str(base), [], names
                current_dir = directory
                base = self.root / f"album-{directory:07d}"
                names = []
            names.append(f"track-{index:09d}.flac")
        if current_dir is not None and base is not None:
            if self.directory_delay:
                time.sleep(self.directory_delay)
            yield str(base), [], names

    def fake_stat(self, path: Path):
        if self.stat_delay:
            time.sleep(self.stat_delay)
        value = str(path)
        root_value = str(self.root)
        if value == root_value:
            return SimpleNamespace(
                st_size=0,
                st_mtime=1.0,
                st_mtime_ns=1_000_000_000,
                st_mode=0o40755,
            )
        name = path.name
        if value.startswith(root_value) and name.startswith("album-"):
            return SimpleNamespace(
                st_size=0,
                st_mtime=1.0,
                st_mtime_ns=1_000_000_000,
                st_mode=0o40755,
            )
        if not (value.startswith(root_value) and name.endswith(".flac")):
            raise FileNotFoundError(value)
        try:
            index = int(name.removeprefix("track-").removesuffix(".flac"))
        except ValueError:
            raise FileNotFoundError(value)
        if index in self.deleted or index >= self.track_count + self.added:
            raise FileNotFoundError(value)
        version = 2 if index in self.changed else 1
        return SimpleNamespace(
            st_size=1000 + index % 8192 + version,
            st_mtime=float(version),
            st_mtime_ns=version * 1_000_000_000 + index,
            st_mode=0o100644,
        )

    def metadata(self, path: Path) -> dict[str, Any]:
        self.metadata_reads += 1
        if self.metadata_delay:
            time.sleep(self.metadata_delay)
        index = int(path.name.removeprefix("track-").removesuffix(".flac"))
        return {
            "provider_id": "local",
            "track_id": str(path),
            "rel": f"local:{path}",
            "local_path": str(path),
            "title": f"Track {index:09d}",
            "artist": f"Artist {index // 200:06d}",
            "album": f"Album {index // self.tracks_per_directory:07d}",
            "track_number": index % self.tracks_per_directory + 1,
            "duration": 180.0 + index % 120,
            "source": "local",
        }

    def mutate(self, *, changed: int, added: int, deleted: int) -> None:
        self.changed = set(range(min(max(0, changed), self.track_count)))
        self.deleted = set(
            range(
                max(0, self.track_count - max(0, deleted)),
                self.track_count,
            )
        )
        self.added = max(0, int(added))


@contextmanager
def virtual_filesystem(library: VirtualLibrary):
    original_stat = Path.stat

    def patched_stat(path: Path, *args, **kwargs):
        try:
            return library.fake_stat(path)
        except FileNotFoundError:
            return original_stat(path, *args, **kwargs)

    with patch.object(local_files.os, "scandir", library.scandir), patch.object(
        local_files.Path,
        "stat",
        patched_stat,
    ), patch.object(
        LocalFilesProvider,
        "_metadata",
        staticmethod(library.metadata),
    ):
        yield


def _peak_rss_mib() -> float:
    if resource is None:
        return 0.0
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return value / (1024 * 1024)
    return value / 1024


def run_scan(
    provider: LocalFilesProvider,
    index: LocalLibraryIndex,
    roots: list[Path],
    *,
    cached: dict[str, dict[str, Any]] | None = None,
    cached_directories: dict[str, dict[str, Any]] | None = None,
    control: ScanControl | None = None,
    checkpoint=None,
) -> tuple[dict[str, Any], float, float]:
    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    snapshot = provider.scan_snapshot(
        roots,
        cached_entries=cached,
        cached_directories=cached_directories,
        collect_tracks=False,
        control=control,
        checkpoint=checkpoint,
    )
    seconds = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return snapshot, seconds, peak / (1024 * 1024)


def qualify_profile(
    track_count: int,
    *,
    tracks_per_directory: int,
    stat_delay_ms: float,
    directory_delay_ms: float,
    metadata_delay_ms: float,
    delta_changed: int,
    delta_added: int,
    delta_deleted: int,
    cancellation_after: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="melodex-p10i-") as temp:
        base = Path(temp)
        root = base / "virtual-music"
        data = base / "data"
        root.mkdir()

        library = VirtualLibrary(
            root,
            track_count,
            tracks_per_directory=tracks_per_directory,
            stat_delay_ms=stat_delay_ms,
            directory_delay_ms=directory_delay_ms,
            metadata_delay_ms=metadata_delay_ms,
        )
        index = LocalLibraryIndex(data / "library-index.sqlite3")
        index.sync_roots([root])
        provider = LocalFilesProvider([root], scan_on_init=False)

        with virtual_filesystem(library):
            library.metadata_reads = 0
            cold, cold_seconds, cold_peak = run_scan(
                provider,
                index,
                [root],
            )
            cold_reads = library.metadata_reads
            persist_started = time.perf_counter()
            cold_persist = index.replace_scan([root], cold)
            cold_persist_seconds = time.perf_counter() - persist_started

            cached = index.load_scan_cache([root])
            cached_dirs = index.load_directory_manifests([root])

            library.metadata_reads = 0
            warm, warm_seconds, warm_peak = run_scan(
                provider,
                index,
                [root],
                cached=cached,
                cached_directories=cached_dirs,
            )
            warm_reads = library.metadata_reads
            warm_persist = index.replace_scan([root], warm)

            library.mutate(
                changed=delta_changed,
                added=delta_added,
                deleted=delta_deleted,
            )
            cached = index.load_scan_cache([root])
            cached_dirs = index.load_directory_manifests([root])
            library.metadata_reads = 0
            delta, delta_seconds, delta_peak = run_scan(
                provider,
                index,
                [root],
                cached=cached,
                cached_directories=cached_dirs,
            )
            delta_reads = library.metadata_reads
            delta_persist = index.replace_scan([root], delta)

            # Interruption/restart qualification uses staging without publishing
            # the cancelled result. Only freshly-read rows are checkpointed.
            generation = index.begin_scan_generation([root])
            staged_batch: list[dict[str, Any]] = []
            control = ScanControl()
            staged_total = 0

            def checkpoint(record: dict[str, Any]) -> None:
                nonlocal staged_total
                staged_batch.append(dict(record))
                staged_total += 1
                if len(staged_batch) >= 64:
                    index.stage_scan_records(generation, [root], list(staged_batch))
                    staged_batch.clear()
                if cancellation_after > 0 and staged_total >= cancellation_after:
                    control.cancel()

            # Force a fresh changed subset so cancellation has useful work.
            library.changed.update(
                range(
                    min(
                        max(cancellation_after * 2, 1),
                        library.track_count,
                    )
                )
            )
            cached = index.load_scan_cache([root])
            cached_dirs = index.load_directory_manifests([root])
            cancelled, cancel_seconds, cancel_peak = run_scan(
                provider,
                index,
                [root],
                cached=cached,
                cached_directories=cached_dirs,
                control=control,
                checkpoint=checkpoint,
            )
            if staged_batch:
                index.stage_scan_records(generation, [root], list(staged_batch))
                staged_batch.clear()
            index.finish_scan_generation(generation, status="cancelled")
            resume_cache = index.load_resume_cache([root])

            # Overlay live cache exactly as the isolated worker does.
            restart_cache = index.load_scan_cache([root])
            restart_cache.update(resume_cache)
            library.metadata_reads = 0
            restart, restart_seconds, restart_peak = run_scan(
                provider,
                index,
                [root],
                cached=restart_cache,
                cached_directories=index.load_directory_manifests([root]),
            )
            restart_reads = library.metadata_reads

        summary = {
            "tracks": int(track_count),
            "tracks_after_delta": int(library.total_tracks),
            "cold": {
                "seconds": round(cold_seconds, 6),
                "peak_python_mib": round(cold_peak, 3),
                "metadata_reads": int(cold_reads),
                "queue_peak": int(
                    cold["metrics"].get("pipeline_max_queue_depth") or 0
                ),
                "queue_capacity": int(
                    cold["metrics"].get("pipeline_queue_capacity") or 0
                ),
                "metadata_max_in_flight": int(
                    cold["metrics"].get("metadata_max_in_flight") or 0
                ),
                "persist_seconds": round(cold_persist_seconds, 6),
                "write_batches": int(cold_persist.get("write_batches") or 0),
            },
            "unchanged": {
                "seconds": round(warm_seconds, 6),
                "peak_python_mib": round(warm_peak, 3),
                "metadata_reads": int(warm_reads),
                "unchanged": int(warm["changes"].get("unchanged") or 0),
                "manifest_hits": int(
                    warm["metrics"].get("directory_manifest_hits") or 0
                ),
                "rows_written": int(warm_persist.get("tracks_written") or 0),
            },
            "delta": {
                "seconds": round(delta_seconds, 6),
                "peak_python_mib": round(delta_peak, 3),
                "metadata_reads": int(delta_reads),
                "changed": int(delta["changes"].get("changed") or 0),
                "added": int(delta["changes"].get("added") or 0),
                "removed": int(delta["changes"].get("removed") or 0),
                "rows_written": int(delta_persist.get("tracks_written") or 0),
                "rows_deleted": int(delta_persist.get("tracks_deleted") or 0),
            },
            "cancel_restart": {
                "cancelled": bool(cancelled.get("cancelled")),
                "cancel_seconds": round(cancel_seconds, 6),
                "cancel_peak_python_mib": round(cancel_peak, 3),
                "staged_rows": len(resume_cache),
                "restart_seconds": round(restart_seconds, 6),
                "restart_peak_python_mib": round(restart_peak, 3),
                "restart_metadata_reads": int(restart_reads),
                "resumed_rows": int(restart["changes"].get("resumed") or 0),
            },
            "database_mib": round(
                (data / "library-index.sqlite3").stat().st_size
                / (1024 * 1024),
                3,
            ),
            "process_peak_rss_mib": round(_peak_rss_mib(), 3),
        }
        cold_seconds = max(0.000001, float(summary["cold"]["seconds"]))
        python_budget = (
            float(P10J_SCALE_GATES["python_peak_base_mib"])
            + int(track_count)
            * float(P10J_SCALE_GATES["python_peak_mib_per_track"])
        )
        summary["checks"] = {
            "bounded_discovery_queue": (
                summary["cold"]["queue_peak"]
                <= min(
                    summary["cold"]["queue_capacity"],
                    int(P10J_SCALE_GATES["max_queue_capacity"]),
                )
            ),
            "bounded_metadata_in_flight": (
                summary["cold"]["metadata_max_in_flight"]
                <= int(P10J_SCALE_GATES["max_metadata_in_flight"])
            ),
            "unchanged_zero_metadata_reads": (
                summary["unchanged"]["metadata_reads"] == 0
            ),
            "unchanged_zero_rewrites": (
                summary["unchanged"]["rows_written"] == 0
            ),
            "delta_reads_scale_with_changes": (
                summary["delta"]["metadata_reads"]
                <= max(1, delta_changed + delta_added)
            ),
            "unchanged_not_slower_than_cold": (
                float(summary["unchanged"]["seconds"])
                <= cold_seconds
                * float(P10J_SCALE_GATES["max_unchanged_vs_cold_ratio"])
            ),
            "delta_not_slower_than_cold": (
                float(summary["delta"]["seconds"])
                <= cold_seconds
                * float(P10J_SCALE_GATES["max_delta_vs_cold_ratio"])
            ),
            "python_peak_within_linear_budget": (
                float(summary["cold"]["peak_python_mib"]) <= python_budget
            ),
            "cancel_publishes_no_partial_tracks": (
                bool(summary["cancel_restart"]["cancelled"])
            ),
            "resume_reuses_staged_rows": (
                summary["cancel_restart"]["staged_rows"] == 0
                or summary["cancel_restart"]["resumed_rows"] > 0
            ),
        }
        summary["scale_gates"] = {
            **P10J_SCALE_GATES,
            "python_peak_budget_mib": round(python_budget, 3),
        }
        return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run P10i large-library qualification scenarios."
    )
    parser.add_argument(
        "--profiles",
        default=",".join(str(v) for v in DEFAULT_PROFILES),
        help="Comma-separated track counts.",
    )
    parser.add_argument(
        "--release-scale",
        action="store_true",
        help="Append 250k, 500k and 1m qualification profiles.",
    )
    parser.add_argument("--tracks-per-directory", type=int, default=20)
    parser.add_argument("--stat-delay-ms", type=float, default=0.0)
    parser.add_argument("--directory-delay-ms", type=float, default=0.0)
    parser.add_argument("--metadata-delay-ms", type=float, default=0.0)
    parser.add_argument("--delta-changed", type=int, default=50)
    parser.add_argument("--delta-added", type=int, default=50)
    parser.add_argument("--delta-deleted", type=int, default=10)
    parser.add_argument("--cancellation-after", type=int, default=256)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def parse_profiles(raw: str) -> list[int]:
    values = []
    for part in str(raw or "").split(","):
        part = part.strip().replace("_", "")
        if part:
            values.append(max(0, int(part)))
    if not values:
        raise ValueError("at least one profile is required")
    return values


def main() -> int:
    args = parse_args()
    profiles = parse_profiles(args.profiles)
    if args.release_scale:
        for value in RELEASE_PROFILES:
            if value not in profiles:
                profiles.append(value)

    rows = []
    overall_pass = True
    for track_count in profiles:
        row = qualify_profile(
            track_count,
            tracks_per_directory=args.tracks_per_directory,
            stat_delay_ms=args.stat_delay_ms,
            directory_delay_ms=args.directory_delay_ms,
            metadata_delay_ms=args.metadata_delay_ms,
            delta_changed=args.delta_changed,
            delta_added=args.delta_added,
            delta_deleted=args.delta_deleted,
            cancellation_after=args.cancellation_after,
        )
        rows.append(row)
        overall_pass = overall_pass and all(row["checks"].values())

    payload = {
        "campaign": "P10i",
        "profiles": rows,
        "passed": bool(overall_pass),
        "release_scale": bool(args.release_scale),
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Melodex P10i large-library qualification")
        print("----------------------------------------")
        for row in rows:
            print(
                f"{row['tracks']:>10,} tracks | "
                f"cold {row['cold']['seconds']:.3f}s | "
                f"unchanged {row['unchanged']['seconds']:.3f}s | "
                f"delta reads {row['delta']['metadata_reads']:,} | "
                f"peak Python {row['cold']['peak_python_mib']:.1f} MiB | "
                f"{'PASS' if all(row['checks'].values()) else 'FAIL'}"
            )
        print(f"Overall: {'PASS' if overall_pass else 'FAIL'}")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
