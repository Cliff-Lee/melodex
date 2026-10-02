#!/usr/bin/env python3
"""Report macOS signing/notarization trust state for a Melodex distribution."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def _run(command: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    output = "\n".join(
        part.strip()
        for part in (result.stdout, result.stderr)
        if part and part.strip()
    )
    return int(result.returncode), output


def _signature_mode(details: str) -> str:
    lowered = details.lower()
    if "signature=adhoc" in lowered:
        return "ad-hoc"
    if "developer id application:" in lowered:
        return "developer-id"
    return "unknown"


def _hardened_runtime(details: str) -> bool:
    lowered = details.lower()
    return "runtime" in lowered and "flags=" in lowered


def build_report(app: Path, dmg: Path | None = None) -> dict[str, Any]:
    app = Path(app).resolve()
    if not app.is_dir():
        raise FileNotFoundError(app)

    verify_code, verify_output = _run(
        ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)]
    )
    details_code, details_output = _run(
        ["codesign", "-dv", "--verbose=4", str(app)]
    )
    gatekeeper_code, gatekeeper_output = _run(
        ["spctl", "--assess", "--type", "execute", "--verbose=4", str(app)]
    )

    mode = _signature_mode(details_output)
    result: dict[str, Any] = {
        "schema_version": 1,
        "app": app.name,
        "signature_mode": mode,
        "codesign_valid": verify_code == 0,
        "hardened_runtime": _hardened_runtime(details_output),
        "gatekeeper_app_accepted": gatekeeper_code == 0,
        "codesign_details": details_output,
        "codesign_verify_output": verify_output,
        "gatekeeper_app_output": gatekeeper_output,
        "dmg": None,
    }

    if dmg is not None:
        dmg = Path(dmg).resolve()
        if not dmg.is_file():
            raise FileNotFoundError(dmg)
        dmg_code, dmg_output = _run(
            ["codesign", "--verify", "--strict", "--verbose=2", str(dmg)]
        )
        staple_code, staple_output = _run(
            ["xcrun", "stapler", "validate", str(dmg)]
        )
        gatekeeper_dmg_code, gatekeeper_dmg_output = _run(
            [
                "spctl",
                "--assess",
                "--type",
                "open",
                "--context",
                "context:primary-signature",
                "--verbose=4",
                str(dmg),
            ]
        )
        result["dmg"] = {
            "name": dmg.name,
            "codesign_valid": dmg_code == 0,
            "stapled": staple_code == 0,
            "gatekeeper_accepted": gatekeeper_dmg_code == 0,
            "codesign_output": dmg_output,
            "stapler_output": staple_output,
            "gatekeeper_output": gatekeeper_dmg_output,
        }

    distribution_ready = (
        result["signature_mode"] == "developer-id"
        and bool(result["codesign_valid"])
        and bool(result["hardened_runtime"])
    )
    dmg_result = result.get("dmg")
    if isinstance(dmg_result, dict):
        distribution_ready = (
            distribution_ready
            and bool(dmg_result.get("codesign_valid"))
            and bool(dmg_result.get("stapled"))
            and bool(dmg_result.get("gatekeeper_accepted"))
        )
    result["distribution_ready"] = distribution_ready
    return result


def markdown(report: dict[str, Any]) -> str:
    dmg = report.get("dmg")
    lines = [
        "# Melodex macOS trust report",
        "",
        f"- App signature: **{report.get('signature_mode', 'unknown')}**",
        f"- App codesign verification: **{'PASS' if report.get('codesign_valid') else 'FAIL'}**",
        f"- Hardened runtime: **{'yes' if report.get('hardened_runtime') else 'no'}**",
        f"- Gatekeeper app assessment: **{'accepted' if report.get('gatekeeper_app_accepted') else 'not accepted'}**",
    ]
    if isinstance(dmg, dict):
        lines.extend(
            [
                f"- DMG codesign verification: **{'PASS' if dmg.get('codesign_valid') else 'FAIL'}**",
                f"- Notarization ticket stapled: **{'yes' if dmg.get('stapled') else 'no'}**",
                f"- Gatekeeper DMG assessment: **{'accepted' if dmg.get('gatekeeper_accepted') else 'not accepted'}**",
            ]
        )
    lines.extend(
        [
            f"- Distribution trust ready: **{'YES' if report.get('distribution_ready') else 'NO'}**",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("app", type=Path)
    parser.add_argument("--dmg", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--require-distribution-trust", action="store_true")
    args = parser.parse_args()

    report = build_report(args.app, args.dmg)
    rendered = markdown(report)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(rendered, "utf-8")

    print(rendered)
    if args.require_distribution_trust and not report["distribution_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
