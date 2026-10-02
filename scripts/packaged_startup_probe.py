from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


REQUIRED_PHASES = (
    "app_module_ready",
    "qapplication_ready",
    "single_instance_ready",
    "main_window_import_ready",
    "providers_ready",
    "user_state_ready",
    "core_services_ready",
    "player_ready",
    "ui_built",
    "home_ready",
    "bridge_start_scheduled",
    "main_window_construct_ready",
    "window_show_requested",
    "first_event_loop_turn",
)


def _phase_map(trace: dict[str, Any]) -> dict[str, dict[str, float]]:
    rows: dict[str, dict[str, float]] = {}
    for raw in list(trace.get("events") or []):
        if not isinstance(raw, dict):
            continue
        phase = str(raw.get("phase") or "").strip()
        if not phase:
            continue
        rows[phase] = {
            "elapsed_ms": float(raw.get("elapsed_ms") or 0.0),
            "delta_ms": float(raw.get("delta_ms") or 0.0),
        }
    return rows


def _command(executable: Path, *, appimage: bool) -> list[str]:
    command = [str(executable)]
    if appimage:
        command.append("--appimage-extract-and-run")
    return command


def _run_launch(
    executable: Path,
    data_dir: Path,
    trace_path: Path,
    *,
    appimage: bool = False,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    env = dict(os.environ)
    env.update(
        {
            "MELODEX_DATA_DIR": str(data_dir),
            "MELODEX_STARTUP_TRACE": str(trace_path),
            "MELODEX_STARTUP_PROBE_EXIT": "1",
            "QT_QPA_PLATFORM": str(env.get("QT_QPA_PLATFORM") or "offscreen"),
        }
    )

    started = time.perf_counter()
    process = subprocess.Popen(
        _command(executable, appimage=appimage),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    trace_seen_at: float | None = None
    deadline = time.monotonic() + max(5.0, float(timeout_seconds))
    try:
        while time.monotonic() < deadline:
            if trace_path.is_file():
                trace_seen_at = time.perf_counter()
                break
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise RuntimeError(
                    "Packaged Melodex exited before producing a startup trace "
                    f"(exit {process.returncode}).\n"
                    f"stdout: {stdout[-1500:]}\n"
                    f"stderr: {stderr[-1500:]}"
                )
            time.sleep(0.01)
        else:
            process.kill()
            stdout, stderr = process.communicate()
            raise RuntimeError(
                "Packaged Melodex did not produce a startup trace before timeout.\n"
                f"stdout: {stdout[-1500:]}\n"
                f"stderr: {stderr[-1500:]}"
            )

        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()

        if process.returncode not in (0, None):
            raise RuntimeError(
                f"Packaged Melodex returned {process.returncode} after tracing.\n"
                f"stdout: {stdout[-1500:]}\n"
                f"stderr: {stderr[-1500:]}"
            )
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    launch_to_trace_ms = (
        (trace_seen_at - started) * 1000.0 if trace_seen_at is not None else 0.0
    )
    process_wall_ms = (time.perf_counter() - started) * 1000.0

    trace = json.loads(trace_path.read_text("utf-8"))
    phases = _phase_map(trace)
    missing = [phase for phase in REQUIRED_PHASES if phase not in phases]
    if missing:
        raise RuntimeError(
            "Packaged startup trace is missing phases: " + ", ".join(missing)
        )

    internal_ms = float(trace.get("total_ms") or 0.0)
    bootloader_overhead_ms = max(0.0, launch_to_trace_ms - internal_ms)
    return {
        "launch_to_first_event_loop_ms": round(launch_to_trace_ms, 3),
        "process_wall_ms": round(process_wall_ms, 3),
        "internal_timeline_ms": round(internal_ms, 3),
        "packaging_bootloader_overhead_ms": round(bootloader_overhead_ms, 3),
        "phases": phases,
    }


def run_probe(
    executable: Path,
    *,
    appimage: bool = False,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    executable = executable.resolve()
    if not executable.is_file():
        raise FileNotFoundError(f"packaged executable not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="melodex-packaged-startup-") as temporary:
        root = Path(temporary)

        first_profile = root / "profile-a"
        fresh = _run_launch(
            executable,
            first_profile,
            root / "fresh.json",
            appimage=appimage,
            timeout_seconds=timeout_seconds,
        )
        warm = _run_launch(
            executable,
            first_profile,
            root / "warm.json",
            appimage=appimage,
            timeout_seconds=timeout_seconds,
        )

        profile_cold = _run_launch(
            executable,
            root / "profile-b",
            root / "profile-cold.json",
            appimage=appimage,
            timeout_seconds=timeout_seconds,
        )

    warm_ms = float(warm["launch_to_first_event_loop_ms"])
    profile_cold_ms = float(profile_cold["launch_to_first_event_loop_ms"])
    return {
        "schema": 1,
        "platform": sys.platform,
        "executable_name": executable.name,
        "appimage": bool(appimage),
        "fresh_profile": fresh,
        "warm_profile": warm,
        "profile_cold_profile": profile_cold,
        "comparison": {
            "profile_cold_over_warm_ms": round(profile_cold_ms - warm_ms, 3),
            "profile_cold_over_warm_ratio": round(
                profile_cold_ms / warm_ms if warm_ms else 0.0,
                4,
            ),
            "warm_packaging_overhead_ms": float(
                warm["packaging_bootloader_overhead_ms"]
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure startup of a frozen/packaged Melodex executable from "
            "process launch to the first Qt event-loop turn."
        )
    )
    parser.add_argument("executable", type=Path)
    parser.add_argument(
        "--appimage",
        action="store_true",
        help="launch with --appimage-extract-and-run for FUSE-less CI",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = run_probe(
        args.executable,
        appimage=args.appimage,
        timeout_seconds=args.timeout,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
