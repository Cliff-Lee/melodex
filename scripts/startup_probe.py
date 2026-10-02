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

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
SCRIPTS = ROOT / "scripts"
for entry in (DESKTOP, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from large_library_probe import synthetic_catalog  # noqa: E402
from melodex.library_index import LocalLibraryIndex  # noqa: E402


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
    result: dict[str, dict[str, float]] = {}
    for row in list(trace.get("events") or []):
        if not isinstance(row, dict):
            continue
        phase = str(row.get("phase") or "")
        if not phase:
            continue
        result[phase] = {
            "elapsed_ms": float(row.get("elapsed_ms") or 0.0),
            "delta_ms": float(row.get("delta_ms") or 0.0),
        }
    return result


def _run_launch(
    data_dir: Path,
    trace_path: Path,
    *,
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["MELODEX_DATA_DIR"] = str(data_dir)
    env["MELODEX_STARTUP_TRACE"] = str(trace_path)
    env["MELODEX_STARTUP_PROBE_EXIT"] = "1"
    existing_pythonpath = str(env.get("PYTHONPATH") or "")
    env["PYTHONPATH"] = (
        str(DESKTOP)
        if not existing_pythonpath
        else str(DESKTOP) + os.pathsep + existing_pythonpath
    )

    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, "-m", "melodex.app"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=max(5.0, float(timeout_seconds)),
        check=False,
    )
    wall_ms = (time.perf_counter() - started) * 1000.0

    if completed.returncode != 0:
        raise RuntimeError(
            "Melodex startup probe failed with exit code "
            f"{completed.returncode}: {completed.stderr[-2000:]}"
        )
    if not trace_path.exists():
        raise RuntimeError("Melodex startup probe did not produce a trace")

    trace = json.loads(trace_path.read_text("utf-8"))
    phases = _phase_map(trace)
    missing = [phase for phase in REQUIRED_PHASES if phase not in phases]
    if missing:
        raise RuntimeError(
            "Melodex startup trace is missing phases: " + ", ".join(missing)
        )

    return {
        "wall_ms": round(wall_ms, 3),
        "timeline_total_ms": round(float(trace.get("total_ms") or 0.0), 3),
        "phases": phases,
    }


def _seed_cached_library(data_dir: Path, track_count: int) -> None:
    root = data_dir / "synthetic-library"
    catalog = synthetic_catalog(track_count)

    remapped: list[dict[str, Any]] = []
    for index, source in enumerate(catalog):
        track = dict(source)
        relative = Path(
            f"artist-{index // 40:05d}",
            f"album-{index // 10:06d}",
            f"track-{index:07d}.flac",
        )
        local_path = root / relative
        track["local_path"] = str(local_path)
        track["track_id"] = str(local_path)
        remapped.append(track)

    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "sources.json").write_text(
        json.dumps({"local_roots": [str(root)]}, indent=2) + "\n",
        "utf-8",
    )

    index = LocalLibraryIndex(data_dir / "library-index.sqlite3")
    index.sync_roots([root])
    result = index.replace_scan(
        [root],
        {
            "root_states": [
                {
                    "path": str(root),
                    "available": True,
                    "complete": True,
                }
            ],
            "tracks": remapped,
        },
    )
    if int(result.get("tracks_persisted") or 0) != int(track_count):
        raise RuntimeError(
            "Synthetic startup index did not persist the expected track count"
        )


def run_probe(
    *,
    track_count: int = 12_700,
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    track_count = max(100, int(track_count))

    with tempfile.TemporaryDirectory(prefix="melodex-startup-") as temp:
        root = Path(temp)

        empty_profile = root / "empty-profile"
        fresh = _run_launch(
            empty_profile,
            root / "fresh-empty.json",
            timeout_seconds=timeout_seconds,
        )
        warm = _run_launch(
            empty_profile,
            root / "warm-empty.json",
            timeout_seconds=timeout_seconds,
        )

        # Separate "new Melodex profile" work from an OS-cold Python/Qt import.
        # By this point code pages/import caches are warm, but this data
        # directory has never been opened by Melodex.
        profile_cold_dir = root / "profile-cold-after-code-warmup"
        profile_cold = _run_launch(
            profile_cold_dir,
            root / "profile-cold.json",
            timeout_seconds=timeout_seconds,
        )

        large_profile = root / "large-profile"
        # Bootstrap bundled providers and small persistent stores outside the
        # measured large-library run, then add the synthetic cached index.
        _run_launch(
            large_profile,
            root / "large-bootstrap.json",
            timeout_seconds=timeout_seconds,
        )
        _seed_cached_library(large_profile, track_count)
        large_cached = _run_launch(
            large_profile,
            root / "large-cached.json",
            timeout_seconds=timeout_seconds,
        )

    fresh_total = float(fresh["timeline_total_ms"])
    warm_total = float(warm["timeline_total_ms"])
    profile_cold_total = float(profile_cold["timeline_total_ms"])
    large_total = float(large_cached["timeline_total_ms"])
    warm_gain = max(0.0, fresh_total - warm_total)

    return {
        "schema": 1,
        "cached_library_tracks": track_count,
        "fresh_profile": fresh,
        "warm_profile": warm,
        "profile_cold_profile": profile_cold,
        "large_cached_profile": large_cached,
        "comparison": {
            "warm_vs_fresh_saved_ms": round(warm_gain, 3),
            "warm_vs_fresh_ratio": round(
                warm_total / fresh_total if fresh_total else 0.0,
                4,
            ),
            "profile_cold_over_warm_ms": round(
                profile_cold_total - warm_total,
                3,
            ),
            "profile_cold_over_warm_ratio": round(
                profile_cold_total / warm_total if warm_total else 0.0,
                4,
            ),
            "large_cached_over_warm_ms": round(large_total - warm_total, 3),
            "large_cached_over_warm_ratio": round(
                large_total / warm_total if warm_total else 0.0,
                4,
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure Melodex process-to-first-event-loop startup phases for "
            "OS-cold fresh, warm, code-warm/profile-cold and large cached-library profiles."
        )
    )
    parser.add_argument("--tracks", type=int, default=12_700)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = run_probe(
        track_count=args.tracks,
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
