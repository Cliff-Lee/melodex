from __future__ import annotations

from typing import Any, Callable

from .bridge_server import ProviderBridge, handoff_queue_conflict, playback_session_matches


def handoff_queue_to_desktop(
    player: Any,
    args: dict[str, Any],
    resume_checkpoint: Callable[[dict[str, Any], int], None],
) -> dict[str, Any]:
    tracks = [dict(track) for track in list(args.get("tracks") or []) if isinstance(track, dict)]
    reason = handoff_queue_conflict(player.status(), tracks)
    if reason:
        return {"ok": False, "reason": reason}
    start = int(args.get("start", 0))
    if start < 0 or start >= len(tracks):
        raise RuntimeError("Handoff start index is outside the queue")
    player.set_queue(
        tracks,
        start,
        bool(args.get("autoplay", True)),
        intent="manual_queue",
    )
    position_ms = max(0, int(args.get("position_ms", 0)))
    if position_ms:
        resume_checkpoint(dict(tracks[start]), position_ms)
    return {"ok": True}


def stop_playback_if_session_matches(
    player: Any,
    args: dict[str, Any],
) -> dict[str, Any]:
    status = player.status()
    expected_queue = [
        dict(track)
        for track in list(args.get("expected_queue") or [])
        if isinstance(track, dict)
    ]
    expected_index = int(args.get("expected_index", -1))
    if not playback_session_matches(status, expected_queue, expected_index):
        return {"ok": False, "stopped": False, "reason": "desktop_session_changed"}
    player.stop()
    return {"ok": True, "stopped": True, "reason": ""}
