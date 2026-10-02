from __future__ import annotations

import heapq
import itertools
import threading
from dataclasses import dataclass, field
from typing import Callable


PRIORITY_ORDER = {
    "foreground": 0,
    "visible": 1,
    "prefetch": 2,
    "background": 3,
    "idle": 4,
}


@dataclass(order=True)
class _ScheduledJob:
    sort_key: tuple[int, int]
    priority: str = field(compare=False)
    callback: Callable[[], None] = field(compare=False)
    name: str = field(compare=False, default="")


class BackgroundScheduler:
    """Shared bounded scheduler for desktop background work.

    The scheduler deliberately keeps one worker available for direct foreground
    work while lower-priority work is active. This trades a little peak
    throughput for predictable interaction latency under heavy library load.
    """

    def __init__(
        self,
        *,
        max_workers: int = 4,
        reserved_foreground_slots: int = 1,
        lane_limits: dict[str, int] | None = None,
    ) -> None:
        self.max_workers = max(1, int(max_workers))
        self.reserved_foreground_slots = max(
            0,
            min(int(reserved_foreground_slots), self.max_workers - 1),
        )
        defaults = {
            "foreground": self.max_workers,
            "visible": max(1, self.max_workers - self.reserved_foreground_slots),
            "prefetch": 1,
            "background": 1,
            "idle": 1,
        }
        supplied = dict(lane_limits or {})
        self._lane_limits = {
            lane: max(1, int(supplied.get(lane, defaults[lane])))
            for lane in PRIORITY_ORDER
        }

        self._condition = threading.Condition()
        self._pending: list[_ScheduledJob] = []
        self._sequence = itertools.count()
        self._active_total = 0
        self._active_by_priority = {lane: 0 for lane in PRIORITY_ORDER}
        self._submitted = 0
        self._completed = 0
        self._failed = 0
        self._peak_active = 0
        self._stopping = False

        self._threads = [
            threading.Thread(
                target=self._worker,
                name=f"MelodexBackground-{index + 1}",
                daemon=True,
            )
            for index in range(self.max_workers)
        ]
        for thread in self._threads:
            thread.start()

    def submit(
        self,
        callback: Callable[[], None],
        *,
        priority: str = "background",
        name: str = "",
    ) -> bool:
        lane = str(priority or "background").strip().lower()
        if lane not in PRIORITY_ORDER:
            raise ValueError(f"Unknown background priority: {priority!r}")
        with self._condition:
            if self._stopping:
                return False
            sequence = next(self._sequence)
            heapq.heappush(
                self._pending,
                _ScheduledJob(
                    (PRIORITY_ORDER[lane], sequence),
                    lane,
                    callback,
                    str(name or ""),
                ),
            )
            self._submitted += 1
            self._condition.notify_all()
            return True

    def snapshot(self) -> dict[str, object]:
        with self._condition:
            pending = {lane: 0 for lane in PRIORITY_ORDER}
            for job in self._pending:
                pending[job.priority] += 1
            return {
                "max_workers": self.max_workers,
                "reserved_foreground_slots": self.reserved_foreground_slots,
                "active_total": self._active_total,
                "peak_active": self._peak_active,
                "submitted": self._submitted,
                "completed": self._completed,
                "failed": self._failed,
                "pending_total": len(self._pending),
                "active_by_priority": dict(self._active_by_priority),
                "pending_by_priority": pending,
            }

    def shutdown(self, *, wait: bool = False) -> None:
        with self._condition:
            self._stopping = True
            self._pending.clear()
            self._condition.notify_all()
        if wait:
            for thread in self._threads:
                thread.join(timeout=1.0)

    def _worker(self) -> None:
        while True:
            with self._condition:
                job = self._take_next_locked()
                while job is None and not self._stopping:
                    self._condition.wait()
                    job = self._take_next_locked()
                if job is None and self._stopping:
                    return
                assert job is not None
                self._active_total += 1
                self._active_by_priority[job.priority] += 1
                self._peak_active = max(self._peak_active, self._active_total)

            failed = False
            try:
                job.callback()
            except Exception:
                failed = True
            finally:
                with self._condition:
                    self._active_total -= 1
                    self._active_by_priority[job.priority] -= 1
                    self._completed += 1
                    if failed:
                        self._failed += 1
                    self._condition.notify_all()

    def _take_next_locked(self) -> _ScheduledJob | None:
        if not self._pending:
            return None

        skipped: list[_ScheduledJob] = []
        selected: _ScheduledJob | None = None
        while self._pending:
            job = heapq.heappop(self._pending)
            if self._can_start_locked(job):
                selected = job
                break
            skipped.append(job)
        for job in skipped:
            heapq.heappush(self._pending, job)
        return selected

    def _can_start_locked(self, job: _ScheduledJob) -> bool:
        if self._active_total >= self.max_workers:
            return False
        if (
            self._active_by_priority[job.priority]
            >= self._lane_limits[job.priority]
        ):
            return False

        if job.priority != "foreground" and self.reserved_foreground_slots:
            lower_priority_ceiling = (
                self.max_workers - self.reserved_foreground_slots
            )
            if self._active_total >= lower_priority_ceiling:
                return False

        return True


__all__ = ["BackgroundScheduler", "PRIORITY_ORDER"]
