#!/usr/bin/env python3
"""Qualification-only worker for deterministic NAS fault injection.

This script wraps the real Melodex library scan child with controlled latency and
filesystem failures. It is never imported or used by the packaged application.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import melodex.providers.local_files as local_files
from melodex.library_scan_process import run_library_scan_child
from melodex.providers.local_files import LocalFilesProvider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scandir-ms", type=float, default=0.0)
    parser.add_argument("--stat-ms", type=float, default=0.0)
    parser.add_argument("--metadata-ms", type=float, default=0.0)
    parser.add_argument("--transient-scandir-every", type=int, default=0)
    parser.add_argument("--transient-stat-every", type=int, default=0)
    parser.add_argument("--persistent-fail-dir", default="")
    parser.add_argument("--drop-after-scandirs", type=int, default=0)
    return parser.parse_args()


class FaultState:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.lock = threading.Lock()
        self.scandir_calls = 0
        self.successful_scandirs = 0
        self.stat_ordinals = 0

    def next_scandir(self) -> tuple[int, int]:
        with self.lock:
            self.scandir_calls += 1
            return self.scandir_calls, self.successful_scandirs

    def scandir_succeeded(self) -> None:
        with self.lock:
            self.successful_scandirs += 1

    def next_stat_ordinal(self) -> int:
        with self.lock:
            self.stat_ordinals += 1
            return self.stat_ordinals


class FaultEntry:
    def __init__(self, entry, state: FaultState) -> None:
        self._entry = entry
        self._state = state
        self._stat_ordinal: int | None = None
        self._transient_stat_failed = False

    @property
    def name(self):
        return self._entry.name

    @property
    def path(self):
        return self._entry.path

    def is_dir(self, *, follow_symlinks: bool = False):
        return self._entry.is_dir(follow_symlinks=follow_symlinks)

    def stat(self):
        delay = max(0.0, float(self._state.args.stat_ms)) / 1000.0
        if delay:
            time.sleep(delay)
        if self._stat_ordinal is None:
            self._stat_ordinal = self._state.next_stat_ordinal()
        every = max(0, int(self._state.args.transient_stat_every))
        if (
            every
            and self._stat_ordinal % every == 0
            and not self._transient_stat_failed
        ):
            self._transient_stat_failed = True
            raise OSError("simulated transient NAS stat failure")
        return self._entry.stat()


class FaultScandir:
    def __init__(self, iterator, state: FaultState) -> None:
        self._iterator = iterator
        self._state = state

    def __enter__(self):
        self._iterator.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._iterator.__exit__(exc_type, exc, tb)

    def __iter__(self):
        return (FaultEntry(entry, self._state) for entry in self._iterator)


def install_faults(args: argparse.Namespace) -> None:
    state = FaultState(args)
    real_scandir = local_files.os.scandir
    real_metadata = LocalFilesProvider._metadata

    def fault_scandir(path):
        delay = max(0.0, float(args.scandir_ms)) / 1000.0
        if delay:
            time.sleep(delay)
        call_number, successful = state.next_scandir()
        target = str(args.persistent_fail_dir or "").strip()
        if target and Path(path).name == target:
            raise OSError("simulated persistent NAS directory failure")
        drop_after = max(0, int(args.drop_after_scandirs))
        if drop_after and successful >= drop_after:
            raise OSError("simulated NAS disconnect during traversal")
        transient_every = max(0, int(args.transient_scandir_every))
        if transient_every and call_number % transient_every == 0:
            raise OSError("simulated transient NAS scandir failure")
        iterator = real_scandir(path)
        state.scandir_succeeded()
        return FaultScandir(iterator, state)

    def fault_metadata(path: Path):
        delay = max(0.0, float(args.metadata_ms)) / 1000.0
        if delay:
            time.sleep(delay)
        return real_metadata(path)

    local_files.os.scandir = fault_scandir
    LocalFilesProvider._metadata = staticmethod(fault_metadata)


def main() -> int:
    args = parse_args()
    install_faults(args)
    return run_library_scan_child()


if __name__ == "__main__":
    raise SystemExit(main())
