"""Shared low-cost visual state and quality policy for Melodex visual experiences.

This module is deliberately Qt-free.  Renderers consume a small semantic state
instead of independently re-deriving musical intensity, pulse and performance
policy.  It is the common foundation for Campaign 13 visual work.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .visualization_profile import VisualProfile, energy_at


def _unit(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True, slots=True)
class VisualState:
    """One cheap, renderer-facing snapshot of the current musical moment.

    The state contains no player, file path, audio handle or Qt object.  Values
    are normalized to 0..1 except tempo_phase, which is radians in 0..tau.
    """

    progress: float
    energy: float
    brightness: float
    rhythm: float
    warmth: float
    density: float
    pulse: float
    glow: float
    drift: float
    tempo_phase: float
    flow_available: bool

    @classmethod
    def idle(cls) -> "VisualState":
        return cls(
            progress=0.0,
            energy=0.0,
            brightness=0.5,
            rhythm=0.0,
            warmth=0.5,
            density=0.0,
            pulse=0.0,
            glow=0.0,
            drift=0.0,
            tempo_phase=0.0,
            flow_available=False,
        )


def sample_visual_state(
    profile: VisualProfile | None,
    progress: float,
    tempo_phase: float,
) -> VisualState:
    """Sample a stable visual state without doing live audio analysis.

    P13a intentionally reuses already-cached Flow/profile information.  Later
    stages can enrich this contract with real band energy or onset events
    without changing every visualizer independently.
    """

    if profile is None:
        return VisualState.idle()

    progress = _unit(progress)
    phase = float(tempo_phase) % math.tau if math.isfinite(float(tempo_phase)) else 0.0
    energy = _unit(energy_at(profile, progress))
    brightness = _unit(profile.brightness)
    rhythm = _unit(profile.rhythm)
    warmth = _unit(1.0 - brightness)
    density = _unit(0.62 * energy + 0.38 * rhythm)

    # The phase comes from cached/known BPM.  This is deliberately a restrained
    # pulse, not a claim of beat-perfect onset detection.
    pulse_shape = 0.5 + 0.5 * math.cos(phase)
    pulse = _unit(pulse_shape * (0.22 + 0.78 * rhythm))
    glow = _unit(0.16 + 0.58 * energy + 0.26 * pulse)
    drift = _unit(0.18 + 0.44 * rhythm + 0.38 * energy)

    return VisualState(
        progress=progress,
        energy=energy,
        brightness=brightness,
        rhythm=rhythm,
        warmth=warmth,
        density=density,
        pulse=pulse,
        glow=glow,
        drift=drift,
        tempo_phase=phase,
        flow_available=bool(profile.flow_available),
    )


@dataclass(frozen=True, slots=True)
class VisualQuality:
    """Bounded rendering policy shared by built-in visual scenes."""

    name: str
    fps: int
    timer_interval_ms: int
    detail_scale: float
    max_detail: int
    glow_layers: int
    max_glows: int
    max_particles: int
    artwork_cache_px: int
    paint_budget_ms: float
    animation_enabled: bool


def resolve_visual_quality(requested: str, effective: str = "normal") -> VisualQuality:
    """Return the rendering budget while preserving the existing UI presets.

    The limits are deliberately conservative because Visuals share the UI
    process with playback controls, library navigation and artwork work.
    """

    requested = requested if requested in {"auto", "eco", "high", "battery"} else "auto"

    if requested == "battery":
        return VisualQuality(
            "battery", 0, 1000, 0.45, 24, 1, 2, 8, 360, 10.0, False
        )
    if requested == "eco":
        return VisualQuality(
            "eco", 10, 100, 0.50, 32, 2, 4, 12, 480, 10.0, True
        )
    if requested == "high":
        return VisualQuality(
            "high", 30, 34, 1.50, 48, 4, 12, 32, 1280, 16.0, True
        )

    eco = effective == "eco"
    if eco:
        return VisualQuality(
            "auto-eco", 12, 84, 0.55, 32, 2, 4, 16, 640, 10.0, True
        )
    return VisualQuality(
        "auto", 15, 67, 1.00, 48, 3, 8, 24, 960, 16.0, True
    )


@dataclass(slots=True)
class VisualPerformanceGovernor:
    """Tiny hysteresis governor for Auto visual quality.

    It reacts to repeated expensive paints, not one-off spikes, and recovers
    only after a sustained run of inexpensive frames.  This keeps visual work
    opportunistic rather than allowing it to compete with the rest of the UI.
    """

    effective: str = "normal"
    frames: int = 0
    slow_frames: int = 0
    fast_frames: int = 0
    ema_ms: float = 0.0
    peak_ms: float = 0.0
    reductions: int = 0
    grace_frames: int = 3

    def reset(self, effective: str = "normal") -> None:
        self.effective = "eco" if effective == "eco" else "normal"
        self.frames = 0
        self.slow_frames = 0
        self.fast_frames = 0
        self.ema_ms = 0.0
        self.peak_ms = 0.0
        self.reductions = 0

    def observe(self, paint_ms: float, requested: str = "auto") -> str | None:
        try:
            paint_ms = max(0.0, float(paint_ms))
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(paint_ms):
            return None

        self.frames += 1
        self.peak_ms = max(self.peak_ms, paint_ms)
        self.ema_ms = paint_ms if self.frames == 1 else self.ema_ms * 0.88 + paint_ms * 0.12

        # Qt text/layout and first-use raster caches can make the first few
        # paints anomalously expensive. They are tracked for diagnostics but do
        # not immediately demote the visual quality.
        if self.frames <= self.grace_frames:
            self.slow_frames = 0
            self.fast_frames = 0
            return None

        if requested != "auto":
            self.slow_frames = 0
            self.fast_frames = 0
            return None

        budget = resolve_visual_quality("auto", self.effective)
        slow_threshold = budget.paint_budget_ms
        fast_threshold = min(7.0, slow_threshold * 0.58)

        if paint_ms > slow_threshold:
            self.slow_frames += 1
            self.fast_frames = 0
        elif paint_ms < fast_threshold:
            self.fast_frames += 1
            self.slow_frames = 0
        else:
            self.slow_frames = 0
            self.fast_frames = 0

        if self.slow_frames >= 3 and self.effective != "eco":
            self.effective = "eco"
            self.reductions += 1
            self.slow_frames = 0
            self.fast_frames = 0
            return "eco"

        if self.fast_frames >= 72 and self.effective == "eco":
            self.effective = "normal"
            self.slow_frames = 0
            self.fast_frames = 0
            return "normal"

        return None

    def snapshot(self) -> dict[str, float | int | str]:
        return {
            "effective": self.effective,
            "frames": self.frames,
            "ema_ms": round(self.ema_ms, 3),
            "peak_ms": round(self.peak_ms, 3),
            "reductions": self.reductions,
        }

