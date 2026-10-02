from __future__ import annotations

from melodex.responsiveness import ResponsivenessTracker


def test_tracker_records_stall_with_recent_action():
    tracker = ResponsivenessTracker(
        interval_ms=50,
        stall_threshold_ms=100,
        severe_threshold_ms=250,
        critical_threshold_ms=1000,
    )
    tracker.reset_clock(10.0)
    tracker.mark_action("sources:selection", 10.02)

    assert tracker.observe(10.10) is None

    event = tracker.observe(10.55)
    assert event is not None
    assert event["severity"] == "severe"
    assert event["action"] == "sources:selection"
    assert event["gap_ms"] == 450.0
    assert event["delay_ms"] == 400.0

    summary = tracker.summary()
    assert summary["total_stalls"] == 1
    assert summary["warning_stalls"] == 0
    assert summary["severe_stalls"] == 1
    assert summary["critical_stalls"] == 0
    assert summary["max_delay_ms"] == 400.0
    assert summary["recent_stalls"][0]["action"] == "sources:selection"


def test_tracker_classifies_critical_stall():
    tracker = ResponsivenessTracker(
        interval_ms=50,
        stall_threshold_ms=100,
        severe_threshold_ms=250,
        critical_threshold_ms=1000,
    )
    tracker.reset_clock(1.0)

    event = tracker.observe(2.25)
    assert event is not None
    assert event["severity"] == "critical"
    assert event["delay_ms"] == 1200.0
    assert tracker.summary()["critical_stalls"] == 1


def test_tracker_does_not_attach_stale_action():
    tracker = ResponsivenessTracker(
        interval_ms=50,
        stall_threshold_ms=100,
        action_ttl_seconds=1.0,
    )
    tracker.reset_clock(1.0)
    tracker.mark_action("navigate:sources", 1.0)

    event = tracker.observe(3.0)
    assert event is not None
    assert event["action"] == ""
