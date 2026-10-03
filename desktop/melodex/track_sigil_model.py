"""Qt-free deterministic geometry model for Melodex Track Sigil identity."""

from __future__ import annotations


def _unit_from_seed(seed: int, shift: int) -> float:
    return ((int(seed) >> shift) & 0xFF) / 255.0


def sigil_radii(seed: int, points: int = 10) -> tuple[float, ...]:
    """Return stable normalized radii for one recording identity."""

    points = max(6, min(16, int(points)))
    seed = int(seed)
    values = []
    for index in range(points):
        shift = (index * 5) % 56
        primary = _unit_from_seed(seed, shift)
        secondary = _unit_from_seed(seed ^ 0x9E3779B97F4A7C15, (shift + 17) % 56)
        values.append(0.66 + 0.22 * primary + 0.08 * secondary)
    return tuple(values)
