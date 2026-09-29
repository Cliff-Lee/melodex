from __future__ import annotations

from typing import Any


def configuration_state(info: dict[str, Any] | None) -> str:
    """Return a small UI-neutral state for one plugin configuration descriptor."""
    info = dict(info or {})
    fields = list(info.get("fields") or [])
    if not fields:
        return "none"
    status = dict(info.get("status") or {})
    return "ready" if status.get("ready", True) else "setup_needed"


def configuration_summary(info: dict[str, Any] | None) -> str:
    state = configuration_state(info)
    if state == "none":
        return "No setup required"
    if state == "ready":
        return "Ready"
    info = dict(info or {})
    status = dict(info.get("status") or {})
    missing = [str(x) for x in status.get("missing_required") or []]
    labels = {
        str(field.get("key") or ""): str(
            field.get("label") or field.get("key") or ""
        )
        for field in info.get("fields") or []
        if isinstance(field, dict)
    }
    names = [labels.get(key, key) for key in missing]
    return "Setup needed" + (f" — missing: {', '.join(names)}" if names else "")


def plugin_configuration_info(manager, plugin_id: str) -> dict[str, Any]:
    try:
        return dict(manager.plugin_configuration(str(plugin_id)) or {})
    except (KeyError, ValueError):
        return {}


def plugin_needs_setup(manager, plugin_id: str) -> bool:
    return (
        configuration_state(plugin_configuration_info(manager, plugin_id))
        == "setup_needed"
    )
