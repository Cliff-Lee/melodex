from __future__ import annotations

import heapq
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable


PRIORITIES = {
    "foreground": 0,
    "visible": 10,
    "background": 20,
    "prefetch": 30,
    "idle": 40,
}

DEFAULT_LANE_LIMITS = {
    "default": 4,
    "disk": 2,
    "network": 2,
    "analysis": 1,
    "prefetch": 1,
    "idle": 1,
}


@dataclass(order=True)
class _QueuedTask:
    priority_value: int
    sequence: int
    submitted_at: float = field(compare=False)
    fn: Callable[[], Any] = field(compare=False)
    future: Future = field(compare=False)
    lane: str = field(compare=False)
    label: str = field(compare=False)
    priority_name: str = field(compare=False)


class BackgroundScheduler:
    """Bounded priority scheduler for Melodex background work.

    The scheduler deliberately does not preempt work that is already running.
    It controls what starts next, keeps total concurrency bounded and applies
    per-lane limits so speculative/background work cannot flood the machine.
    """

    def __init__(
        self,
        *,
        max_workers: int = 4,
        lane_limits: dict[str, int] | None = None,
        foreground_reserve: int = 1,
        thread_name_prefix: str = "melodex-bg",
    ) -> None:
        self.max_workers = max(1, int(max_workers))
        self.foreground_reserve = max(
            0,
            min(self.max_workers - 1, int(foreground_reserve)),
        )
        configured = dict(DEFAULT_LANE_LIMITS)
        configured.update(dict(lane_limits or {}))
        self.lane_limits = {
            str(name): max(1, int(limit))
            for name, limit in configured.items()
        }

        self._condition = threading.Condition(threading.RLock())
        self._queue: list[_QueuedTask] = []
        self._sequence = 0
        self._closing = False
        self._active_total = 0
        self._active_by_lane: dict[str, int] = {}
        self._submitted = 0
        self._completed = 0
        self._cancelled = 0
        self._queue_high_water = 0
        self._max_active_observed = 0

        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix=thread_name_prefix,
        )
        self._dispatcher = threading.Thread(
            target=self._dispatch_loop,
            name=f"{thread_name_prefix}-dispatcher",
            daemon=True,
        )
        self._dispatcher.start()

    def _priority_value(self, priority: str) -> tuple[str, int]:
        name = str(priority or "background").strip().casefold()
        if name not in PRIORITIES:
            name = "background"
        return name, PRIORITIES[name]

    def _lane_limit(self, lane: str) -> int:
        return min(
            self.max_workers,
            self.lane_limits.get(str(lane or "default"), self.max_workers),
        )

    def submit(
        self,
        fn: Callable[[], Any],
        *,
        priority: str = "background",
        lane: str = "default",
        label: str = "",
    ) -> Future:
        if not callable(fn):
            raise TypeError("fn must be callable")

        priority_name, priority_value = self._priority_value(priority)
        lane_name = str(lane or "default").strip() or "default"
        future: Future = Future()

        with self._condition:
            if self._closing:
                future.set_exception(RuntimeError("Background scheduler is closed"))
                return future

            self._sequence += 1
            self._submitted += 1
            heapq.heappush(
                self._queue,
                _QueuedTask(
                    priority_value=priority_value,
                    sequence=self._sequence,
                    submitted_at=time.monotonic(),
                    fn=fn,
                    future=future,
                    lane=lane_name,
                    label=str(label or ""),
                    priority_name=priority_name,
                ),
            )
            self._queue_high_water = max(self._queue_high_water, len(self._queue))
            self._condition.notify_all()
        return future

    def _pop_runnable_locked(self) -> _QueuedTask | None:
        if self._active_total >= self.max_workers or not self._queue:
            return None

        blocked: list[_QueuedTask] = []
        chosen: _QueuedTask | None = None
        while self._queue:
            task = heapq.heappop(self._queue)
            if task.future.cancelled():
                self._cancelled += 1
                continue

            lane_active = self._active_by_lane.get(task.lane, 0)
            low_priority = task.priority_value >= PRIORITIES["background"]
            low_priority_cap = self.max_workers - self.foreground_reserve
            reserve_blocked = (
                low_priority
                and self.foreground_reserve
                and self._active_total >= low_priority_cap
            )
            if (
                lane_active < self._lane_limit(task.lane)
                and not reserve_blocked
            ):
                chosen = task
                break
            blocked.append(task)

        for task in blocked:
            heapq.heappush(self._queue, task)
        return chosen

    def _dispatch_loop(self) -> None:
        while True:
            with self._condition:
                while True:
                    if self._closing and not self._queue and self._active_total == 0:
                        return
                    task = self._pop_runnable_locked()
                    if task is not None:
                        self._active_total += 1
                        self._active_by_lane[task.lane] = (
                            self._active_by_lane.get(task.lane, 0) + 1
                        )
                        self._max_active_observed = max(
                            self._max_active_observed,
                            self._active_total,
                        )
                        break
                    self._condition.wait(timeout=0.05)

            executor_future = self._executor.submit(task.fn)
            executor_future.add_done_callback(
                lambda completed, queued=task: self._task_completed(queued, completed)
            )

    def _task_completed(self, task: _QueuedTask, completed: Future) -> None:
        try:
            if not task.future.cancelled():
                try:
                    task.future.set_result(completed.result())
                except Exception as exc:
                    task.future.set_exception(exc)
        finally:
            with self._condition:
                self._active_total = max(0, self._active_total - 1)
                lane_active = max(0, self._active_by_lane.get(task.lane, 0) - 1)
                if lane_active:
                    self._active_by_lane[task.lane] = lane_active
                else:
                    self._active_by_lane.pop(task.lane, None)
                self._completed += 1
                self._condition.notify_all()

    def wait_for_idle(self, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._condition:
            while self._queue or self._active_total:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=min(0.05, remaining))
            return True

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            pending_by_priority: dict[str, int] = {}
            pending_by_lane: dict[str, int] = {}
            for task in self._queue:
                if task.future.cancelled():
                    continue
                pending_by_priority[task.priority_name] = (
                    pending_by_priority.get(task.priority_name, 0) + 1
                )
                pending_by_lane[task.lane] = pending_by_lane.get(task.lane, 0) + 1

            return {
                "max_workers": self.max_workers,
                "foreground_reserve": self.foreground_reserve,
                "lane_limits": dict(self.lane_limits),
                "active_total": self._active_total,
                "active_by_lane": dict(self._active_by_lane),
                "pending_total": sum(pending_by_priority.values()),
                "pending_by_priority": pending_by_priority,
                "pending_by_lane": pending_by_lane,
                "submitted": self._submitted,
                "completed": self._completed,
                "cancelled": self._cancelled,
                "queue_high_water": self._queue_high_water,
                "max_active_observed": self._max_active_observed,
            }

    def shutdown(
        self,
        *,
        wait: bool = False,
        cancel_pending: bool = True,
    ) -> None:
        with self._condition:
            if self._closing:
                return
            self._closing = True
            if cancel_pending:
                while self._queue:
                    task = heapq.heappop(self._queue)
                    if task.future.cancel():
                        self._cancelled += 1
            self._condition.notify_all()

        if wait:
            self._dispatcher.join(timeout=5.0)
        self._executor.shutdown(wait=wait, cancel_futures=False)
