from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__

_SCAN_METRIC_FIELDS = (
    "started_at",
    "thread_name",
    "main_thread",
    "root_count",
    "roots_checked",
    "roots_missing",
    "directories_seen",
    "files_seen",
    "audio_files_seen",
    "metadata_attempts",
    "metadata_seconds",
    "non_metadata_seconds",
    "total_seconds",
    "tracks_indexed",
    "unchanged_files",
    "added_files",
    "changed_files",
    "removed_files",
    "stat_failures",
    "metadata_reused",
    "incomplete_roots",
    "process_isolated",
)

_CATALOG_METRIC_FIELDS = (
    "thread_name",
    "main_thread",
    "track_count",
    "album_count",
    "artist_count",
    "reset_seconds",
    "copy_catalog_seconds",
    "album_model_seconds",
    "album_index_seconds",
    "artist_model_seconds",
    "initial_layout_seconds",
    "artwork_request_seconds",
    "total_seconds",
)

_RESPONSIVENESS_FIELDS = (
    "interval_ms",
    "long_task_threshold_ms",
    "ci_threshold_ms",
    "serious_threshold_ms",
    "blocker_threshold_ms",
    "total_stalls",
    "long_tasks",
    "ci_violations",
    "serious_stalls",
    "release_blockers",
    "p99_event_loop_gap_ms",
    "max_gap_ms",
    "max_delay_ms",
    "interaction_count",
    "interaction_p95_ms",
    "interaction_max_ms",
    "interactions_over_50_ms",
    "interactions_over_100_ms",
)

_RESPONSIVENESS_EVENT_FIELDS = (
    "recorded_at",
    "severity",
    "delay_ms",
    "gap_ms",
    "action",
)

_RESPONSIVENESS_INTERACTION_FIELDS = (
    "label",
    "duration_ms",
)


def _metric_summary(raw: Any, allowed: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {key: raw.get(key) for key in allowed if key in raw}


def _responsiveness_summary(raw: Any) -> dict[str, Any]:
    summary = _metric_summary(raw, _RESPONSIVENESS_FIELDS)
    if not isinstance(raw, dict):
        return summary

    events: list[dict[str, Any]] = []
    for event in list(raw.get("recent_stalls") or [])[-50:]:
        if not isinstance(event, dict):
            continue
        clean = {
            key: event.get(key)
            for key in _RESPONSIVENESS_EVENT_FIELDS
            if key in event
        }
        if "action" in clean:
            clean["action"] = str(clean["action"] or "")[:80]
        events.append(clean)
    if events:
        summary["recent_stalls"] = events

    interactions: list[dict[str, Any]] = []
    for event in list(raw.get("recent_interactions") or [])[-50:]:
        if not isinstance(event, dict):
            continue
        clean = {
            key: event.get(key)
            for key in _RESPONSIVENESS_INTERACTION_FIELDS
            if key in event
        }
        if "label" in clean:
            clean["label"] = str(clean["label"] or "")[:80]
        interactions.append(clean)
    if interactions:
        summary["recent_interactions"] = interactions
    return summary



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


def build_diagnostics(
    manager: Any,
    ui_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
            try:
                row["plugin_health"] = manager.plugin_health(provider_id)
            except Exception:
                row["plugin_health"] = {}
            row["installation"] = _installation_summary(
                manager.installation_record(provider_id)
            )
        providers.append(row)

    extensions: list[dict[str, Any]] = []
    for raw in manager.extensions():
        extension = dict(raw)
        extension_id = str(extension.get("id") or "")
        try:
            plugin_health = manager.plugin_health(extension_id) if extension_id else {}
        except Exception:
            plugin_health = {}
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
                "plugin_health": plugin_health,
                "configuration_status": dict(
                    extension.get("configuration_status") or {}
                ),
                "installation": _installation_summary(
                    manager.installation_record(extension_id)
                ),
            }
        )

    performance: dict[str, Any] = {}
    local_provider = getattr(manager, "providers", {}).get("local")
    local_scan = _metric_summary(
        getattr(local_provider, "last_scan_metrics", {}),
        _SCAN_METRIC_FIELDS,
    )
    if local_scan:
        performance["local_scan"] = local_scan

    supplied_ui = dict(ui_metrics or {})
    library_catalog = _metric_summary(
        supplied_ui.get("library_catalog"),
        _CATALOG_METRIC_FIELDS,
    )
    if library_catalog:
        performance["library_catalog"] = library_catalog

    ui_responsiveness = _responsiveness_summary(
        supplied_ui.get("responsiveness")
    )
    if ui_responsiveness:
        performance["ui_responsiveness"] = ui_responsiveness

    library_index: dict[str, Any] = {}
    summary_fn = getattr(manager, "local_index_summary", None)
    if callable(summary_fn):
        try:
            raw_summary = dict(summary_fn() or {})
        except Exception:
            raw_summary = {}
        for key in ("root_count", "ready_roots", "track_count", "all_ready"):
            if key in raw_summary:
                library_index[key] = raw_summary.get(key)

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
        "performance": performance,
        "library_index": library_index,
        "notes": [
            "This export omits plugin configuration values, API keys, tokens, "
            "local library paths, user-stream URLs, playback URLs, headers and cookies.",
            "Package SHA-256 values and public source-repository URLs may be included "
            "to help diagnose installation provenance.",
            "Performance telemetry contains counts, timings and thread information only; "
            "library root, directory and file names are not included.",
        ],
    }


def write_diagnostics(
    path: Path,
    manager: Any,
    ui_metrics: dict[str, Any] | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            build_diagnostics(manager, ui_metrics=ui_metrics),
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    return path
