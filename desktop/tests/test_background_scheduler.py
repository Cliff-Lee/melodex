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
    scheduler = BackgroundScheduler(max_workers=3, foreground_reserve=0)
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


def test_background_work_leaves_one_slot_for_foreground():
    scheduler = BackgroundScheduler(max_workers=4, foreground_reserve=1)
    release = threading.Event()
    background_started = threading.Event()
    foreground_started = threading.Event()
    lock = threading.Lock()
    running_background = 0

    def background_work():
        nonlocal running_background
        with lock:
            running_background += 1
            if running_background >= 3:
                background_started.set()
        release.wait(2)

    def foreground_work():
        foreground_started.set()
        release.wait(2)

    try:
        for _ in range(6):
            scheduler.submit(
                background_work,
                priority="background",
                lane="default",
            )

        assert background_started.wait(1)
        time.sleep(0.05)
        with lock:
            assert running_background == 3
        assert scheduler.snapshot()["active_total"] == 3

        scheduler.submit(
            foreground_work,
            priority="foreground",
            lane="default",
        )
        assert foreground_started.wait(1)
        assert scheduler.snapshot()["active_total"] == 4

        release.set()
        assert scheduler.wait_for_idle(2)
    finally:
        scheduler.shutdown(wait=True)


def test_background_can_fill_capacity_once_foreground_is_active():
    scheduler = BackgroundScheduler(max_workers=4, foreground_reserve=1)
    release = threading.Event()
    lock = threading.Lock()
    started = {"background": 0, "foreground": 0}
    two_background = threading.Event()
    third_background = threading.Event()
    foreground_started = threading.Event()

    def background_work():
        with lock:
            started["background"] += 1
            count = started["background"]
            if count >= 2:
                two_background.set()
            if count >= 3:
                third_background.set()
        release.wait(2)

    def foreground_work():
        with lock:
            started["foreground"] += 1
        foreground_started.set()
        release.wait(2)

    try:
        for _ in range(2):
            scheduler.submit(background_work, priority="background")
        assert two_background.wait(1)

        scheduler.submit(foreground_work, priority="foreground")
        assert foreground_started.wait(1)
        assert scheduler.snapshot()["active_total"] == 3

        # The foreground task already occupies the reserved capacity, so a
        # third background task may use the remaining fourth worker.
        scheduler.submit(background_work, priority="background")
        assert third_background.wait(1)
        snapshot = scheduler.snapshot()
        assert snapshot["active_total"] == 4
        assert snapshot["active_by_priority"]["background"] == 3
        assert snapshot["active_by_priority"]["foreground"] == 1

        release.set()
        assert scheduler.wait_for_idle(2)
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


def test_replace_by_key_cancels_queued_stale_work():
    scheduler = BackgroundScheduler(max_workers=1, foreground_reserve=0)
    release = threading.Event()
    started = threading.Event()
    ran: list[str] = []

    def blocker():
        started.set()
        release.wait(2)

    try:
        scheduler.submit(blocker, priority="foreground")
        assert started.wait(1)

        old = scheduler.submit(
            lambda: ran.append("old"),
            priority="foreground",
            key="discover-search",
            replace=True,
        )
        newest = scheduler.submit(
            lambda: ran.append("new"),
            priority="foreground",
            key="discover-search",
            replace=True,
        )

        assert old.cancelled()
        snapshot = scheduler.snapshot()
        assert snapshot["pending_total"] == 1
        assert snapshot["stale_queued_cancelled"] >= 1

        release.set()
        assert scheduler.wait_for_idle(2)
        assert newest.done()
        assert ran == ["new"]
    finally:
        scheduler.shutdown(wait=True)


def test_replaced_running_task_result_is_suppressed():
    from melodex.background_scheduler import StaleTaskError

    scheduler = BackgroundScheduler(max_workers=2, foreground_reserve=0)
    old_started = threading.Event()
    release_old = threading.Event()

    def old_work():
        old_started.set()
        release_old.wait(2)
        return "old"

    try:
        old = scheduler.submit(
            old_work,
            priority="foreground",
            key="visual-context",
            replace=True,
        )
        assert old_started.wait(1)

        newest = scheduler.submit(
            lambda: "new",
            priority="foreground",
            key="visual-context",
            replace=True,
        )
        assert newest.result(timeout=1) == "new"

        release_old.set()
        try:
            old.result(timeout=1)
            raise AssertionError("stale running result should not be delivered")
        except StaleTaskError:
            pass

        snapshot = scheduler.snapshot()
        assert snapshot["stale_results_suppressed"] >= 1
    finally:
        scheduler.shutdown(wait=True)


def test_cancel_key_invalidates_running_and_queued_work():
    from melodex.background_scheduler import StaleTaskError

    scheduler = BackgroundScheduler(max_workers=1, foreground_reserve=0)
    started = threading.Event()
    release = threading.Event()

    def running():
        started.set()
        release.wait(2)
        return "obsolete"

    try:
        active = scheduler.submit(
            running,
            priority="background",
            key="next-track-prefetch",
        )
        assert started.wait(1)
        queued = scheduler.submit(
            lambda: "queued",
            priority="prefetch",
            key="next-track-prefetch",
        )

        cancelled = scheduler.cancel_key("next-track-prefetch")
        assert cancelled == 1
        assert queued.cancelled()

        release.set()
        try:
            active.result(timeout=1)
            raise AssertionError("invalidated running result should be stale")
        except StaleTaskError:
            pass

        snapshot = scheduler.snapshot()
        assert snapshot["invalidations"] >= 1
        assert snapshot["stale_queued_cancelled"] >= 1
        assert snapshot["stale_results_suppressed"] >= 1
    finally:
        scheduler.shutdown(wait=True)


def test_rapid_latest_wins_submissions_do_not_grow_pending_queue():
    scheduler = BackgroundScheduler(max_workers=1, foreground_reserve=0)
    release = threading.Event()
    started = threading.Event()

    def blocker():
        started.set()
        release.wait(2)

    try:
        scheduler.submit(blocker, priority="foreground")
        assert started.wait(1)

        latest = None
        for index in range(50):
            latest = scheduler.submit(
                lambda value=index: value,
                priority="foreground",
                key="discover-search",
                replace=True,
            )
            assert scheduler.snapshot()["pending_total"] <= 1

        release.set()
        assert scheduler.wait_for_idle(2)
        assert latest is not None
        assert latest.result() == 49
        assert scheduler.snapshot()["stale_queued_cancelled"] >= 49
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
