"""Pure, deterministic visual identity derived from track metadata and cached Flow."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
from typing import Any, Mapping


def _read(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _number(value: Any, name: str) -> float | None:
    raw = _read(value, name)
    try:
        number = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _unit(value: float, fallback: float) -> float:
    if not math.isfinite(value):
        value = fallback
    return max(0.0, min(1.0, float(value)))


def _normalise_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


@dataclass(frozen=True, slots=True)
class VisualProfile:
    """Small renderer input; it contains no local paths or playback handles."""

    fingerprint: str
    seed: int
    hue: int
    bpm: float
    energy: float
    brightness: float
    rhythm: float
    energy_curve: tuple[float, ...]
    flow_available: bool
    artist: str
    title: str


def build_visual_profile(track: Mapping[str, Any] | None, analysis: Any = None) -> VisualProfile:
    """Build a repeatable track fingerprint without reading audio or touching disk.

    ``analysis`` is expected to be an already-cached Flow record. Missing Flow
    analysis gets a deterministic identity seed and safe visual defaults; it is
    never computed here.
    """

    track = track if isinstance(track, Mapping) else {}
    artist = str(track.get("artist") or "")
    title = str(track.get("title") or "")
    duration = _number(track, "duration")
    if duration is None:
        duration_ms = _number(track, "duration_ms")
        duration = duration_ms / 1000.0 if duration_ms is not None else 0.0

    artist_key = _normalise_text(artist)
    title_key = _normalise_text(title)
    # A three-second bucket tolerates small metadata rounding differences while
    # distinguishing most studio/live and edited versions.
    identity = "\x1f".join((artist_key, title_key, str(max(0, round(duration / 3.0)))))
    if not artist_key and not title_key:
        identity = _normalise_text(track.get("provider_id") or track.get("id") or "unknown-track")

    digest = hashlib.blake2b(
        identity.encode("utf-8", "replace"), digest_size=16, person=b"melodex-viz"
    ).digest()
    seed = int.from_bytes(digest[:8], "big")

    bpm = _number(analysis, "bpm")
    if bpm is None or bpm <= 0:
        bpm = 80.0 + float(seed % 81)
    bpm = max(40.0, min(220.0, bpm))

    energy_value = _number(analysis, "energy")
    energy_fallback = ((seed >> 11) % 1000) / 999.0
    energy = _unit(energy_value if energy_value is not None else energy_fallback, energy_fallback)

    centroid = _number(analysis, "spectral_centroid")
    brightness_fallback = ((seed >> 23) % 1000) / 999.0
    brightness = (
        _unit((centroid - 350.0) / 3300.0, brightness_fallback)
        if centroid is not None
        else brightness_fallback
    )

    onset_density = _number(analysis, "onset_density")
    rhythm_fallback = ((seed >> 37) % 1000) / 999.0
    rhythm = (
        _unit(onset_density * 5.0, rhythm_fallback)
        if onset_density is not None
        else rhythm_fallback
    )

    raw_curve = _read(analysis, "energy_curve")
    curve: list[float] = []
    if isinstance(raw_curve, (list, tuple)):
        for raw in raw_curve[:64]:
            try:
                value = float(raw)
            except (TypeError, ValueError, OverflowError):
                continue
            if math.isfinite(value):
                curve.append(_unit(value, energy))
    if len(curve) < 2:
        curve = []
    flow_available = analysis is not None and (
        bool(curve)
        or any(
            _number(analysis, name) is not None
            for name in ("bpm", "energy", "spectral_centroid", "onset_density")
        )
    )

    return VisualProfile(
        fingerprint=digest.hex(),
        seed=seed,
        hue=seed % 360,
        bpm=bpm,
        energy=energy,
        brightness=brightness,
        rhythm=rhythm,
        energy_curve=tuple(curve),
        flow_available=flow_available,
        artist=artist,
        title=title,
    )


def energy_at(profile: VisualProfile, fraction: float) -> float:
    """Sample the cached song contour at a normalized playback position."""

    fraction = _unit(float(fraction), 0.0)
    curve = profile.energy_curve
    if len(curve) < 2:
        return profile.energy
    position = fraction * (len(curve) - 1)
    left = int(position)
    right = min(len(curve) - 1, left + 1)
    blend = position - left
    return curve[left] * (1.0 - blend) + curve[right] * blend
