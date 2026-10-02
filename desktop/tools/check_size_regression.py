#!/usr/bin/env python3
"""Fail CI when a desktop package grows materially beyond the accepted baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _human(value: int) -> str:
    size = float(max(0, int(value)))
    units = ("B", "KB", "MB", "GB")
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{size:.1f} GB"


def _percent(actual: int, baseline: int) -> float:
    if baseline <= 0:
        return 0.0
    return ((actual - baseline) / baseline) * 100.0


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def evaluate(
    *,
    profile: str,
    baselines: dict[str, Any],
    bundle_report: dict[str, Any] | None = None,
    portable: Path | None = None,
    installer: Path | None = None,
    deb: Path | None = None,
    appimage: Path | None = None,
) -> dict[str, Any]:
    tolerance = float(baselines.get("tolerance_percent") or 0.0)
    profiles = dict(baselines.get("profiles") or {})
    baseline = dict(profiles.get(profile) or {})
    if not baseline:
        raise KeyError(f"unknown bundle-size profile: {profile}")

    actual: dict[str, int] = {}
    if bundle_report is not None:
        actual["installed_bytes"] = int(bundle_report.get("total_bytes") or 0)
        archive = bundle_report.get("archive")
        if isinstance(archive, dict):
            actual["archive_bytes"] = int(archive.get("bytes") or 0)
    if portable is not None:
        actual["portable_zip_bytes"] = int(Path(portable).stat().st_size)
    if installer is not None:
        actual["installer_bytes"] = int(Path(installer).stat().st_size)
    if deb is not None:
        actual["deb_bytes"] = int(Path(deb).stat().st_size)
    if appimage is not None:
        actual["appimage_bytes"] = int(Path(appimage).stat().st_size)

    rows: list[dict[str, Any]] = []
    failed = False
    for metric, baseline_value_raw in baseline.items():
        baseline_value = int(baseline_value_raw)
        if metric not in actual:
            raise ValueError(f"missing actual metric for {profile}: {metric}")
        actual_value = int(actual[metric])
        limit = int(round(baseline_value * (1.0 + tolerance / 100.0)))
        growth = _percent(actual_value, baseline_value)
        ok = actual_value <= limit
        failed = failed or not ok
        rows.append(
            {
                "metric": metric,
                "baseline_bytes": baseline_value,
                "actual_bytes": actual_value,
                "growth_percent": growth,
                "limit_bytes": limit,
                "ok": ok,
            }
        )

    return {
        "schema_version": 1,
        "profile": profile,
        "tolerance_percent": tolerance,
        "ok": not failed,
        "metrics": rows,
    }


def markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Melodex size regression check",
        "",
        f"- Profile: **{result.get('profile', '')}**",
        f"- Allowed growth: **{float(result.get('tolerance_percent') or 0):.1f}%**",
        f"- Result: **{'PASS' if result.get('ok') else 'FAIL'}**",
        "",
        "| Metric | Baseline | Actual | Change | Limit |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in list(result.get("metrics") or []):
        lines.append(
            "| {metric} | {baseline} | {actual} | {growth:+.1f}% | {limit} |".format(
                metric=row["metric"],
                baseline=_human(int(row["baseline_bytes"])),
                actual=_human(int(row["actual_bytes"])),
                growth=float(row["growth_percent"]),
                limit=_human(int(row["limit_bytes"])),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument(
        "--baselines",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "bundle-size-baselines.json",
    )
    parser.add_argument("--bundle-report", type=Path)
    parser.add_argument("--portable", type=Path)
    parser.add_argument("--installer", type=Path)
    parser.add_argument("--deb", type=Path)
    parser.add_argument("--appimage", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    baselines = _load_json(args.baselines)
    report = _load_json(args.bundle_report) if args.bundle_report else None
    result = evaluate(
        profile=args.profile,
        baselines=baselines,
        bundle_report=report,
        portable=args.portable,
        installer=args.installer,
        deb=args.deb,
        appimage=args.appimage,
    )
    rendered = markdown(result)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2) + "\n", "utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(rendered, "utf-8")

    print(rendered)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
