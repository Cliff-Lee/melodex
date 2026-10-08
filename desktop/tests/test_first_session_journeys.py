from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "desktop" / "tools" / "qualify_first_session_journeys.py"


def _module():
    spec = importlib.util.spec_from_file_location("first_session_journeys", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_queue_journeys_preserve_tracks_and_reject_stale_refinement():
    report = _module().qualify_queue_journeys(seeds=4)
    assert [row["journey"] for row in report["journeys"]] == [
        "fresh_local", "partial_nas", "returning_cache"
    ]
    assert all(row["all_candidates_preserved"] for row in report["journeys"])
    assert all(row["late_plan_respects_queue_edits"] for row in report["journeys"])
    assert all(row["time_to_audio_ms"] is None for row in report["journeys"])


def test_missing_diagnostics_never_claim_first_audio():
    report = _module().build_report(seeds=2)
    assert report["passed"] is True
    assert report["real_audio_qualification"] == "pending"
    assert report["desktop_diagnostics"]["time_to_audio_ms"] is None
    assert _module().qualify_diagnostics({})["available"] is False


def test_diagnostics_separate_first_visible_queue_and_audio_timings():
    report = _module().qualify_diagnostics({
        "performance": {
            "first_music": {
                "audio_output_measurement": "position advance",
                "journeys": {
                    "sources": [{
                        "source_id": 4,
                        "source_selected_to_first_track_visible_ms": 120,
                        "source_selected_to_first_queue_ready_ms": 180,
                        "source_selected_to_first_playable_track_ms": 90,
                    }],
                    "plays": [{"play_id": 2, "play_requested_to_audio_output_ms": 420}],
                },
            }
        }
    })
    assert report["time_to_first_choice_ms"] == 120
    assert report["time_to_queue_ms"] == 180
    assert report["time_to_first_playable_ms"] == 90
    assert report["time_to_audio_ms"] == 420
