from __future__ import annotations

from typing import Any


# Fields used internally for playback but which should never be exposed to an
# LLM/control response or written into ordinary listening-history metadata.
_PRIVATE_KEYS = {
    "local_path",
    "url",
    "stream_url",
    "headers",
    "cookies",
    "refresh_token",
    "expires_at",
    "gateway_required",
    "_playback_allowed_hosts",
    "request_timeout_seconds",
}

_PRIVATE_KEY_FRAGMENTS = (
    "password",
    "secret",
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "bearer_token",
)


def redact_for_llm(value: Any) -> Any:
    """Return a JSON-like copy with playback credentials/private paths removed."""

    if isinstance(value, dict):
        out: dict[str, Any] = {}

        for raw_key, raw_value in value.items():
            key = str(raw_key)
            lowered = key.casefold()

            if lowered in _PRIVATE_KEYS:
                continue

            if any(fragment in lowered for fragment in _PRIVATE_KEY_FRAGMENTS):
                continue

            out[key] = redact_for_llm(raw_value)

        return out

    if isinstance(value, list):
        return [redact_for_llm(item) for item in value]

    if isinstance(value, tuple):
        return [redact_for_llm(item) for item in value]

    return value
