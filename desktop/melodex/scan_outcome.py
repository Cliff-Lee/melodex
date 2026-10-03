from __future__ import annotations

from typing import Any


def scan_storage_outcome(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Return a path-free summary of network/local root health.

    Scanner snapshots contain root paths for internal reconciliation. UI and
    diagnostics should consume only aggregate counts so a support export cannot
    accidentally reveal a mount point, share name, artist folder or filename.
    """
    payload = dict(snapshot or {})
    persistence = dict(payload.get("persistence") or {})
    root_states = [
        dict(row)
        for row in list(payload.get("root_states") or [])
        if isinstance(row, dict)
    ]

    unavailable = int(persistence.get("roots_unavailable") or 0)
    incomplete = int(persistence.get("roots_incomplete") or 0)

    # Direct scan snapshots used by tests/non-persistent callers may not yet
    # have persistence counters. Derive the same aggregate state without
    # exposing paths.
    if root_states and "roots_unavailable" not in persistence:
        unavailable = sum(
            1 for row in root_states if not bool(row.get("available"))
        )
    if root_states and "roots_incomplete" not in persistence:
        incomplete = sum(
            1
            for row in root_states
            if bool(row.get("available"))
            and not bool(row.get("complete", True))
        )

    io_retries = sum(
        max(0, int(row.get("io_retries") or 0))
        for row in root_states
    )
    state = "ok"
    if unavailable:
        state = "unavailable"
    elif incomplete:
        state = "incomplete"

    return {
        "state": state,
        "root_count": len(root_states),
        "roots_unavailable": max(0, unavailable),
        "roots_incomplete": max(0, incomplete),
        "io_retries": io_retries,
        "degraded": bool(unavailable or incomplete),
    }


def scan_storage_message(outcome: dict[str, Any] | None) -> str:
    """Human-facing message for a degraded scan, without private paths."""
    data = dict(outcome or {})
    unavailable = max(0, int(data.get("roots_unavailable") or 0))
    incomplete = max(0, int(data.get("roots_incomplete") or 0))

    if unavailable:
        noun = "location" if unavailable == 1 else "locations"
        return (
            f"{unavailable} music {noun} unavailable — showing your last "
            "indexed library. No cached tracks were removed."
        )
    if incomplete:
        noun = "location" if incomplete == 1 else "locations"
        return (
            f"Could not finish reading {incomplete} music {noun} — showing "
            "your last indexed library. No partial scan was applied."
        )
    return ""


__all__ = ["scan_storage_message", "scan_storage_outcome"]
