from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any


def bundled_provider_dir() -> Path:
    return Path(__file__).resolve().parent / "bundled_providers"


def _manifest_from_package(package: Path) -> dict[str, Any]:
    with zipfile.ZipFile(package) as zf:
        name = next(
            (item for item in zf.namelist() if item.rstrip("/").endswith("manifest.json")),
            None,
        )
        if not name:
            raise ValueError(f"{package.name} has no manifest.json")
        data = json.loads(zf.read(name))
        return data if isinstance(data, dict) else {}


def _installed_manifest(folder: Path) -> dict[str, Any]:
    try:
        data = json.loads((folder / "manifest.json").read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def version_key(value: str) -> tuple[int, ...]:
    nums = [int(x) for x in re.findall(r"\d+", str(value or ""))]
    return tuple(nums or [0])


def bundled_packages() -> list[tuple[str, Path, dict[str, Any]]]:
    result: list[tuple[str, Path, dict[str, Any]]] = []
    root = bundled_provider_dir()
    if not root.is_dir():
        return result

    for package in sorted(root.glob("*.mdxprovider")):
        try:
            manifest = _manifest_from_package(package)
            pid = str(manifest.get("id") or "").strip()
            if pid:
                result.append((pid, package, manifest))
        except Exception:
            continue
    return result


def bundled_provider_ids() -> list[str]:
    return [pid for pid, _, _ in bundled_packages()]


def ensure_bundled_providers(installer, settings: dict[str, Any]) -> list[str]:
    disabled = {
        str(x)
        for x in (settings.get("disabled_bundled_providers") or [])
        if str(x).strip()
    }
    ready: list[str] = []

    for pid, package, manifest in bundled_packages():
        if pid in disabled:
            continue

        dest = installer.providers_dir / pid
        bundled_version = version_key(str(manifest.get("version") or "0"))
        installed = _installed_manifest(dest)
        installed_version = version_key(str(installed.get("version") or "0"))

        if (
            not dest.is_dir()
            or not installed
            or bundled_version > installed_version
        ):
            installer.install(package)

        ready.append(pid)

    return ready


def set_bundled_provider_disabled(
    settings: dict[str, Any],
    provider_id: str,
    disabled: bool,
) -> None:
    pid = str(provider_id or "").strip()
    current = {
        str(x)
        for x in (settings.get("disabled_bundled_providers") or [])
        if str(x).strip()
    }
    if disabled:
        current.add(pid)
    else:
        current.discard(pid)
    settings["disabled_bundled_providers"] = sorted(current)


def restore_all_bundled_provider_flags(settings: dict[str, Any]) -> None:
    settings["disabled_bundled_providers"] = []
