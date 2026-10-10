from __future__ import annotations

from melodex.music_map_clusters import cluster_grid_size, cluster_mapped_positions


def test_overview_clusters_are_stable_and_never_invent_relationships():
    # The two regions come from positions already supplied by the music model.
    positions = {
        **{f"left-{i:02d}": (20 + i % 4 * 8, 30 + i // 4 * 9) for i in range(36)},
        **{f"right-{i:02d}": (440 + i % 4 * 8, 440 + i // 4 * 9) for i in range(36)},
    }
    first = cluster_mapped_positions(positions, scale=0.7)
    assert first == cluster_mapped_positions(dict(reversed(list(positions.items()))), scale=0.7)
    assert len(first) == 2
    assert sum(len(group["refs"]) for group in first) == 72
    assert all(group["representative"] in group["refs"] for group in first)
    assert not set(first[0]["refs"]) & set(first[1]["refs"])
    assert first[0]["cell"] != first[1]["cell"]

    protected = {"left-00", "right-00"}
    pinned = cluster_mapped_positions(positions, scale=0.7, protected=protected)
    refs = {ref for group in pinned for ref in group["refs"]}
    assert not refs & protected
    assert sum(len(group["refs"]) for group in pinned) == 70
    assert cluster_mapped_positions(positions, scale=1.6) == []
    assert cluster_grid_size(0.9) > cluster_grid_size(1.0)
    assert cluster_grid_size(1.6) == 0.0


def test_groups_only_summarise_actual_dense_areas():
    sparse = {f"r{i}": (i * 210.0, i * 240.0) for i in range(70)}
    assert cluster_mapped_positions(sparse, scale=0.6) == []
    assert cluster_mapped_positions({"a": (10, 10)}, scale=0.6) == []
    nearby = {f"r{i}": (12 + i % 4, 18 + i // 4) for i in range(75)}
    assert len(cluster_mapped_positions(nearby, scale=0.7)) == 1
    assert len(cluster_mapped_positions(nearby, scale=0.7, minimum=76)) == 0
