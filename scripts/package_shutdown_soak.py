#!/usr/bin/env python3
"""Repeated native packaged GUI launch and close with isolated profiles.

Uses the existing strict packaged startup probe. No real library or
credentials are accessed, and Qt process-exit failures are never suppressed.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from packaged_startup_probe import _run_launch


def qualify(executable: Path, *, repeats: int = 12, appimage: bool = False,
            timeout: float = 60.0) -> dict:
    executable = Path(executable).resolve()
    if not executable.is_file():
        raise FileNotFoundError("Packaged Melodex executable was not found")
    if not 2 <= repeats <= 100:
        raise ValueError("Expected 2..100 independent packaged launches")

    attempts = []
    with tempfile.TemporaryDirectory(prefix="melodex-package-qt-close-") as directory:
        root = Path(directory)
        for i in range(repeats):
            # First launch and warm relaunch reuse a private profile.
            # The next pair starts with another private profile.
            profile = root / ("profile-" + str(i // 2))
            trace = root / ("startup-" + str(i + 1) + ".json")
            measurement = _run_launch(
                executable, profile, trace,
                appimage=appimage, timeout_seconds=timeout,
            )
            if "first_event_loop_turn" not in measurement["phases"]:
                raise RuntimeError("Packaged process did not reach the GUI event loop")
            attempts.append({
                "iteration": i + 1,
                "profile": "fresh" if i % 2 == 0 else "warm",
                "process_wall_ms": measurement["process_wall_ms"],
                "native_exit_zero": True,
            })
    return {
        "schema": 1,
        "scope": "packaged startup, Qt close, native zero exit (not audible playback)",
        "executable_name": executable.name,
        "appimage": bool(appimage),
        "successful_exits": len(attempts),
        "requested_runs": repeats,
        "attempts": attempts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--appimage", action="store_true")
    parser.add_argument("--repeats", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = qualify(
        args.executable, repeats=args.repeats,
        appimage=args.appimage, timeout=args.timeout,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", "utf-8")
    print(
        f"Packaged Qt close: {result['successful_exits']}/"
        f"{result['requested_runs']} clean native exits"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
