from __future__ import annotations

"""Deterministic, local overview grouping for Music Map.

Groups are spatial *summaries* of the existing Flow-feature projection.
They are not genres, inferred factual relationships, or alternative
Pathfinder edges. No library data leaves the machine.
"""

from math import floor
from typing import Iterable


def cluster_grid_size(scale: float) -> float:
    """Return a stable scene-space grid size for the active overview level."""
    if scale < 0.92:
        return 190.0
    if scale < 1.38:
        return 125.0
    return 0.0


def cluster_mapped_positions(
    positions: dict[str, tuple[float, float]],
    *,
    scale: float,
    protected: Iterable[str] = (),
    minimum: int = 3,
) -> list[dict[str, object]]:
    """Group dense feature-map positions with deterministic cell boundaries.

    Protected refs (selected, playing and route tracks) remain individually
    visible. Groups contain only known refs, without changing their
    underlying positions or any musical similarity links.
    """
    if len(positions) < 60:
        return []
    cell_size = cluster_grid_size(float(scale))
    if cell_size <= 0:
        return []
    excluded = set(protected)
    cells: dict[tuple[int, int], list[tuple[str, float, float]]] = {}
    for ref in sorted(positions):
        if ref in excluded:
            continue
        x, y = positions[ref]
        key = (floor(x / cell_size), floor(y / cell_size))
        cells.setdefault(key, []).append((ref, x, y))

    result: list[dict[str, object]] = []
    for cell_key, tracks in sorted(cells.items()):
        if len(tracks) < max(3, int(minimum)):
            continue
        # Use the actual group centroid to choose meaningful representative
        # artwork, but centre the overview tile within its spatial cell so
        # neighbouring dense cells can never draw colliding count badges.
        centroid_x = sum(x for _, x, _ in tracks) / len(tracks)
        centroid_y = sum(y for _, _, y in tracks) / len(tracks)
        representative = min(
            tracks,
            key=lambda row: (
                (row[1] - centroid_x) ** 2 + (row[2] - centroid_y) ** 2,
                row[0],
            ),
        )[0]
        cx = (cell_key[0] + 0.5) * cell_size
        cy = (cell_key[1] + 0.5) * cell_size
        result.append({
            "cell": cell_key,
            "x": cx,
            "y": cy,
            "refs": tuple(ref for ref, _, _ in tracks),
            "representative": representative,
        })
    return result


__all__ = ["cluster_grid_size", "cluster_mapped_positions"]
