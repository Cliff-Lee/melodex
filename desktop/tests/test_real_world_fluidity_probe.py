from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "real_world_fluidity_probe.py"


def _module():
    spec = importlib.util.spec_from_file_location("p14_real_world_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_p14_probe_small_profile_exercises_reported_paths():
    module = _module()

    result = module.run_probe(
        track_count=240,
        pan_steps=4,
        resize_cycles=3,
        pause_ms=0,
        p99_gap_limit_ms=1000.0,
    )

    assert result["schema"] == 1
    assert result["campaign"] == "P14a-real-world-fluidity-baseline"
    assert result["track_count"] == 240
    assert result["album_count"] > 0
    assert result["album_wall"]["pan_steps"] == 4
    assert result["resize"]["cycles"] == 3
    assert "clear" in result["library_search_ms"]
    assert "p99_event_loop_gap_ms" in result["responsiveness"]
    assert set(result["checks"]) >= {
        "no_release_blocker",
        "no_serious_stall",
        "p99_event_loop_gap_within_budget",
        "search_clear_under_250ms",
        "pan_p95_under_100ms",
        "resize_p95_under_100ms",
    }
    assert result["limitations"]
