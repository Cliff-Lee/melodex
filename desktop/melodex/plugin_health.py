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
    if raw in {"unavailable", "offline", "timeout", "degraded"}:
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
