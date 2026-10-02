from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


class StartupTimeline:
    """Small, content-free startup timing recorder.

    Only static phase labels and elapsed timings are recorded. Paths, tracks,
    providers, credentials and other user content never enter the timeline.
    """

    def __init__(self, *, started_at: float | None = None) -> None:
        self.started_at = (
            time.perf_counter() if started_at is None else float(started_at)
        )
        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] = []

    def mark(self, phase: str, *, now: float | None = None) -> dict[str, Any]:
        label = str(phase or "").strip()[:80]
        if not label:
            raise ValueError("Startup phase must not be empty")
        current = time.perf_counter() if now is None else float(now)
        elapsed_ms = max(0.0, (current - self.started_at) * 1000.0)
        with self._lock:
            previous_ms = (
                float(self._events[-1]["elapsed_ms"]) if self._events else 0.0
            )
            event = {
                "phase": label,
                "elapsed_ms": round(elapsed_ms, 3),
                "delta_ms": round(max(0.0, elapsed_ms - previous_ms), 3),
            }
            self._events.append(event)
            return dict(event)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            events = [dict(row) for row in self._events]
        return {
            "schema": 1,
            "total_ms": (
                float(events[-1]["elapsed_ms"]) if events else 0.0
            ),
            "events": events,
        }

    def write_json(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n",
            "utf-8",
        )
        return target


__all__ = ["StartupTimeline"]
