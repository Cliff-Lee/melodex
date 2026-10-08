"""Pure queue rules for applying a late session plan safely."""

from __future__ import annotations

from typing import Any


def track_key(track: dict[str, Any]) -> str:
    return str(track.get("track_id") or track.get("local_path") or "")


def refined_upcoming(
    current_queue: list[dict[str, Any]],
    current_index: int,
    planned_tracks: list[dict[str, Any]],
    expected_queue_ids: tuple[str, ...],
) -> list[dict[str, Any]] | None:
    """Return a personalized tail only while the user-owned queue is unchanged.

    ``None`` means the live queue no longer belongs to the session that asked
    for enrichment. An empty list means the plan has no unseen tracks to add.
    """
    queue = [dict(track) for track in current_queue if isinstance(track, dict)]
    current_ids = tuple(track_key(track) for track in queue)
    if current_ids != expected_queue_ids:
        return None
    if not (0 <= int(current_index) < len(queue)):
        return None

    already_heard_or_current = {
        track_key(track) for track in queue[: int(current_index) + 1]
    }
    upcoming: list[dict[str, Any]] = []
    seen = set(already_heard_or_current)
    for raw in planned_tracks:
        if not isinstance(raw, dict):
            continue
        track = dict(raw)
        key = track_key(track)
        if not key or key in seen:
            continue
        seen.add(key)
        upcoming.append(track)
    return upcoming


__all__ = ["refined_upcoming", "track_key"]
