from __future__ import annotations

import math

from melodex.music_map_alignment import align_projection
from melodex.music_map_clusters import (
    cluster_grid_size, cluster_mapped_positions, stable_cluster_grid_size,
)


def _points(n: int = 16) -> dict[str, tuple[float, float]]:
    return {
        f"track-{i:02d}": (
            -0.65 + (i % 4) * 0.35,
            -0.55 + (i // 4) * 0.30,
        )
        for i in range(n)
    }


def test_projection_alignment_resolves_axis_swap_without_warping_graph():
    previous = _points()
    swapped = {ref: (-y, x) for ref, (x, y) in previous.items()}
    aligned = align_projection(swapped, previous)
    for ref, (x, y) in previous.items():
        ax, ay = aligned[ref]
        assert math.isclose(ax, x, abs_tol=1e-8)
        assert math.isclose(ay, y, abs_tol=1e-8)

    # A pure PCA orientation change must leave pairwise display distances
    # intact. The original graph relationships are never passed to alignment.
    for a, b in (("track-00", "track-11"), ("track-03", "track-09")):
        before = math.dist(previous[a], previous[b])
        after = math.dist(aligned[a], aligned[b])
        assert math.isclose(before, after, rel_tol=1e-8)


def test_projection_alignment_is_conservative_with_large_library_changes():
    previous = _points()
    current = {
        ref: (-y, x) for ref, (x, y) in previous.items()
        if ref in {"track-00", "track-01", "track-02", "track-03"}
    }
    current["new-artist"] = (0.4, 0.3)
    assert align_projection(current, previous) == current
    assert align_projection(previous, previous) == previous


def test_projection_alignment_preserves_existing_points_when_new_track_arrives():
    previous = _points()
    revised = {ref: (-y, x) for ref, (x, y) in previous.items()}
    revised["new-track"] = (0.4, -0.1)
    aligned = align_projection(revised, previous)
    for ref in previous:
        assert math.dist(aligned[ref], previous[ref]) < 1e-8
    assert "new-track" in aligned


def test_zoom_hysteresis_prevents_flickering_at_cluster_boundaries():
    assert stable_cluster_grid_size(0.91, None) == 190.0
    assert stable_cluster_grid_size(0.93, 190.0) == 190.0
    assert stable_cluster_grid_size(1.01, 190.0) == 125.0
    assert stable_cluster_grid_size(0.90, 125.0) == 125.0
    assert stable_cluster_grid_size(0.84, 125.0) == 190.0
    assert stable_cluster_grid_size(1.39, 125.0) == 125.0
    assert stable_cluster_grid_size(1.47, 125.0) == 0.0
    assert stable_cluster_grid_size(1.34, 0.0) == 0.0
    assert stable_cluster_grid_size(1.30, 0.0) == 125.0

    positions = {f"track-{i}": (20.0 + i % 8, 40.0 + i // 8)
                 for i in range(80)}
    assert cluster_mapped_positions(
        positions, scale=0.93, cell_size=190.0
    )  # held overview still uses large, stable grouping
    assert cluster_mapped_positions(
        positions, scale=1.39, cell_size=0.0
    ) == []  # expanded mode never leaks stale groups
