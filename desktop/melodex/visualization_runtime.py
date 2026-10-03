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
    animation_enabled: bool


def resolve_visual_quality(requested: str, effective: str = "normal") -> VisualQuality:
    """Return the rendering budget while preserving the existing UI presets."""

    requested = requested if requested in {"auto", "eco", "high", "battery"} else "auto"

    if requested == "battery":
        return VisualQuality("battery", 0, 1000, 0.45, 24, 1, False)
    if requested == "eco":
        return VisualQuality("eco", 10, 100, 0.50, 32, 2, True)
    if requested == "high":
        return VisualQuality("high", 30, 34, 2.00, 48, 4, True)

    # Auto keeps the existing 15 fps cadence, but can halve scene detail after
    # repeated slow frames without changing playback or the visual meaning.
    eco = effective == "eco"
    return VisualQuality(
        "auto-eco" if eco else "auto",
        15,
        67,
        0.50 if eco else 1.00,
        32 if eco else 48,
        2 if eco else 3,
        True,
    )
