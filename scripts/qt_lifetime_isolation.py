"""Strict, fresh-interpreter Qt lifetime triage for Fluid GUI batch 2.

No test waiver or automatic retry-to-green: each failing interpreter is counted.
The program itself needs no PySide6; child interpreters need the actual Qt runtime.
"""
from __future__ import annotations

import argparse
import json
from itertools import combinations
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fluid_ci_gate import FLUID_GATE_TESTS  # noqa: E402


def batch_two() -> list[str]:
    gui = FLUID_GATE_TESTS[(len(FLUID_GATE_TESTS) + 1) // 2:]
    specs = gui[7:14]
    expected = (
        "desktop/tests/test_playback_feature.py::test_flow_refinement_requests_new_queue_without_player_access",
        "desktop/tests/test_playback_state.py",
        "desktop/tests/test_gui_redesign.py::test_navigation_shell_changes_before_slow_page_population",
        "desktop/tests/test_gui_redesign.py::test_heavy_pages_build_once_after_navigation_shell",
        "desktop/tests/test_gui_redesign.py::test_rapid_navigation_drops_stale_page_population",
        "desktop/tests/test_gui_redesign.py::test_search_keeps_previous_results_visible_while_refreshing",
        "desktop/tests/test_gui_redesign.py::test_fast_search_never_flashes_delayed_loading_placeholder",
    )
    if tuple(specs) != expected:
        raise RuntimeError("Fluid GUI batch 2 has changed: stop and audit selectors before triage")
    return specs


def selectors(mode: str) -> list[tuple[str, list[str]]]:
    group = batch_two()
    if mode == "group":
        return [("original", group)]
    if mode == "reverse":
        return [("reverse", list(reversed(group)))]
    if mode == "prefix":
        return [(f"prefix-{size}", group[:size]) for size in range(1, len(group) + 1)]
    if mode == "suffix":
        return [(f"suffix-{size}", group[-size:]) for size in range(1, len(group) + 1)]
    if mode == "single":
        return [(f"single-{i+1}", [spec]) for i, spec in enumerate(group)]
    if mode == "triple":
        return [("triple-1-3-4", [group[0], group[2], group[3]])]
    if mode == "quartet":
        first = group[:4]
        return [
            ("quartet-" + "-".join(str(i + 1) for i in chosen),
             [first[i] for i in chosen])
            for size in range(1, 5)
            for chosen in combinations(range(4), size)
        ]
    if mode == "all":
        return (
            [("original", group), ("reverse", list(reversed(group)))]
            + [(f"prefix-{size}", group[:size]) for size in range(1, len(group) + 1)]
            + [(f"suffix-{size}", group[-size:]) for size in range(1, len(group) + 1)]
            + [(f"single-{i+1}", [spec]) for i, spec in enumerate(group)]
        )
    raise ValueError(mode)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONFAULTHANDLER"] = "1"
    current = str(env.get("PYTHONPATH") or "")
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "desktop"), str(ROOT / "scripts")] + ([current] if current else []))
    return env


def trial(label: str, specs: list[str], repeat: int, timeout: int, pin_app: bool = False) -> dict:
    command = [sys.executable, "-m", "pytest", "-q", "--maxfail=1"]
    if pin_app:
        command.extend(("-p", "qt_lifetime_app_probe"))
    command.extend(specs)
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            command, cwd=ROOT, env=_env(), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, errors="replace",
            timeout=timeout, check=False,
        )
        rc, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        rc = -999
        stdout = str(exc.stdout or b"")[-3000:]
        stderr = str(exc.stderr or b"")[-3000:]
    combined = stdout + "\n" + stderr
    return {
        "label": label, "repeat": repeat, "pin_app": bool(pin_app), "exit_code": rc,
        "passed": rc == 0, "elapsed_seconds": round(time.perf_counter() - start, 3),
        "qt_ownership_warning": "QObject: shared QObject was deleted directly" in combined,
        "segmentation_fault": rc == -11 or rc == 139,
        "selectors": list(specs),
        "stdout_tail": stdout[-2200:], "stderr_tail": stderr[-4500:],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("group", "reverse", "prefix", "suffix", "single", "triple", "quartet", "all"), default="group")
    parser.add_argument("--repeats", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--pin-app", action="store_true", help="Pin the QApplication Python wrapper using a test-only pytest plugin")
    parser.add_argument("--strict", action="store_true",
                        help="Exit nonzero if any child test process fails to exit zero")
    args = parser.parse_args(argv)
    if not 1 <= args.repeats <= 100 or not 5 <= args.timeout <= 180:
        parser.error("repeats must be 1..100 and timeout 5..180 seconds")
    specs = selectors(args.mode)
    results = []
    for label, group in specs:
        for i in range(args.repeats):
            item = trial(label, group, i + 1, args.timeout, pin_app=args.pin_app)
            results.append(item)
            print(
                f"{label} {i+1}/{args.repeats}: rc={item['exit_code']} "
                f"QtWarning={item['qt_ownership_warning']} "
                f"elapsed={item['elapsed_seconds']}s",
                flush=True,
            )
    failures = [row for row in results if not row["passed"]]
    report = {
        "schema": 1, "baseline": "Fluid Melodex GUI / interaction 2",
        "mode": args.mode, "pin_app": args.pin_app, "runs": len(results), "failures": len(failures),
        "results": results,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    print(f"Qt lifetime probe: {len(results) - len(failures)}/{len(results)} clean exits; "
          f"{len(failures)} failures. Full evidence: {args.json_out}", flush=True)
    return 1 if args.strict and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
