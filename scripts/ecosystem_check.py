from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "provider-sdk"


def fail(errors: list[str]) -> int:
    if errors:
        print("Ecosystem consistency check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Ecosystem consistency check passed")
    return 0


def main() -> int:
    errors: list[str] = []

    pyproject = tomllib.loads((SDK / "pyproject.toml").read_text("utf-8"))
    version = str(pyproject["project"]["version"])

    init_text = (SDK / "src/melodex_provider_sdk/__init__.py").read_text("utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    init_version = match.group(1) if match else ""
    if init_version != version:
        errors.append(
            f"provider-sdk __version__ {init_version!r} != pyproject version {version!r}"
        )

    for relative in (
        "src/melodex_provider_sdk/cli.py",
        "src/melodex_provider_sdk/extension_cli.py",
        "src/melodex_provider_sdk/registry_cli.py",
    ):
        text = (SDK / relative).read_text("utf-8")
        if f"%(prog)s {version}" not in text:
            errors.append(f"{relative} does not expose CLI version {version}")

    registry = json.loads((SDK / "registry/registry.json").read_text("utf-8"))
    example = json.loads((SDK / "registry/example-registry.json").read_text("utf-8"))
    if registry != example:
        errors.append(
            "registry/example-registry.json no longer mirrors canonical registry.json"
        )

    required_docs = (
        ROOT / "docs/DEVELOPER_QUICKSTART.md",
        ROOT / "docs/developers/00_STATUS_AND_STABILITY.md",
        ROOT / "docs/developers/01_ECOSYSTEM_ARCHITECTURE.md",
        ROOT / "docs/developers/07_PERMISSIONS_SECURITY.md",
        ROOT / "docs/PLUGIN_DIRECTORY.md",
    )
    for path in required_docs:
        if not path.is_file():
            errors.append(f"required developer/trust documentation missing: {path.relative_to(ROOT)}")

    readme = (ROOT / "README.md").read_text("utf-8")
    for required_link in (
        "docs/DEVELOPER_QUICKSTART.md",
        "docs/developers/00_STATUS_AND_STABILITY.md",
        "docs/developers/01_ECOSYSTEM_ARCHITECTURE.md",
    ):
        if required_link not in readme:
            errors.append(f"README does not surface {required_link}")

    return fail(errors)


if __name__ == "__main__":
    sys.exit(main())
