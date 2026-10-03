#!/usr/bin/env python3
"""Run Ruff as a debt ratchet instead of suppressing whole files."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "scripts" / "ruff_baseline.json"
TARGETS = (
    "desktop/melodex",
    "scripts/codebase_health.py",
    "scripts/codebase_guardrails.py",
    "scripts/ruff_guardrail.py",
)


def source_line(relative: str, row: int) -> str:
    lines = (ROOT / relative).read_text(encoding="utf-8").splitlines()
    return lines[row - 1].strip() if 1 <= row <= len(lines) else ""


def fingerprint(issue: dict[str, object]) -> tuple[str, str, str, str]:
    filename = Path(str(issue["filename"]))
    try:
        relative = filename.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        relative = filename.as_posix()

    location = issue.get("location")
    row = int(location.get("row", 0)) if isinstance(location, dict) else 0
    return (
        relative,
        str(issue.get("code", "")),
        str(issue.get("message", "")),
        source_line(relative, row),
    )


def main() -> int:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    allowed = {
        (
            item["path"],
            item["code"],
            item["message"],
            item["source"],
        )
        for item in baseline["allowed"]
    }

    command = [
        "ruff",
        "check",
        "--config",
        "desktop/pyproject.toml",
        "--output-format",
        "json",
        *TARGETS,
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode not in (0, 1):
        print(completed.stdout, end="")
        print(completed.stderr, end="")
        return completed.returncode

    issues = json.loads(completed.stdout or "[]")
    current = {fingerprint(issue) for issue in issues}
    unexpected = sorted(current - allowed)
    resolved = sorted(allowed - current)

    if resolved:
        print("Ruff baseline debt resolved since P12b:")
        for path, code, message, _source in resolved:
            print(f"- {path}: {code} {message}")
        print("The stale baseline entries can be removed in a focused cleanup.")

    if unexpected:
        print("New Ruff findings are not allowed by the P12b debt baseline:")
        for path, code, message, source in unexpected:
            print(f"- {path}: {code} {message}")
            if source:
                print(f"  {source}")
        return 1

    print(f"OK: Ruff found {len(current)} known issue(s) and no new correctness debt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
