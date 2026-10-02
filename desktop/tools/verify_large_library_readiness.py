#!/usr/bin/env python3
"""Run the permanent 12,700-track Melodex large-library acceptance suite."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _run_json(script: str, *args: str) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run(
        [sys.executable, str(TOOLS / script), *args, "--json"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{script} failed with exit {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{script} did not emit valid JSON:\n{result.stdout}"
        ) from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{script} returned a non-object JSON value")
    return value


def evaluate(tracks: int) -> dict[str, Any]:
    count = max(1, int(tracks))

    scan = _run_json(
        "profile_library_scan.py",
        "--tracks",
        str(count),
    )
    index = _run_json(
        "profile_library_index.py",
        "--tracks",
        str(count),
    )
    incremental = _run_json(
        "profile_incremental_rescan.py",
        "--tracks",
        str(count),
    )
    catalog = _run_json(
        "profile_library_catalog.py",
        "--tracks",
        str(count),
        "--view",
        "tracks",
    )

    checks = [
        {
            "name": "initial scan indexes every synthetic track",
            "ok": int(scan.get("tracks_indexed") or 0) == count,
            "actual": int(scan.get("tracks_indexed") or 0),
            "expected": count,
        },
        {
            "name": "persistent index reloads the complete library",
            "ok": (
                int(index.get("tracks_loaded") or 0) == count
                and bool(index.get("ready"))
            ),
            "actual": int(index.get("tracks_loaded") or 0),
            "expected": count,
        },
        {
            "name": "unchanged rescan performs zero metadata reads",
            "ok": int(incremental.get("rescan_metadata_reads") or -1) == 0,
            "actual": int(incremental.get("rescan_metadata_reads") or -1),
            "expected": 0,
        },
        {
            "name": "unchanged rescan reuses every metadata record",
            "ok": int(incremental.get("metadata_reused") or 0) == count,
            "actual": int(incremental.get("metadata_reused") or 0),
            "expected": count,
        },
        {
            "name": "unchanged rescan rewrites zero index rows",
            "ok": int(incremental.get("index_rows_rewritten") or -1) == 0,
            "actual": int(incremental.get("index_rows_rewritten") or -1),
            "expected": 0,
        },
        {
            "name": "My Music retains the complete track model",
            "ok": int(catalog.get("track_count") or 0) == count,
            "actual": int(catalog.get("track_count") or 0),
            "expected": count,
        },
        {
            "name": "Albums initial render remains bounded",
            "ok": int(catalog.get("album_widgets") or 0) <= 120,
            "actual": int(catalog.get("album_widgets") or 0),
            "expected": "<= 120",
        },
        {
            "name": "Tracks initial render remains bounded",
            "ok": int(catalog.get("track_widgets") or 0) <= 300,
            "actual": int(catalog.get("track_widgets") or 0),
            "expected": "<= 300",
        },
    ]

    return {
        "schema_version": 1,
        "tracks": count,
        "ok": all(bool(row["ok"]) for row in checks),
        "checks": checks,
        "timings": {
            "scan_total_seconds": scan.get("total_seconds"),
            "index_write_seconds": index.get("write_seconds"),
            "index_read_seconds": index.get("read_seconds"),
            "first_scan_seconds": incremental.get("first_scan_seconds"),
            "unchanged_rescan_seconds": incremental.get("unchanged_rescan_seconds"),
            "catalog_total_seconds": catalog.get("total_seconds"),
            "catalog_initial_with_events_seconds": catalog.get(
                "initial_with_events_seconds"
            ),
        },
        "raw": {
            "scan": scan,
            "index": index,
            "incremental": incremental,
            "catalog": catalog,
        },
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Melodex large-library acceptance",
        "",
        f"- Synthetic tracks: **{int(report.get('tracks') or 0):,}**",
        f"- Result: **{'PASS' if report.get('ok') else 'FAIL'}**",
        "",
        "| Check | Actual | Expected | Result |",
        "| --- | ---: | ---: | --- |",
    ]
    for row in list(report.get("checks") or []):
        lines.append(
            "| {name} | {actual} | {expected} | {result} |".format(
                name=row["name"],
                actual=row["actual"],
                expected=row["expected"],
                result="PASS" if row["ok"] else "FAIL",
            )
        )

    lines.extend(["", "## Timings (informational)", ""])
    for key, value in dict(report.get("timings") or {}).items():
        lines.append(f"- {key}: **{value}**")
    lines.extend(
        [
            "",
            "Timing values are recorded for comparison but are not hard CI limits; "
            "hosted-runner performance varies. Correctness and bounded-work "
            "invariants are the release gate.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracks", type=int, default=12_700)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    report = evaluate(args.tracks)
    rendered = markdown(report)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(rendered, "utf-8")

    print(rendered)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
