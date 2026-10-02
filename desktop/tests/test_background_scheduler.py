from __future__ import annotations

import threading
import time

import pytest

from melodex.background_scheduler import BackgroundScheduler


def _wait_for(predicate, timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def test_scheduler_prioritizes_visible_work_over_idle_queue() -> None:
    scheduler = BackgroundScheduler(
        max_workers=1,
        reserved_foreground_slots=0,
    )
    release = threading.Event()
    blocker_started = threading.Event()
    idle_done = threading.Event()
    order: list[str] = []
    lock = threading.Lock()

    def record(name: str) -> None:
        with lock:
            order.append(name)

    def blocker() -> None:
        record("blocker")
        blocker_started.set()
        release.wait(2.0)

    try:
        scheduler.submit(blocker, priority="foreground", name="blocker")
        assert blocker_started.wait(1.0)

        scheduler.submit(
            lambda: (record("idle"), idle_done.set()),
            priority="idle",
            name="idle",
        )
        scheduler.submit(
            lambda: record("visible"),
            priority="visible",
            name="visible",
        )

        release.set()
        assert idle_done.wait(1.0)
        assert order == ["blocker", "visible", "idle"]
    finally:
        release.set()
        scheduler.shutdown(wait=True)


def test_scheduler_reserves_capacity_for_foreground_work() -> None:
    scheduler = BackgroundScheduler(
        max_workers=4,
        reserved_foreground_slots=1,
    )
    release = threading.Event()
    started = {
        lane: threading.Event()
        for lane in ("prefetch", "background", "idle")
    }
    foreground_started = threading.Event()

    def blocking(lane: str) -> None:
        started[lane].set()
        release.wait(2.0)

    try:
        for lane in ("prefetch", "background", "idle"):
            scheduler.submit(
                lambda lane=lane: blocking(lane),
                priority=lane,
                name=f"{lane}-blocker",
            )

        assert all(event.wait(1.0) for event in started.values())
        assert _wait_for(
            lambda: scheduler.snapshot()["active_total"] == 3,
            timeout=1.0,
        )

        scheduler.submit(
            foreground_started.set,
            priority="foreground",
            name="foreground-check",
        )
        assert foreground_started.wait(0.5)

        snapshot = scheduler.snapshot()
        assert snapshot["max_workers"] == 4
        assert snapshot["reserved_foreground_slots"] == 1
        assert snapshot["peak_active"] <= 4
    finally:
        release.set()
        scheduler.shutdown(wait=True)


def test_background_lane_is_serialized_and_queue_is_observable() -> None:
    scheduler = BackgroundScheduler(
        max_workers=4,
        reserved_foreground_slots=1,
    )
    release = threading.Event()
    first_started = threading.Event()

    def blocking_background() -> None:
        first_started.set()
        release.wait(2.0)

    try:
        scheduler.submit(
            blocking_background,
            priority="background",
            name="background-0",
        )
        assert first_started.wait(1.0)

        for index in range(3):
            scheduler.submit(
                lambda: None,
                priority="background",
                name=f"background-{index + 1}",
            )

        assert _wait_for(
            lambda: scheduler.snapshot()["pending_by_priority"]["background"]
            == 3,
            timeout=1.0,
        )
        snapshot = scheduler.snapshot()
        assert snapshot["active_by_priority"]["background"] == 1
        assert snapshot["pending_by_priority"]["background"] == 3
    finally:
        release.set()
        scheduler.shutdown(wait=True)


def test_scheduler_rejects_unknown_priority() -> None:
    scheduler = BackgroundScheduler(max_workers=1, reserved_foreground_slots=0)
    try:
        with pytest.raises(ValueError):
            scheduler.submit(lambda: None, priority="urgent")
    finally:
        scheduler.shutdown(wait=True)
