#!/usr/bin/env python3
"""Safely prune proven-unneeded Qt payload from a frozen Melodex bundle."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def _dependencies(path: Path) -> list[str]:
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
    return [
        line.strip().split(" (", 1)[0].strip()
        for line in result.stdout.splitlines()[1:]
        if line.strip()
    ]


def _files(root: Path):
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        yield path


def _find_qpdf_plugins(root: Path) -> list[Path]:
    matches = []
    for path in _files(root):
        lower = path.as_posix().lower()
        if "/plugins/imageformats/" in lower and "qpdf" in path.name.lower():
            matches.append(path)
    return matches


def _qt_pdf_dependents(root: Path) -> list[str]:
    dependents: list[str] = []
    for path in _files(root):
        for dep in _dependencies(path):
            if "qtpdf" in dep.lower():
                dependents.append(path.relative_to(root).as_posix())
                break
    return sorted(set(dependents))


def _qt_pdf_frameworks(root: Path) -> list[Path]:
    matches = []
    for path in root.rglob("QtPdf.framework"):
        if path.is_dir():
            matches.append(path)
    return sorted(set(matches))


def prune_bundle(root: Path) -> dict:
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)

    removed_plugins: list[str] = []
    bytes_removed = 0

    # QtGui's imageformats plugin set includes qpdf even though Melodex never
    # renders PDFs internally. Removing the plugin removes the only known
    # consumer of QtPdf; we verify that assumption from the actual frozen
    # bundle before deleting the framework.
    for plugin in _find_qpdf_plugins(root):
        try:
            bytes_removed += int(plugin.stat().st_size)
        except OSError:
            pass
        removed_plugins.append(plugin.relative_to(root).as_posix())
        plugin.unlink(missing_ok=True)

    dependents = _qt_pdf_dependents(root)
    removed_frameworks: list[str] = []
    if not dependents and shutil.which("otool") is not None:
        for framework in _qt_pdf_frameworks(root):
            size = 0
            for path in framework.rglob("*"):
                if path.is_symlink() or not path.is_file():
                    continue
                try:
                    size += int(path.stat().st_size)
                except OSError:
                    pass
            bytes_removed += size
            removed_frameworks.append(framework.relative_to(root).as_posix())
            shutil.rmtree(framework)

    return {
        "schema_version": 1,
        "removed_qpdf_plugins": removed_plugins,
        "qt_pdf_dependents_after_plugin_removal": dependents,
        "removed_qt_pdf_frameworks": removed_frameworks,
        "bytes_removed": bytes_removed,
        "qt_pdf_pruned": bool(removed_plugins and removed_frameworks and not dependents),
    }


def markdown(report: dict) -> str:
    lines = [
        "# Melodex Qt prune report",
        "",
        f"- qpdf plugins removed: **{len(report.get('removed_qpdf_plugins') or [])}**",
        f"- QtPdf framework removed: **{'yes' if report.get('qt_pdf_pruned') else 'no'}**",
        f"- Bytes removed: **{int(report.get('bytes_removed') or 0):,}**",
        "",
    ]
    dependents = list(report.get("qt_pdf_dependents_after_plugin_removal") or [])
    if dependents:
        lines.extend(["Remaining QtPdf dependents:", ""])
        lines.extend(f"- `{value}`" for value in dependents)
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    report = prune_bundle(args.bundle)
    rendered = markdown(report)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(rendered, "utf-8")
    print(rendered)

    # On macOS, if qpdf was present but QtPdf could not be safely removed, fail
    # rather than silently claiming the optimization succeeded.
    if report["removed_qpdf_plugins"] and not report["qt_pdf_pruned"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
