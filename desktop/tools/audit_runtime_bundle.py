#!/usr/bin/env python3
"""Summarize non-Qt runtime payload in a frozen Melodex bundle."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


CATEGORIES = {
    "numpy": ("numpy",),
    "python_runtime": ("python.framework", "python3__dot__", "python312", "python3.dll"),
    "openssl": ("libcrypto", "libssl", "openssl"),
    "keyring": ("keyring",),
    "requests_stack": ("certifi", "charset_normalizer", "urllib3", "requests"),
    "shiboken": ("shiboken6",),
    "melodex_resources": ("/resources/melodex/",),
}


def _files(root: Path):
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            size = int(path.stat().st_size)
        except OSError:
            continue
        yield path, size


def audit_runtime_payload(root: Path) -> dict:
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)

    totals = defaultdict(int)
    examples: dict[str, list[str]] = defaultdict(list)
    uncategorized = 0

    for path, size in _files(root):
        relative = "/" + path.relative_to(root).as_posix().lower()
        if "/pyside6/" in relative:
            continue

        matched = False
        for category, markers in CATEGORIES.items():
            if any(marker in relative for marker in markers):
                totals[category] += size
                if len(examples[category]) < 12:
                    examples[category].append(path.relative_to(root).as_posix())
                matched = True
                break
        if not matched:
            uncategorized += size

    return {
        "schema_version": 1,
        "bundle": root.name,
        "categories": {
            category: {
                "bytes": int(totals.get(category, 0)),
                "examples": examples.get(category, []),
            }
            for category in CATEGORIES
        },
        "uncategorized_non_qt_bytes": int(uncategorized),
    }


def markdown(report: dict) -> str:
    lines = [
        "# Melodex non-Qt runtime audit",
        "",
        "| Component | Size (bytes) |",
        "| --- | ---: |",
    ]
    for category, data in dict(report.get("categories") or {}).items():
        lines.append(f"| {category} | {int(data.get('bytes') or 0):,} |")
    lines.append(
        f"| uncategorized non-Qt | {int(report.get('uncategorized_non_qt_bytes') or 0):,} |"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    report = audit_runtime_payload(args.bundle)
    rendered = markdown(report)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(rendered, "utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
