from __future__ import annotations

import json

import pytest

from melodex.startup_metrics import StartupTimeline


def test_startup_timeline_records_monotonic_deltas(tmp_path) -> None:
    timeline = StartupTimeline(started_at=10.0)
    timeline.mark("module_ready", now=10.125)
    timeline.mark("ui_ready", now=10.300)

    summary = timeline.summary()
    assert summary["schema"] == 1
    assert summary["total_ms"] == pytest.approx(300.0)
    assert summary["events"] == [
        {
            "phase": "module_ready",
            "elapsed_ms": pytest.approx(125.0),
            "delta_ms": pytest.approx(125.0),
        },
        {
            "phase": "ui_ready",
            "elapsed_ms": pytest.approx(300.0),
            "delta_ms": pytest.approx(175.0),
        },
    ]

    path = timeline.write_json(tmp_path / "startup.json")
    stored = json.loads(path.read_text("utf-8"))
    assert stored["events"][1]["phase"] == "ui_ready"


def test_startup_timeline_rejects_empty_phase() -> None:
    timeline = StartupTimeline(started_at=0.0)
    with pytest.raises(ValueError):
        timeline.mark("   ", now=1.0)
