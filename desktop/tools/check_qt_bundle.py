#!/usr/bin/env python3
"""Validate that frozen Melodex contains only the Qt families it actually needs."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_PYSIDE_MODULES = (
    "qtcore",
    "qtgui",
    "qtwidgets",
    "qtmultimedia",
)

FORBIDDEN_MARKERS = (
    "qtwebengine",
    "/qt/qml/",
    "/pyside6/qtqml",
    "/pyside6/qtquick",
    "qtquick3d",
    "/pyside6/qtdesigner",
    "/pyside6/qtpdf",
    "/pyside6/qtcharts",
    "qtdatavisualization",
    "qtgraphs",
    "qtbluetooth",
    "/pyside6/qtnfc",
    "qtsensors",
    "qtserialbus",
    "qtserialport",
    "/pyside6/qtsql",
    "/qt/plugins/sqldrivers/",
)


def _paths(root: Path) -> list[str]:
    values: list[str] = []
    for path in root.rglob("*"):
        if not path.exists() and not path.is_symlink():
            continue
        try:
            relative = path.relative_to(root).as_posix().lower()
        except ValueError:
            continue
        values.append("/" + relative)
    return values


def validate_bundle(root: Path) -> tuple[list[str], list[str]]:
    root = Path(root)
    if not root.is_dir():
        return [f"bundle directory not found: {root}"], []

    paths = _paths(root)
    errors: list[str] = []
    findings: list[str] = []

    for module in REQUIRED_PYSIDE_MODULES:
        marker = f"/pyside6/{module}"
        if not any(marker in value for value in paths):
            errors.append(f"required PySide6 module missing: {module}")

    for marker in FORBIDDEN_MARKERS:
        matches = [value for value in paths if marker in value]
        if matches:
            errors.append(
                f"unexpected heavyweight Qt payload {marker}: {matches[0].lstrip('/')}"
            )
            findings.extend(matches[:5])

    return errors, findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()

    errors, _ = validate_bundle(args.bundle)
    if errors:
        print("Qt bundle check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        "Qt bundle check passed: "
        + ", ".join(REQUIRED_PYSIDE_MODULES)
        + "; heavyweight unused Qt families absent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
