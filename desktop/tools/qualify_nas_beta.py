#!/usr/bin/env python3
"""Campaign 11c: repeatable NAS / network-library qualification harness.

The harness uses tiny valid WAV files in a temporary tree so it never touches a
user's music collection. It exercises the same isolated scan-process boundary
used by the desktop application and checks the behaviors that matter most before
recruiting NAS testers:

- first scan completes through the disposable worker;
- the persistent index survives the library root becoming unavailable;
- reconnecting the root restores a normal scan;
- a deliberately hung worker is forcibly cancelled within a bounded time.

It is intentionally a qualification harness, not a performance optimizer.
Campaign 10 owns scanner-engine tuning; Campaign 11c measures the user-facing
contract around whatever scanner implementation is current.
"""

from __future__ import annotations

import argparse
import json
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

from melodex.library_scan_process import LibraryScanProcess


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Melodex NAS/offline/cancellation qualification scenarios."
    )
    parser.add_argument("--tracks", type=int, default=100)
    parser.add_argument(
        "--cancel-limit-seconds",
        type=float,
        default=2.5,
        help="Maximum acceptable time for hard cancellation of a hung worker.",
    )
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
    count = max(0, int(tracks))
    for index in range(count):
        album = root / f"album-{index // 20:05d}"
        _write_silent_wav(album / f"track-{index:06d}.wav")


def run_scan(
    data_dir: Path,
    roots: list[Path],
    *,
    timeout: float = 30.0,
    command: list[str] | None = None,
    hard_cancel_after: float = 0.15,
) -> tuple[dict[str, Any], list[str], list[str]]:
    done = threading.Event()
    result_box: dict[str, Any] = {}
    errors: list[str] = []
    phases: list[str] = []

    runner = LibraryScanProcess(
        data_dir,
        roots,
        on_progress=lambda payload: phases.append(str(payload.get("phase") or "")),
        on_done=lambda payload: (result_box.setdefault("result", dict(payload or {})), done.set()),
        on_error=lambda error: (errors.append(str(error)), done.set()),
        command=command,
        hard_cancel_after=hard_cancel_after,
    )
    runner.start()
    if not done.wait(timeout):
        runner.shutdown(timeout=0.1)
        raise TimeoutError("isolated scan did not finish within the qualification timeout")
    return dict(result_box.get("result") or {}), phases, errors


def run_hard_cancel_case(
    base: Path,
    *,
    cancel_limit_seconds: float,
) -> dict[str, Any]:
    script = base / "hung_network_worker.py"
    script.write_text(
        "import json, sys, time\n"
        "sys.stdin.readline()\n"
        "print(json.dumps({'type':'progress','payload':{'phase':'discovering'}}), flush=True)\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )

    progress = threading.Event()
    done = threading.Event()
    result_box: dict[str, Any] = {}
    errors: list[str] = []

    runner = LibraryScanProcess(
        base / "cancel-data",
        [base / "simulated-nas"],
        on_progress=lambda payload: progress.set(),
        on_done=lambda payload: (result_box.setdefault("result", dict(payload or {})), done.set()),
        on_error=lambda error: (errors.append(str(error)), done.set()),
        command=[sys.executable, "-u", str(script)],
        hard_cancel_after=0.05,
    )
    runner.start()
    if not progress.wait(3):
        runner.shutdown(timeout=0.1)
        return {
            "passed": False,
            "reason": "hung worker did not reach the progress boundary",
        }

    started = time.monotonic()
    runner.cancel()
    finished = done.wait(max(3.0, cancel_limit_seconds + 1.0))
    elapsed = time.monotonic() - started
    result = dict(result_box.get("result") or {})
    passed = (
        finished
        and not errors
        and bool(result.get("cancelled"))
        and bool(result.get("hard_cancelled"))
        and elapsed <= cancel_limit_seconds
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
    expected = max(0, int(tracks))

    with tempfile.TemporaryDirectory(prefix="melodex-nas-qualification-") as temp:
        base = Path(temp)
        data_dir = base / "data"
        root = base / "nas-music"
        root.mkdir()
        create_library(root, expected)

        first_started = time.monotonic()
        first, first_phases, first_errors = run_scan(data_dir, [root])
        first_elapsed = time.monotonic() - first_started
        first_count = len(list(first.get("tracks") or []))
        first_passed = (
            not first_errors
            and not bool(first.get("cancelled"))
            and first_count == expected
            and {"discovering", "metadata", "saving"}.issubset(set(first_phases))
        )

        offline_root = base / "nas-music-offline"
        root.rename(offline_root)

        offline_started = time.monotonic()
        offline, offline_phases, offline_errors = run_scan(data_dir, [root])
        offline_elapsed = time.monotonic() - offline_started
        offline_count = len(list(offline.get("tracks") or []))
        offline_changes = dict(offline.get("changes") or {})
        offline_passed = (
            not offline_errors
            and not bool(offline.get("cancelled"))
            and offline_count == expected
            and int(offline_changes.get("incomplete_roots") or 0) >= 1
        )

        offline_root.rename(root)
        reconnect_started = time.monotonic()
        reconnect, reconnect_phases, reconnect_errors = run_scan(data_dir, [root])
        reconnect_elapsed = time.monotonic() - reconnect_started
        reconnect_count = len(list(reconnect.get("tracks") or []))
        reconnect_passed = (
            not reconnect_errors
            and not bool(reconnect.get("cancelled"))
            and reconnect_count == expected
            and "saving" in reconnect_phases
        )

        cancel_case = run_hard_cancel_case(
            base,
            cancel_limit_seconds=max(0.1, float(cancel_limit_seconds)),
        )

        cases = {
            "initial_scan": {
                "passed": bool(first_passed),
                "tracks": first_count,
                "expected_tracks": expected,
                "elapsed_seconds": round(first_elapsed, 3),
                "phases": sorted(set(first_phases)),
                "errors": len(first_errors),
            },
            "offline_cache_preservation": {
                "passed": bool(offline_passed),
                "tracks": offline_count,
                "expected_tracks": expected,
                "elapsed_seconds": round(offline_elapsed, 3),
                "incomplete_roots": int(offline_changes.get("incomplete_roots") or 0),
                "phases": sorted(set(offline_phases)),
                "errors": len(offline_errors),
            },
            "reconnect_rescan": {
                "passed": bool(reconnect_passed),
                "tracks": reconnect_count,
                "expected_tracks": expected,
                "elapsed_seconds": round(reconnect_elapsed, 3),
                "phases": sorted(set(reconnect_phases)),
                "errors": len(reconnect_errors),
            },
            "hung_worker_cancel": cancel_case,
        }

        return {
            "campaign": "11c",
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
        print("Melodex Campaign 11c NAS qualification")
        print("--------------------------------------")
        print(f"Synthetic tracks: {result['tracks']:,}")
        for name, case in result["cases"].items():
            status = "PASS" if case.get("passed") else "FAIL"
            elapsed = case.get("elapsed_seconds")
            suffix = f" ({elapsed:.3f}s)" if isinstance(elapsed, (int, float)) else ""
            print(f"{status:4}  {name}{suffix}")
        print("--------------------------------------")
        print("OVERALL:", "PASS" if result["passed"] else "FAIL")

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
