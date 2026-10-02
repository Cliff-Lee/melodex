#!/usr/bin/env python3
"""Audit native Qt dependencies inside a frozen Melodex bundle.

On macOS this uses otool to show which bundled binaries pull in heavyweight
frameworks that Melodex does not import directly. On other platforms it still
lists matching payload paths so CI gives us a useful inventory.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from collections import defaultdict, deque
from pathlib import Path
from typing import Iterable


TARGETS = ("QtPdf", "QtQuick", "QtQml", "QtQmlModels")


def _bundle_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        yield path


def _native_dependencies(path: Path) -> list[str]:
    if shutil.which("otool") is None:
        return []
    try:
        result = subprocess.run(
            ["otool", "-L", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    deps: list[str] = []
    for line in result.stdout.splitlines()[1:]:
        value = line.strip().split(" (", 1)[0].strip()
        if value:
            deps.append(value)
    return deps


def _target_from_dependency(value: str) -> str | None:
    lowered = value.lower()
    for target in sorted(TARGETS, key=len, reverse=True):
        if target.lower() in lowered:
            return target
    return None


def audit_bundle(root: Path) -> dict:
    root = Path(root).resolve()
    files = list(_bundle_files(root))
    rel = {path: path.relative_to(root).as_posix() for path in files}

    payloads: dict[str, list[str]] = {target: [] for target in TARGETS}
    for path in files:
        lower = rel[path].lower()
        for target in TARGETS:
            if target.lower() in lower:
                payloads[target].append(rel[path])

    dependencies: dict[str, list[str]] = {}
    direct_dependents: dict[str, list[str]] = defaultdict(list)
    for path in files:
        deps = _native_dependencies(path)
        if not deps:
            continue
        dependencies[rel[path]] = deps
        for dep in deps:
            target = _target_from_dependency(dep)
            if target:
                direct_dependents[target].append(rel[path])

    # Produce a small reverse-dependency view. The direct list is the important
    # result for pruning: removing a framework is only safe after its dependents
    # are either removed too or proved unnecessary.
    return {
        "schema_version": 1,
        "bundle": root.name,
        "otool_available": shutil.which("otool") is not None,
        "targets": {
            target: {
                "payloads": sorted(payloads[target]),
                "direct_dependents": sorted(set(direct_dependents[target])),
            }
            for target in TARGETS
        },
        "interesting_plugins": sorted(
            value
            for value in rel.values()
            if "/plugins/" in value.lower()
            and any(
                marker in value.lower()
                for marker in (
                    "imageformats",
                    "multimedia",
                    "platforms",
                    "networkinformation",
                    "tls",
                )
            )
        ),
    }


def markdown(report: dict) -> str:
    lines = [
        "# Melodex Qt dependency audit",
        "",
        f"- Bundle: **{report.get('bundle', '')}**",
        f"- Native dependency inspection: **{'yes' if report.get('otool_available') else 'no'}**",
        "",
    ]
    targets = dict(report.get("targets") or {})
    for target in TARGETS:
        data = dict(targets.get(target) or {})
        payloads = list(data.get("payloads") or [])
        dependents = list(data.get("direct_dependents") or [])
        lines.extend(
            [
                f"## {target}",
                "",
                f"- Matching payloads: **{len(payloads)}**",
                f"- Direct bundled dependents: **{len(dependents)}**",
            ]
        )
        if dependents:
            lines.extend(["", "Direct dependents:"])
            lines.extend(f"- `{value}`" for value in dependents)
        if payloads:
            lines.extend(["", "Payloads:"])
            lines.extend(f"- `{value}`" for value in payloads[:30])
        lines.append("")

    plugins = list(report.get("interesting_plugins") or [])
    lines.extend(["## Relevant Qt plugins", ""])
    lines.extend(f"- `{value}`" for value in plugins)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    report = audit_bundle(args.bundle)
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
