from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text("utf-8")


def desktop_pyproject_version() -> str:
    data = tomllib.loads(read_text("desktop/pyproject.toml"))
    return str(data["project"]["version"])


def python_module_version() -> str:
    text = read_text("desktop/melodex/__init__.py")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def android_version() -> tuple[int, str]:
    text = read_text("android/app/build.gradle.kts")
    code = re.search(r"versionCode\s*=\s*(\d+)", text)
    name = re.search(r'versionName\s*=\s*"([^"]+)"', text)
    return (
        int(code.group(1)) if code else 0,
        name.group(1) if name else "",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--release-tag",
        default="",
        help="Optional release tag, for example v0.3.0",
    )
    args = parser.parse_args(argv)

    canonical = read_text("VERSION").strip()
    desktop_project = desktop_pyproject_version()
    module = python_module_version()
    android_code, android_name = android_version()
    installer_text = read_text("desktop/installer.iss")
    installer_match = re.search(r'#define MyAppVersion "([^"]+)"', installer_text)
    installer_fallback = installer_match.group(1) if installer_match else ""

    errors: list[str] = []
    for label, value in (
        ("desktop/pyproject.toml", desktop_project),
        ("desktop/melodex/__init__.py", module),
        ("Android versionName", android_name),
        ("Windows installer fallback", installer_fallback),
    ):
        if value != canonical:
            errors.append(f"{label} version {value!r} != VERSION {canonical!r}")

    if android_code < 1:
        errors.append("Android versionCode must be a positive integer")

    tag = str(args.release_tag or "").strip()
    if tag:
        expected = tag[1:] if tag.startswith("v") else tag
        if ".dev" in canonical:
            errors.append(
                f"release tag {tag!r} cannot be built while VERSION is development version {canonical!r}"
            )
        if canonical != expected:
            errors.append(
                f"release tag {tag!r} does not match VERSION {canonical!r}"
            )

    if errors:
        print("Version consistency check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        f"Version consistency check passed: app={canonical}, "
        f"androidVersionCode={android_code}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
