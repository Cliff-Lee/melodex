from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from melodex.visualization_profile import build_visual_profile
from melodex.visualization_runtime import (
    VisualPerformanceGovernor,
    VisualState,
    resolve_visual_quality,
    sample_visual_state,
)


def test_visual_state_is_bounded_and_uses_cached_energy_curve():
    profile = build_visual_profile(
        {"artist": "Example", "title": "Track", "duration": 200},
        {
            "bpm": 120,
            "energy": 0.6,
            "spectral_centroid": 1850,
            "onset_density": 0.12,
            "energy_curve": [0.0, 0.4, 0.8, 1.0],
        },
    )
    state = sample_visual_state(profile, 0.5, math.pi / 2)

    assert math.isclose(state.energy, 0.6)
    assert state.flow_available
    for value in (
        state.progress,
        state.energy,
        state.brightness,
        state.rhythm,
        state.warmth,
        state.density,
        state.pulse,
        state.glow,
        state.drift,
    ):
        assert 0.0 <= value <= 1.0
    assert 0.0 <= state.tempo_phase < math.tau


def test_visual_state_is_deterministic_for_same_moment():
    profile = build_visual_profile(
        {"artist": "Example", "title": "Track"},
        {"bpm": 98, "energy": 0.42, "onset_density": 0.08},
    )
    assert sample_visual_state(profile, 0.37, 1.2) == sample_visual_state(profile, 0.37, 1.2)
    assert sample_visual_state(None, 0.5, 2.0) == VisualState.idle()


def test_quality_policy_preserves_existing_fps_and_bounds_detail():
    auto = resolve_visual_quality("auto")
    auto_eco = resolve_visual_quality("auto", "eco")
    eco = resolve_visual_quality("eco")
    high = resolve_visual_quality("high")
    battery = resolve_visual_quality("battery")

    assert (auto.fps, auto.timer_interval_ms, auto.detail_scale) == (15, 67, 1.0)
    assert (auto_eco.fps, auto_eco.timer_interval_ms, auto_eco.detail_scale) == (12, 84, 0.55)
    assert (eco.fps, eco.timer_interval_ms, eco.detail_scale) == (10, 100, 0.5)
    assert (high.fps, high.timer_interval_ms, high.detail_scale) == (30, 34, 1.5)
    assert not battery.animation_enabled
    assert battery.fps == 0
    assert high.max_detail <= 48
    assert auto.max_particles <= 24
    assert eco.max_glows <= auto.max_glows
    assert auto.artwork_cache_px <= 960
    assert auto.paint_budget_ms <= 16.0


def test_unknown_quality_falls_back_to_auto():
    assert resolve_visual_quality("something-new") == resolve_visual_quality("auto")


def test_performance_governor_reduces_only_after_repeated_expensive_frames():
    governor = VisualPerformanceGovernor()
    # First paints are diagnostics-only so one-time Qt cache setup cannot
    # immediately demote visual quality.
    for _ in range(governor.grace_frames):
        assert governor.observe(40.0) is None
    assert governor.observe(17.0) is None
    assert governor.observe(17.5) is None
    assert governor.observe(18.0) == "eco"
    assert governor.effective == "eco"
    assert governor.reductions == 1


def test_performance_governor_recovers_with_hysteresis():
    governor = VisualPerformanceGovernor(effective="eco")
    for _ in range(governor.grace_frames):
        assert governor.observe(2.0) is None
    for _ in range(71):
        assert governor.observe(2.0) is None
    assert governor.observe(2.0) == "normal"
    assert governor.effective == "normal"


def test_explicit_quality_does_not_auto_switch():
    governor = VisualPerformanceGovernor()
    for _ in range(10):
        assert governor.observe(40.0, requested="high") is None
    assert governor.effective == "normal"
    assert governor.frames == 10
