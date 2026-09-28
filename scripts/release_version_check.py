from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    tag = (args[0] if args else os.getenv("GITHUB_REF_NAME", "")).strip()
    version = (ROOT / "VERSION").read_text("utf-8").strip()

    errors: list[str] = []
    if not tag:
        errors.append("release tag is required (for example v0.3.0)")
    if ".dev" in version or version.endswith("-dev"):
        errors.append(
            f"VERSION is a development version ({version}); set a stable version before tagging"
        )
    expected = f"v{version}"
    if tag and tag != expected:
        errors.append(f"tag {tag!r} does not match VERSION {version!r} (expected {expected!r})")

    if errors:
        print("Release version check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Release version check passed: {tag} == VERSION {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
