from __future__ import annotations

import time
from typing import Callable


class SeekInteraction:
    """Arbitrate transport-slider ownership while a seek is in flight.

    Player position updates remain authoritative for playback state, but they
    must not overwrite the slider while the user is scrubbing or while the
    backend is still acknowledging a committed seek.
    """

    def __init__(
        self,
        *,
        tolerance_ms: int = 900,
        commit_timeout_ms: int = 2000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.tolerance_ms = max(0, int(tolerance_ms))
        self.commit_timeout_ms = max(100, int(commit_timeout_ms))
        self._clock = clock
        self.state = "idle"
        self.target_ms: int | None = None
        self._commit_started_at = 0.0
        self._metrics = {
            "scrubs_started": 0,
            "commits": 0,
            "acknowledged": 0,
            "timed_out": 0,
            "player_updates_suppressed": 0,
            "cancelled": 0,
        }

    def begin(self) -> None:
        self.state = "scrubbing"
        self.target_ms = None
        self._commit_started_at = 0.0
        self._metrics["scrubs_started"] += 1

    def commit(self, slider_value: int, duration_ms: int) -> int | None:
        duration = max(0, int(duration_ms))
        if duration <= 0:
            self.cancel()
            return None
        value = max(0, min(1000, int(slider_value)))
        target = int(round(duration * value / 1000.0))
        self.state = "committing"
        self.target_ms = target
        self._commit_started_at = self._clock()
        self._metrics["commits"] += 1
        return target

    def follow_player_position(self, position_ms: int, duration_ms: int) -> bool:
        """Return whether the transport slider may follow this player update."""
        if self.state == "scrubbing":
            self._metrics["player_updates_suppressed"] += 1
            return False
        if self.state != "committing":
            return True

        target = self.target_ms
        if target is None:
            self.state = "idle"
            return True

        position = max(0, int(position_ms))
        duration = max(0, int(duration_ms))
        tolerance = max(
            self.tolerance_ms,
            min(2500, int(round(duration * 0.002))) if duration else 0,
        )
        if abs(position - target) <= tolerance:
            self.state = "idle"
            self.target_ms = None
            self._commit_started_at = 0.0
            self._metrics["acknowledged"] += 1
            return True

        elapsed_ms = (self._clock() - self._commit_started_at) * 1000.0
        if elapsed_ms >= self.commit_timeout_ms:
            self.state = "idle"
            self.target_ms = None
            self._commit_started_at = 0.0
            self._metrics["timed_out"] += 1
            return True

        self._metrics["player_updates_suppressed"] += 1
        return False

    def cancel(self) -> None:
        if self.state != "idle":
            self._metrics["cancelled"] += 1
        self.state = "idle"
        self.target_ms = None
        self._commit_started_at = 0.0

    def snapshot(self) -> dict[str, int | str | None]:
        return {
            **dict(self._metrics),
            "state": self.state,
            "target_ms": self.target_ms,
            "tolerance_ms": self.tolerance_ms,
            "commit_timeout_ms": self.commit_timeout_ms,
        }


__all__ = ["SeekInteraction"]
