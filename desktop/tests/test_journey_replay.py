from __future__ import annotations

from melodex.journey_replay import (
    materialize_route_snapshot,
    portable_route_snapshot,
    summarize_journey_run,
)


def test_route_snapshot_is_ref_independent_and_path_safe():
    route = {
        "found": True,
        "journey": True,
        "mode": "balanced",
        "path_refs": ["a", "b"],
        "hops": [
            {
                "from": "a",
                "to": "b",
                "reason": "Flow similarity 80%",
                "sonic_similarity": 0.8,
            }
        ],
        "stages": [],
    }
    ref_map = {
        "a": {
            "artist": "A",
            "title": "One",
            "album": "X",
            "local_path": "/secret/a.flac",
        },
        "b": {
            "artist": "B",
            "title": "Two",
            "album": "Y",
            "local_path": "/secret/b.flac",
        },
    }
    snapshot = portable_route_snapshot(route, ref_map)
    assert snapshot["tracks"][0]["display"] == "A — One"
    assert "local_path" not in snapshot["tracks"][0]["selector"]
    assert "local_path" not in snapshot["tracks"][1]["selector"]
    assert "/secret" not in str(snapshot)
    assert snapshot["hops"][0]["from_index"] == 0
    assert snapshot["hops"][0]["to_index"] == 1


def test_historical_route_materializes_on_new_map_refs():
    snapshot = {
        "tracks": [
            {"selector": {"artist": "A", "title": "One"}, "display": "A — One"},
            {"selector": {"artist": "B", "title": "Two"}, "display": "B — Two"},
        ]
    }
    ref_map = {
        "new-a": {"artist": "A", "title": "One", "album": ""},
        "new-b": {"artist": "B", "title": "Two", "album": ""},
    }
    result = materialize_route_snapshot(snapshot, ref_map)
    assert result["complete"] is True
    assert result["refs"] == ["new-a", "new-b"]


def test_run_summary_shows_live_divergence_and_decisions():
    run = {
        "id": "run-1",
        "status": "completed",
        "started_at": 1,
        "ended_at": 2,
        "original_route": {
            "tracks": [
                {"display": "A — One"},
                {"display": "B — Two"},
                {"display": "C — Three"},
            ]
        },
        "final_route": {
            "tracks": [
                {"display": "A — One"},
                {"display": "X — New"},
                {"display": "C — Three"},
            ]
        },
    }
    events = [
        {"event_type": "steer", "payload": {"label": "More energy next"}},
        {"event_type": "manual_skip", "payload": {"track": "B — Two"}},
        {"event_type": "replan", "payload": {"reason": "manual skip"}},
    ]
    summary = summarize_journey_run(run, events)
    assert summary["changed"] is True
    assert summary["common_prefix"] == 1
    assert summary["event_counts"]["manual_skip"] == 1
    assert "Steer · More energy next" in summary["decisions"]
    assert "Skip · B — Two" in summary["decisions"]
