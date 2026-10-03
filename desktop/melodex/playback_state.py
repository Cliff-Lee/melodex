"""Canonical in-process snapshot of the current playback session.

FlowPlayer remains the playback authority.  This model stores the latest
semantic state observed by the Playback feature so presentation and adjacent
features can read defensive snapshots without keeping their own mutable copy.
It deliberately has no Qt or player dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlaybackSnapshot:
    current_track: dict[str, Any] | None
    current_history_id: int
    current_track_started: float
    position_ms: int
    duration_ms: int
    playing: bool
    queue: tuple[dict[str, Any], ...]
    queue_index: int


@dataclass
class PlaybackSessionState:
    """Own canonical playback snapshots while FlowPlayer owns actual playback."""

    _current_track: dict[str, Any] | None = None
    _current_history_id: int = 0
    _current_track_started: float = 0.0
    _position_ms: int = 0
    _duration_ms: int = 0
    _playing: bool = False
    _queue: list[dict[str, Any]] = field(default_factory=list)
    _queue_index: int = -1

    def snapshot(self) -> PlaybackSnapshot:
        track = dict(self._current_track) if self._current_track else None
        queue = tuple(dict(item) for item in self._queue)
        return PlaybackSnapshot(
            current_track=track,
            current_history_id=int(self._current_history_id),
            current_track_started=float(self._current_track_started),
            position_ms=int(self._position_ms),
            duration_ms=int(self._duration_ms),
            playing=bool(self._playing),
            queue=queue,
            queue_index=int(self._queue_index),
        )

    def start_track(
        self,
        track: dict[str, Any],
        *,
        history_id: int,
        started_at: float,
    ) -> None:
        self._current_track = dict(track)
        self._current_history_id = int(history_id)
        self._current_track_started = float(started_at)
        self._position_ms = 0
        self._duration_ms = 0

    def clear_current_track(self) -> None:
        self._current_track = None
        self._current_history_id = 0
        self._current_track_started = 0.0
        self._position_ms = 0
        self._duration_ms = 0

    def merge_current_track(self, changes: dict[str, Any]) -> dict[str, Any] | None:
        if not self._current_track:
            return None
        self._current_track = {**self._current_track, **dict(changes or {})}
        return dict(self._current_track)

    def update_position(self, position_ms: int, duration_ms: int) -> None:
        self._position_ms = int(position_ms)
        self._duration_ms = int(duration_ms)

    def mark_current_track_completed(self) -> int:
        history_id = int(self._current_history_id)
        self._current_history_id = 0
        return history_id

    def set_playing(self, playing: bool) -> None:
        self._playing = bool(playing)

    def update_queue(self, tracks: list[dict[str, Any]], index: int) -> None:
        self._queue = [dict(track) for track in tracks if isinstance(track, dict)]
        self._queue_index = int(index)


__all__ = ["PlaybackSessionState", "PlaybackSnapshot"]
