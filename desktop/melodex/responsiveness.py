from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer, Qt


class ResponsivenessTracker:
    """Measure event-loop scheduling delays without recording user content."""

    def __init__(
        self,
        *,
        interval_ms: int = 50,
        stall_threshold_ms: int = 100,
        severe_threshold_ms: int = 250,
        critical_threshold_ms: int = 1000,
        action_ttl_seconds: float = 5.0,
        max_events: int = 50,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.interval_ms = max(1, int(interval_ms))
        self.stall_threshold_ms = max(self.interval_ms, int(stall_threshold_ms))
        self.severe_threshold_ms = max(
            self.stall_threshold_ms, int(severe_threshold_ms)
        )
        self.critical_threshold_ms = max(
            self.severe_threshold_ms, int(critical_threshold_ms)
        )
        self.action_ttl_seconds = max(0.0, float(action_ttl_seconds))
        self._clock = clock
        self._last_tick: float | None = None
        self._last_action = ""
        self._last_action_at = 0.0
        self._events: deque[dict[str, Any]] = deque(maxlen=max(1, int(max_events)))
        self._warning_stalls = 0
        self._severe_stalls = 0
        self._critical_stalls = 0
        self._max_delay_ms = 0.0

    def reset_clock(self, now: float | None = None) -> None:
        self._last_tick = self._clock() if now is None else float(now)

    def mark_action(self, label: str, now: float | None = None) -> None:
        self._last_action = str(label or "").strip()
        self._last_action_at = self._clock() if now is None else float(now)

    def observe(self, now: float | None = None) -> dict[str, Any] | None:
        current = self._clock() if now is None else float(now)
        if self._last_tick is None:
            self._last_tick = current
            return None

        gap_ms = max(0.0, (current - self._last_tick) * 1000.0)
        self._last_tick = current
        delay_ms = max(0.0, gap_ms - float(self.interval_ms))
        if delay_ms < self.stall_threshold_ms:
            return None

        if delay_ms >= self.critical_threshold_ms:
            severity = "critical"
            self._critical_stalls += 1
        elif delay_ms >= self.severe_threshold_ms:
            severity = "severe"
            self._severe_stalls += 1
        else:
            severity = "warning"
            self._warning_stalls += 1

        action = ""
        if (
            self._last_action
            and current - self._last_action_at <= self.action_ttl_seconds
        ):
            action = self._last_action

        event = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "severity": severity,
            "delay_ms": round(delay_ms, 1),
            "gap_ms": round(gap_ms, 1),
            "action": action,
        }
        self._events.append(event)
        self._max_delay_ms = max(self._max_delay_ms, delay_ms)
        return dict(event)

    def summary(self) -> dict[str, Any]:
        return {
            "interval_ms": self.interval_ms,
            "stall_threshold_ms": self.stall_threshold_ms,
            "severe_threshold_ms": self.severe_threshold_ms,
            "critical_threshold_ms": self.critical_threshold_ms,
            "total_stalls": (
                self._warning_stalls
                + self._severe_stalls
                + self._critical_stalls
            ),
            "warning_stalls": self._warning_stalls,
            "severe_stalls": self._severe_stalls,
            "critical_stalls": self._critical_stalls,
            "max_delay_ms": round(self._max_delay_ms, 1),
            "recent_stalls": [dict(event) for event in self._events],
        }


class UiResponsivenessMonitor(QObject):
    """Qt timer wrapper around ResponsivenessTracker."""

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        interval_ms: int = 50,
        stall_threshold_ms: int = 100,
        severe_threshold_ms: int = 250,
        critical_threshold_ms: int = 1000,
    ) -> None:
        super().__init__(parent)
        self.tracker = ResponsivenessTracker(
            interval_ms=interval_ms,
            stall_threshold_ms=stall_threshold_ms,
            severe_threshold_ms=severe_threshold_ms,
            critical_threshold_ms=critical_threshold_ms,
        )
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(self.tracker.interval_ms)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self.tracker.reset_clock()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def mark_action(self, label: str) -> None:
        self.tracker.mark_action(label)

    def summary(self) -> dict[str, Any]:
        return self.tracker.summary()

    def _tick(self) -> None:
        self.tracker.observe()
