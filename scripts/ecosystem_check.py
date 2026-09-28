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

    app_version = (ROOT / "VERSION").read_text("utf-8").strip()

    desktop_pyproject = tomllib.loads(
        (ROOT / "desktop/pyproject.toml").read_text("utf-8")
    )
    desktop_project_version = str(desktop_pyproject["project"]["version"])
    if desktop_project_version != app_version:
        errors.append(
            f"desktop pyproject version {desktop_project_version!r} "
            f"!= VERSION {app_version!r}"
        )

    desktop_init = (ROOT / "desktop/melodex/__init__.py").read_text("utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', desktop_init)
    desktop_init_version = match.group(1) if match else ""
    if desktop_init_version != app_version:
        errors.append(
            f"desktop __version__ {desktop_init_version!r} != VERSION {app_version!r}"
        )

    installer_text = (ROOT / "desktop/installer.iss").read_text("utf-8")
    match = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', installer_text)
    installer_version = match.group(1) if match else ""
    if installer_version != app_version:
        errors.append(
            f"Windows installer version {installer_version!r} != VERSION {app_version!r}"
        )

    android_text = (ROOT / "android/app/build.gradle.kts").read_text("utf-8")
    match = re.search(r'versionName\s*=\s*"([^"]+)"', android_text)
    android_version = match.group(1) if match else ""
    if android_version != app_version:
        errors.append(
            f"Android versionName {android_version!r} != VERSION {app_version!r}"
        )
    match = re.search(r"versionCode\s*=\s*(\d+)", android_text)
    android_code = int(match.group(1)) if match else 0
    if android_code < 1:
        errors.append("Android versionCode must be a positive integer")

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
        ROOT / "docs/RELEASE_STATUS.md",
        ROOT / "GOVERNANCE.md",
        ROOT / "CODE_OF_CONDUCT.md",
    )
    for path in required_docs:
        if not path.is_file():
            errors.append(f"required developer/trust documentation missing: {path.relative_to(ROOT)}")

    readme = (ROOT / "README.md").read_text("utf-8")
    for required_link in (
        "docs/DEVELOPER_QUICKSTART.md",
        "docs/developers/00_STATUS_AND_STABILITY.md",
        "docs/developers/01_ECOSYSTEM_ARCHITECTURE.md",
        "docs/RELEASE_STATUS.md",
        "GOVERNANCE.md",
    ):
        if required_link not in readme:
            errors.append(f"README does not surface {required_link}")

    docs_root = ROOT / "docs"
    docs_index = (docs_root / "ALL_DOCUMENTATION.md").read_text("utf-8")
    for path in sorted(docs_root.rglob("*.md")):
        relative = path.relative_to(docs_root).as_posix()
        if relative == "ALL_DOCUMENTATION.md":
            continue
        if relative not in docs_index:
            errors.append(
                f"docs/ALL_DOCUMENTATION.md does not index {relative}"
            )

    sdk_docs_root = SDK / "docs"
    sdk_docs_index = (sdk_docs_root / "README.md").read_text("utf-8")
    for path in sorted(sdk_docs_root.glob("*.md")):
        relative = path.name
        if relative == "README.md":
            continue
        if relative not in sdk_docs_index:
            errors.append(
                f"provider-sdk/docs/README.md does not index {relative}"
            )

    release_status = (ROOT / "docs/RELEASE_STATUS.md").read_text("utf-8")
    if app_version not in release_status:
        errors.append(
            f"docs/RELEASE_STATUS.md does not name current app version {app_version}"
        )

    contributing = (ROOT / "CONTRIBUTING.md").read_text("utf-8")
    if "scripts/ecosystem_check.py" not in contributing:
        errors.append("CONTRIBUTING.md does not document ecosystem_check.py")
    if "scripts/api_docs_check.py" not in contributing:
        errors.append("CONTRIBUTING.md does not document api_docs_check.py")

    return fail(errors)


if __name__ == "__main__":
    sys.exit(main())
