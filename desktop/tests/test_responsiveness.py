from __future__ import annotations

from melodex.responsiveness import ResponsivenessTracker


def test_tracker_records_ci_violation_with_recent_action():
    tracker = ResponsivenessTracker(
        interval_ms=50,
        long_task_threshold_ms=50,
        ci_threshold_ms=250,
        serious_threshold_ms=500,
        blocker_threshold_ms=1000,
    )
    tracker.reset_clock(10.0)
    tracker.mark_action("sources:selection", 10.02)

    assert tracker.observe(10.10) is None

    event = tracker.observe(10.55)
    assert event is not None
    assert event["severity"] == "ci_violation"
    assert event["action"] == "sources:selection"
    assert event["gap_ms"] == 450.0
    assert event["delay_ms"] == 400.0

    summary = tracker.summary()
    assert summary["total_stalls"] == 1
    assert summary["long_tasks"] == 0
    assert summary["ci_violations"] == 1
    assert summary["serious_stalls"] == 0
    assert summary["release_blockers"] == 0
    assert summary["max_delay_ms"] == 400.0
    assert summary["recent_stalls"][0]["action"] == "sources:selection"


def test_tracker_classifies_long_serious_and_release_blocker():
    tracker = ResponsivenessTracker(interval_ms=50)
    tracker.reset_clock(1.0)

    long_event = tracker.observe(1.12)
    assert long_event is not None
    assert long_event["severity"] == "long_task"
    assert long_event["delay_ms"] == 70.0

    serious_event = tracker.observe(1.72)
    assert serious_event is not None
    assert serious_event["severity"] == "serious"
    assert serious_event["delay_ms"] == 550.0

    blocker_event = tracker.observe(2.97)
    assert blocker_event is not None
    assert blocker_event["severity"] == "release_blocker"
    assert blocker_event["delay_ms"] == 1200.0

    summary = tracker.summary()
    assert summary["long_tasks"] == 1
    assert summary["serious_stalls"] == 1
    assert summary["release_blockers"] == 1


def test_tracker_reports_p99_gap_and_interaction_acknowledgement():
    tracker = ResponsivenessTracker(interval_ms=50)
    tracker.reset_clock(0.0)

    for timestamp in (0.05, 0.10, 0.15, 0.20, 0.30):
        tracker.observe(timestamp)

    tracker.record_interaction("navigate:home", 18.0)
    tracker.record_interaction("navigate:sources", 72.0)
    tracker.record_interaction("discover:search", 115.0)

    summary = tracker.summary()
    assert summary["p99_event_loop_gap_ms"] == 100.0
    assert summary["max_gap_ms"] == 100.0
    assert summary["interaction_count"] == 3
    assert summary["interaction_p95_ms"] == 115.0
    assert summary["interaction_max_ms"] == 115.0
    assert summary["interactions_over_50_ms"] == 2
    assert summary["interactions_over_100_ms"] == 1


def test_tracker_does_not_attach_stale_action():
    tracker = ResponsivenessTracker(
        interval_ms=50,
        long_task_threshold_ms=50,
        action_ttl_seconds=1.0,
    )
    tracker.reset_clock(1.0)
    tracker.mark_action("navigate:sources", 1.0)

    event = tracker.observe(3.0)
    assert event is not None
    assert event["action"] == ""
