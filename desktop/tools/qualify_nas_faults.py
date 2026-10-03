#!/usr/bin/env python3
"""Campaign 11e: deterministic NAS latency and fault qualification.

The scenarios exercise the real isolated Melodex scan worker through a
qualification-only fault shim. No production code reads fault-injection flags.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from melodex.library_index import LocalLibraryIndex
from melodex.library_scan_process import LibraryScanProcess

FAULT_WORKER = Path(__file__).with_name("nas_fault_worker.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Melodex NAS latency/fault qualification scenarios."
    )
    parser.add_argument("--tracks", type=int, default=100)
    parser.add_argument("--cancel-limit-seconds", type=float, default=2.5)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _write_silent_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8_000)
        wav.writeframes(b"\x00\x00" * 80)


def create_library(root: Path, tracks: int) -> None:
    for index in range(max(0, int(tracks))):
        album = root / f"album-{index // 20:05d}"
        _write_silent_wav(album / f"track-{index:06d}.wav")


def _fault_command(**settings: object) -> list[str]:
    command = [sys.executable, "-u", str(FAULT_WORKER)]
    for key, value in settings.items():
        if value in (None, "", 0, 0.0, False):
            continue
        flag = "--" + key.replace("_", "-")
        command.extend([flag, str(value)])
    return command


def run_scan(
    data_dir: Path,
    roots: list[Path],
    *,
    timeout: float = 30.0,
    hard_cancel_after: float = 0.15,
    **faults: object,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    done = threading.Event()
    result_box: dict[str, Any] = {}
    errors: list[str] = []
    progress: list[dict[str, Any]] = []

    runner = LibraryScanProcess(
        data_dir,
        roots,
        on_progress=lambda payload: progress.append(dict(payload or {})),
        on_done=lambda payload: (
            result_box.setdefault("result", dict(payload or {})),
            done.set(),
        ),
        on_error=lambda error: (errors.append(str(error)), done.set()),
        command=_fault_command(**faults),
        hard_cancel_after=hard_cancel_after,
    )
    runner.start()
    if not done.wait(timeout):
        runner.shutdown(timeout=0.1)
        raise TimeoutError("fault-injected scan exceeded qualification timeout")
    return dict(result_box.get("result") or {}), progress, errors


def _touch_audio(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".wav", ".flac", ".mp3"}:
            continue
        stat = path.stat()
        os.utime(
            path,
            ns=(int(stat.st_atime_ns), int(stat.st_mtime_ns) + 2_000_000_000),
        )


def run_cached_browse_case(
    data_dir: Path,
    root: Path,
    *,
    expected_tracks: int,
) -> dict[str, Any]:
    _touch_audio(root)
    done = threading.Event()
    result_box: dict[str, Any] = {}
    errors: list[str] = []
    progress: list[dict[str, Any]] = []
    runner = LibraryScanProcess(
        data_dir,
        [root],
        on_progress=lambda payload: progress.append(dict(payload or {})),
        on_done=lambda payload: (
            result_box.setdefault("result", dict(payload or {})),
            done.set(),
        ),
        on_error=lambda error: (errors.append(str(error)), done.set()),
        command=_fault_command(stat_ms=5, metadata_ms=80),
        hard_cancel_after=0.2,
    )

    index = LocalLibraryIndex(data_dir / "library-index.sqlite3")
    reads = 0
    counts: list[int] = []
    latencies: list[float] = []

    runner.start()
    deadline = time.monotonic() + 15.0
    while not done.is_set() and time.monotonic() < deadline:
        started = time.monotonic()
        counts.append(len(index.load_tracks([root])))
        latencies.append(time.monotonic() - started)
        reads += 1
        time.sleep(0.025)

    if not done.wait(max(0.0, deadline - time.monotonic())):
        runner.shutdown(timeout=0.1)
        return {
            "passed": False,
            "reason": "slow rescan did not complete",
            "reads": reads,
        }

    result = dict(result_box.get("result") or {})
    final_count = len(list(result.get("tracks") or []))
    max_read = max(latencies, default=0.0)
    passed = (
        not errors
        and reads >= 3
        and counts
        and all(count == expected_tracks for count in counts)
        and final_count == expected_tracks
        and max_read < 1.0
    )
    return {
        "passed": bool(passed),
        "reads": reads,
        "cached_counts_stable": bool(
            counts and all(count == expected_tracks for count in counts)
        ),
        "max_cached_read_seconds": round(max_read, 4),
        "final_tracks": final_count,
        "errors": len(errors),
        "scan_metrics": dict(result.get("metrics") or {}),
    }


def run_blocked_cancel_case(
    data_dir: Path,
    root: Path,
    *,
    cancel_limit_seconds: float,
) -> dict[str, Any]:
    _touch_audio(root)
    first_progress = threading.Event()
    done = threading.Event()
    result_box: dict[str, Any] = {}
    errors: list[str] = []

    runner = LibraryScanProcess(
        data_dir,
        [root],
        on_progress=lambda _payload: first_progress.set(),
        on_done=lambda payload: (
            result_box.setdefault("result", dict(payload or {})),
            done.set(),
        ),
        on_error=lambda error: (errors.append(str(error)), done.set()),
        command=_fault_command(metadata_ms=2000),
        hard_cancel_after=0.15,
    )
    runner.start()
    if not first_progress.wait(3.0):
        runner.shutdown(timeout=0.1)
        return {"passed": False, "reason": "scan emitted no progress"}

    # Give discovery enough time to submit metadata work and block on a slow
    # metadata read before requesting cancellation.
    time.sleep(0.2)
    started = time.monotonic()
    runner.cancel()
    finished = done.wait(max(3.0, float(cancel_limit_seconds) + 1.0))
    elapsed = time.monotonic() - started
    result = dict(result_box.get("result") or {})

    passed = (
        finished
        and not errors
        and bool(result.get("cancelled"))
        and bool(result.get("hard_cancelled"))
        and elapsed <= float(cancel_limit_seconds)
        and not runner.running
    )
    return {
        "passed": bool(passed),
        "elapsed_seconds": round(elapsed, 3),
        "limit_seconds": float(cancel_limit_seconds),
        "cancelled": bool(result.get("cancelled")),
        "hard_cancelled": bool(result.get("hard_cancelled")),
        "errors": len(errors),
    }


def run_qualification(
    *,
    tracks: int = 100,
    cancel_limit_seconds: float = 2.5,
) -> dict[str, Any]:
    # At least 40 audio files guarantees enough stat samples for adaptive
    # concurrency and more than one album directory for traversal faults.
    expected = max(40, int(tracks))

    with tempfile.TemporaryDirectory(prefix="melodex-nas-faults-") as temp:
        base = Path(temp)
        data_dir = base / "data"
        root = base / "nas-music"
        root.mkdir()
        create_library(root, expected)

        initial, _, initial_errors = run_scan(data_dir, [root])
        initial_count = len(list(initial.get("tracks") or []))
        initial_passed = not initial_errors and initial_count == expected

        latency, _, latency_errors = run_scan(
            data_dir,
            [root],
            stat_ms=12,
            scandir_ms=4,
        )
        latency_metrics = dict(latency.get("metrics") or {})
        latency_count = len(list(latency.get("tracks") or []))
        latency_passed = (
            not latency_errors
            and latency_count == expected
            and str(latency_metrics.get("storage_profile") or "") == "high-latency"
            and float(latency_metrics.get("storage_average_stat_ms") or 0.0) >= 8.0
            and int(latency_metrics.get("metadata_worker_limit") or 0) == 2
            and int(latency_metrics.get("metadata_in_flight_limit") or 0) <= 4
        )

        transient, _, transient_errors = run_scan(
            data_dir,
            [root],
            transient_scandir_every=2,
            transient_stat_every=5,
        )
        transient_metrics = dict(transient.get("metrics") or {})
        transient_states = [
            dict(row)
            for row in list(transient.get("root_states") or [])
            if isinstance(row, dict)
        ]
        transient_count = len(list(transient.get("tracks") or []))
        transient_passed = (
            not transient_errors
            and transient_count == expected
            and transient_states
            and all(bool(row.get("complete")) for row in transient_states)
            and int(transient_metrics.get("io_retries") or 0) > 0
        )

        interrupted, _, interrupted_errors = run_scan(
            data_dir,
            [root],
            # Root + first album enumerate successfully; every later scandir
            # then fails through the bounded retry budget, simulating a share
            # disappearing after traversal is already underway.
            drop_after_scandirs=2,
        )
        interrupted_states = [
            dict(row)
            for row in list(interrupted.get("root_states") or [])
            if isinstance(row, dict)
        ]
        interrupted_persistence = dict(interrupted.get("persistence") or {})
        interrupted_count = len(list(interrupted.get("tracks") or []))
        interrupted_passed = (
            not interrupted_errors
            and interrupted_count == expected
            and interrupted_states
            and any(
                bool(row.get("available")) and not bool(row.get("complete"))
                for row in interrupted_states
            )
            and int(interrupted_persistence.get("roots_incomplete") or 0) >= 1
            and int(interrupted_persistence.get("tracks_deleted") or 0) == 0
        )

        browse_case = run_cached_browse_case(
            data_dir,
            root,
            expected_tracks=expected,
        )
        cancel_case = run_blocked_cancel_case(
            data_dir,
            root,
            cancel_limit_seconds=max(0.5, float(cancel_limit_seconds)),
        )

        cases = {
            "baseline_index": {
                "passed": bool(initial_passed),
                "tracks": initial_count,
                "expected_tracks": expected,
                "errors": len(initial_errors),
            },
            "high_latency_adaptation": {
                "passed": bool(latency_passed),
                "tracks": latency_count,
                "storage_profile": latency_metrics.get("storage_profile"),
                "average_stat_ms": latency_metrics.get("storage_average_stat_ms"),
                "metadata_worker_limit": latency_metrics.get("metadata_worker_limit"),
                "metadata_in_flight_limit": latency_metrics.get(
                    "metadata_in_flight_limit"
                ),
                "errors": len(latency_errors),
            },
            "transient_fault_recovery": {
                "passed": bool(transient_passed),
                "tracks": transient_count,
                "io_retries": int(transient_metrics.get("io_retries") or 0),
                "root_complete": bool(
                    transient_states
                    and all(bool(row.get("complete")) for row in transient_states)
                ),
                "errors": len(transient_errors),
            },
            "midscan_disconnect_preserves_cache": {
                "passed": bool(interrupted_passed),
                "tracks": interrupted_count,
                "roots_incomplete": int(
                    interrupted_persistence.get("roots_incomplete") or 0
                ),
                "tracks_deleted": int(
                    interrupted_persistence.get("tracks_deleted") or 0
                ),
                "errors": len(interrupted_errors),
            },
            "cached_browse_during_slow_rescan": browse_case,
            "blocked_metadata_cancel": cancel_case,
        }

        return {
            "campaign": "11e",
            "tracks": expected,
            "passed": all(bool(case.get("passed")) for case in cases.values()),
            "cases": cases,
        }


def main() -> int:
    args = parse_args()
    result = run_qualification(
        tracks=args.tracks,
        cancel_limit_seconds=args.cancel_limit_seconds,
    )

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("Melodex Campaign 11e NAS fault qualification")
        print("--------------------------------------------")
        print(f"Synthetic tracks: {result['tracks']:,}")
        for name, case in result["cases"].items():
            status = "PASS" if case.get("passed") else "FAIL"
            print(f"{status:4}  {name}")
        print("--------------------------------------------")
        print("OVERALL:", "PASS" if result["passed"] else "FAIL")

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
