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
        relative = "/" + path.relative_to(root).as_posix().lower()
        if "/qtpdf.framework/" in relative:
            continue
        for dep in _dependencies(path):
            if "qtpdf" in dep.lower():
                dependents.append(path.relative_to(root).as_posix())
                break
    return sorted(set(dependents))


QML_FAMILY = (
    "QtQuick",
    "QtQml",
    "QtQmlMeta",
    "QtQmlModels",
    "QtQmlWorkerScript",
)


def _frameworks_named(root: Path, names: tuple[str, ...]) -> list[Path]:
    matches: list[Path] = []
    for name in names:
        for path in root.rglob(f"{name}.framework"):
            if path.is_dir():
                matches.append(path)
    return sorted(set(matches))


def _qt_pdf_frameworks(root: Path) -> list[Path]:
    return _frameworks_named(root, ("QtPdf",))


def _family_dependents(root: Path, names: tuple[str, ...]) -> list[str]:
    markers = tuple(name.lower() for name in names)
    family_paths = tuple(f"/{name.lower()}.framework/" for name in names)
    dependents: list[str] = []
    for path in _files(root):
        relative = "/" + path.relative_to(root).as_posix().lower()
        if any(marker in relative for marker in family_paths):
            continue
        for dep in _dependencies(path):
            lower = dep.lower()
            if any(marker in lower for marker in markers):
                dependents.append(path.relative_to(root).as_posix())
                break
    return sorted(set(dependents))


def _remove_tree(path: Path) -> int:
    size = 0
    for child in path.rglob("*"):
        if child.is_symlink() or not child.is_file():
            continue
        try:
            size += int(child.stat().st_size)
        except OSError:
            pass
    shutil.rmtree(path)
    return size


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
            bytes_removed += _remove_tree(framework)
            removed_frameworks.append(framework.relative_to(root).as_posix())

    removed_virtual_keyboard: list[str] = []
    for path in list(_files(root)):
        lower = path.as_posix().lower()
        if (
            "/plugins/platforminputcontexts/" in lower
            and "virtualkeyboard" in path.name.lower()
        ):
            try:
                bytes_removed += int(path.stat().st_size)
            except OSError:
                pass
            removed_virtual_keyboard.append(path.relative_to(root).as_posix())
            path.unlink(missing_ok=True)

    removed_vk_frameworks: list[str] = []
    for framework in _frameworks_named(
        root,
        ("QtVirtualKeyboard", "QtVirtualKeyboardQml"),
    ):
        bytes_removed += _remove_tree(framework)
        removed_vk_frameworks.append(framework.relative_to(root).as_posix())

    qml_dependents = _family_dependents(root, QML_FAMILY)
    removed_qml_frameworks: list[str] = []
    if not qml_dependents and shutil.which("otool") is not None:
        for framework in _frameworks_named(root, QML_FAMILY):
            bytes_removed += _remove_tree(framework)
            removed_qml_frameworks.append(framework.relative_to(root).as_posix())

    return {
        "schema_version": 1,
        "removed_qpdf_plugins": removed_plugins,
        "qt_pdf_dependents_after_plugin_removal": dependents,
        "removed_qt_pdf_frameworks": removed_frameworks,
        "bytes_removed": bytes_removed,
        "qt_pdf_pruned": bool(removed_plugins and removed_frameworks and not dependents),
        "removed_virtual_keyboard_plugins": removed_virtual_keyboard,
        "removed_virtual_keyboard_frameworks": removed_vk_frameworks,
        "qml_family_dependents_after_virtual_keyboard_removal": qml_dependents,
        "removed_qml_frameworks": removed_qml_frameworks,
        "qml_family_pruned": bool(
            (removed_virtual_keyboard or removed_vk_frameworks)
            and removed_qml_frameworks
            and not qml_dependents
        ),
    }


def markdown(report: dict) -> str:
    lines = [
        "# Melodex Qt prune report",
        "",
        f"- qpdf plugins removed: **{len(report.get('removed_qpdf_plugins') or [])}**",
        f"- QtPdf framework removed: **{'yes' if report.get('qt_pdf_pruned') else 'no'}**",
        f"- Virtual keyboard/QML chain removed: **{'yes' if report.get('qml_family_pruned') else 'no'}**",
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
    if (
        report["removed_virtual_keyboard_plugins"]
        or report["removed_virtual_keyboard_frameworks"]
    ) and not report["qml_family_pruned"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
