from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__


def _installation_summary(record: dict[str, Any]) -> dict[str, Any]:
    if not record:
        return {}
    allowed = (
        "id",
        "name",
        "version",
        "kind",
        "installed_at",
        "method",
        "package_name",
        "package_size",
        "package_sha256",
        "registry_verified",
        "registry_status",
        "publisher",
        "registry_sha256",
        "source_repository",
    )
    return {key: record.get(key) for key in allowed if key in record}


def build_diagnostics(manager: Any) -> dict[str, Any]:
    """Build a support snapshot that intentionally excludes user secrets and media URLs."""

    providers: list[dict[str, Any]] = []
    for provider_id in manager.provider_order():
        provider = manager.providers[provider_id]
        info = provider.info
        row: dict[str, Any] = {
            "id": str(info.id),
            "name": str(info.name),
            "version": str(info.version),
            "capabilities": [str(value) for value in info.capabilities],
        }

        if provider_id == "local":
            row["kind"] = "built-in"
            row["track_count"] = len(manager.local_catalog())
        elif provider_id == "jamendo":
            row["kind"] = "reference"
            row["configured"] = bool(
                str(manager.settings.get("jamendo_client_id") or "").strip()
            )
        elif provider_id == "streams":
            row["kind"] = "built-in"
            row["stream_count"] = len(manager.user_streams())
        else:
            row["kind"] = "provider"
            row["permissions"] = dict(info.permissions or {})
            if getattr(info, "configuration", None):
                row["configuration_status"] = manager.plugin_config.status(
                    provider_id, info.configuration
                )
            row["installation"] = _installation_summary(
                manager.installation_record(provider_id)
            )
        providers.append(row)

    extensions: list[dict[str, Any]] = []
    for raw in manager.extensions():
        extension = dict(raw)
        extension_id = str(extension.get("id") or "")
        extensions.append(
            {
                "id": extension_id,
                "name": str(extension.get("name") or extension_id),
                "version": str(extension.get("version") or ""),
                "capabilities": [
                    str(value) for value in extension.get("capabilities") or []
                ],
                "permissions": dict(extension.get("permissions") or {}),
                "enabled": bool(extension.get("enabled", True)),
                "preferred_for": [
                    str(value) for value in extension.get("preferred_for") or []
                ],
                "health": dict(extension.get("health") or {}),
                "configuration_status": dict(
                    extension.get("configuration_status") or {}
                ),
                "installation": _installation_summary(
                    manager.installation_record(extension_id)
                ),
            }
        )

    return {
        "schema_version": "0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "melodex_version": __version__,
        "system": {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "sources": providers,
        "extensions": extensions,
        "notes": [
            "This export omits plugin configuration values, API keys, tokens, "
            "local library paths, user-stream URLs, playback URLs, headers and cookies.",
            "Package SHA-256 values and public source-repository URLs may be included "
            "to help diagnose installation provenance.",
        ],
    }


def write_diagnostics(path: Path, manager: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_diagnostics(manager), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
