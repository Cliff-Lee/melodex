from __future__ import annotations

import re
from typing import Any


_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password|authorization)"
    r"\s*[:=]\s*([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")


def safe_health_text(
    value: Any,
    redact_values: list[str] | tuple[str, ...] | set[str] | None = None,
) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = _BEARER.sub("Bearer [redacted]", text)
    text = _SECRET_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}=[redacted]", text
    )
    for secret in sorted(
        {str(item) for item in (redact_values or []) if len(str(item)) >= 4},
        key=len,
        reverse=True,
    ):
        text = text.replace(secret, "[redacted]")
    return text


def normalise_health_status(value: Any) -> str:
    raw = str(value or "").casefold().strip().replace("-", "_")
    if raw in {"ok", "ready", "healthy", "available", "working"}:
        return "ready"
    if raw in {
        "auth_required",
        "authentication_required",
        "unauthorized",
        "forbidden",
    }:
        return "authentication_required"
    if raw in {"setup_required", "config_required", "configuration_required"}:
        return "setup_required"
    if raw in {"disabled"}:
        return "disabled"
    if raw in {"degraded"}:
        return "degraded"
    if raw in {"unavailable", "offline", "timeout"}:
        return "unavailable"
    if raw in {"error", "failed", "failure", "broken"}:
        return "error"
    if raw in {"idle", "unknown", "untested", ""}:
        return "untested"
    return "unavailable"


def health_badge(result: dict[str, Any] | None) -> str:
    status = normalise_health_status((result or {}).get("status"))
    return {
        "ready": "READY",
        "setup_required": "SETUP NEEDED",
        "authentication_required": "AUTH REQUIRED",
        "disabled": "DISABLED",
        "degraded": "DEGRADED",
        "unavailable": "UNAVAILABLE",
        "error": "ERROR",
        "untested": "NOT TESTED",
    }[status]


def health_summary(result: dict[str, Any] | None) -> str:
    result = dict(result or {})
    badge = health_badge(result)
    message = safe_health_text(result.get("message"))
    scope = str(result.get("check_scope") or "").strip()
    if message:
        return f"{badge} — {message}"
    if scope == "process" and badge == "READY":
        return "READY — extension process starts successfully"
    if scope == "runtime" and badge == "READY":
        return "READY — recent extension calls succeeded"
    return badge



def health_user_presentation(result: dict[str, Any] | None) -> dict[str, str]:
    """Return listener-facing health copy without exposing diagnostic jargon."""
    result = dict(result or {})
    status = normalise_health_status(result.get("status"))
    reason = str(result.get("reason") or "").casefold().strip()

    if status == "ready":
        return {
            "badge": "Ready",
            "semantic": "ready",
            "title": "Ready to use",
            "guidance": "A recent connection or capability check succeeded.",
            "action": "Check connection",
        }
    if status == "setup_required":
        return {
            "badge": "Setup needed",
            "semantic": "attention",
            "title": "Finish setup",
            "guidance": "Add the required settings before this plugin can be used.",
            "action": "Configure…",
        }
    if status == "authentication_required":
        return {
            "badge": "Sign-in needed",
            "semantic": "attention",
            "title": "Sign-in or credential needed",
            "guidance": "Update this plugin's credentials, then check the connection again.",
            "action": "Configure…",
        }
    if status == "disabled":
        return {
            "badge": "Disabled",
            "semantic": "disabled",
            "title": "Plugin disabled",
            "guidance": "Enable it when you want Melodex to use this optional feature.",
            "action": "Enable",
        }
    if status == "degraded":
        return {
            "badge": "Partly available",
            "semantic": "attention",
            "title": "Partly available",
            "guidance": "Some checks succeeded, but a recent plugin call failed.",
            "action": "Try connection again",
        }
    if status == "unavailable":
        if reason == "tls_error":
            title = "Secure connection unavailable"
            guidance = (
                "The plugin is still installed. Melodex could not establish a trusted "
                "connection to the service; check the network and try again."
            )
        elif reason == "network_error":
            title = "Service unreachable"
            guidance = (
                "The plugin is still installed. The service or network could not be "
                "reached; check connectivity and try again."
            )
        elif reason == "timeout":
            title = "Service took too long"
            guidance = (
                "The plugin is still installed. The service did not respond in time; "
                "try the connection again later."
            )
        else:
            title = "Temporarily unavailable"
            guidance = (
                "The plugin is still installed, but its service is not available right now."
            )
        return {
            "badge": "Temporarily unavailable",
            "semantic": "unavailable",
            "title": title,
            "guidance": guidance,
            "action": "Try connection again",
        }
    if status == "error":
        return {
            "badge": "Needs attention",
            "semantic": "attention",
            "title": "Plugin needs attention",
            "guidance": (
                "This looks like a plugin or protocol problem rather than a temporary "
                "internet outage. Check the technical details if it keeps happening."
            ),
            "action": "Check connection",
        }

    return {
        "badge": "Not checked",
        "semantic": "neutral",
        "title": "Not checked yet",
        "guidance": (
            "Melodex has not tested this optional source in the current session. "
            "You can check it now, or simply use it when needed."
        ),
        "action": "Check connection",
    }
