from __future__ import annotations

import threading
import time

from melodex.background_scheduler import BackgroundScheduler


def test_foreground_work_jumps_ahead_of_queued_idle_work():
    scheduler = BackgroundScheduler(max_workers=1)
    blocker_started = threading.Event()
    release = threading.Event()
    order: list[str] = []

    def blocker():
        blocker_started.set()
        release.wait(2)
        order.append("blocker")

    try:
        scheduler.submit(blocker, priority="background", label="blocker")
        assert blocker_started.wait(1)

        idle = scheduler.submit(
            lambda: order.append("idle"),
            priority="idle",
            label="idle",
        )
        foreground = scheduler.submit(
            lambda: order.append("foreground"),
            priority="foreground",
            label="foreground",
        )

        release.set()
        assert scheduler.wait_for_idle(2)
        assert foreground.done()
        assert idle.done()
        assert order == ["blocker", "foreground", "idle"]
    finally:
        scheduler.shutdown(wait=True)


def test_scheduler_enforces_global_worker_cap():
    scheduler = BackgroundScheduler(max_workers=3)
    release = threading.Event()
    lock = threading.Lock()
    active = 0
    peak = 0
    started = threading.Event()

    def work():
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if peak >= 3:
                started.set()
        release.wait(2)
        with lock:
            active -= 1

    try:
        for _ in range(8):
            scheduler.submit(work, priority="background")
        assert started.wait(1)
        time.sleep(0.05)
        assert peak == 3
        assert scheduler.snapshot()["active_total"] == 3

        release.set()
        assert scheduler.wait_for_idle(2)
        assert scheduler.snapshot()["max_active_observed"] == 3
    finally:
        scheduler.shutdown(wait=True)


def test_lane_limit_blocks_same_lane_without_blocking_other_lanes():
    scheduler = BackgroundScheduler(
        max_workers=4,
        lane_limits={"disk": 1, "network": 2},
    )
    release = threading.Event()
    disk_started = 0
    network_started = threading.Event()
    lock = threading.Lock()

    def disk_work():
        nonlocal disk_started
        with lock:
            disk_started += 1
        release.wait(2)

    def network_work():
        network_started.set()
        release.wait(2)

    try:
        scheduler.submit(disk_work, lane="disk", priority="visible")
        scheduler.submit(disk_work, lane="disk", priority="visible")
        scheduler.submit(network_work, lane="network", priority="background")

        assert network_started.wait(1)
        time.sleep(0.05)
        with lock:
            assert disk_started == 1

        snapshot = scheduler.snapshot()
        assert snapshot["active_by_lane"]["disk"] == 1
        assert snapshot["active_by_lane"]["network"] == 1
        assert snapshot["pending_by_lane"]["disk"] == 1

        release.set()
        assert scheduler.wait_for_idle(2)
        with lock:
            assert disk_started == 2
    finally:
        scheduler.shutdown(wait=True)


def test_snapshot_reports_priority_and_queue_high_water():
    scheduler = BackgroundScheduler(max_workers=1)
    release = threading.Event()
    started = threading.Event()

    def blocker():
        started.set()
        release.wait(2)

    try:
        scheduler.submit(blocker, priority="foreground", lane="default")
        assert started.wait(1)

        scheduler.submit(lambda: None, priority="visible", lane="disk")
        scheduler.submit(lambda: None, priority="prefetch", lane="prefetch")
        scheduler.submit(lambda: None, priority="idle", lane="idle")

        snapshot = scheduler.snapshot()
        assert snapshot["pending_total"] == 3
        assert snapshot["pending_by_priority"] == {
            "visible": 1,
            "prefetch": 1,
            "idle": 1,
        }
        assert snapshot["queue_high_water"] >= 3

        release.set()
        assert scheduler.wait_for_idle(2)
    finally:
        scheduler.shutdown(wait=True)
