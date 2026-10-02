from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.fluid_soak import evaluate_report, run_soak


def test_soak_report_budget_evaluator_flags_regressions():
    report = {
        "responsiveness": {
            "ci_violations": 1,
            "serious_stalls": 0,
            "release_blockers": 0,
            "interaction_p95_ms": 125.0,
            "interactions_over_100_ms": 3,
        },
        "memory": {
            "rss_growth_mib": 4.0,
            "python_growth_mib": 1.0,
        },
        "scheduler": {
            "pending_total": 0,
            "active_total": 0,
            "queue_high_water": 2,
            "invalidations": 3,
            "stale_queued_cancelled": 2,
            "stale_results_suppressed": 1,
        },
        "cycles": {"median_growth_ratio": 1.1},
        "widgets": {
            "hydrated_track_rows": 8,
            "hydrated_track_row_budget": 20,
        },
    }

    passed, failures = evaluate_report(report)
    assert passed is False
    assert "event-loop CI violations" in failures
    assert "interaction p95 latency" in failures
    assert "interactions over 100 ms" in failures


def test_small_soak_smoke_run_stays_bounded():
    import pytest

    try:
        report = run_soak(
            track_count=240,
            minimum_cycles=18,
            duration_seconds=0.4,
            warmup_cycles=3,
            pace_ms=1,
        )
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    assert report["schema"] == 1
    assert report["profile_tracks"] == 240
    assert report["cycles_completed"] >= 18
    assert report["scheduler"]["pending_total"] == 0
    assert report["scheduler"]["active_total"] == 0
    assert report["scheduler"]["invalidations"] > 0
    assert (
        report["widgets"]["hydrated_track_rows"]
        <= report["widgets"]["hydrated_track_row_budget"]
    )
