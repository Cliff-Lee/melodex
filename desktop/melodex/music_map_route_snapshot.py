from __future__ import annotations

"""Fast, isolated copies of exactly the fields used by Music Pathfinder.

Run this on the UI thread before background dispatch. The costly O(n²)
feature-vector neighbour search still belongs exclusively to the worker.
"""

from copy import deepcopy
from typing import Any


def snapshot_pathfinder_inputs(
    model: dict[str, Any],
    knowledge_graph: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Produce independent Pathfinder inputs without copying unrelated UI data.

    Maintain node and edge ordering, feature vectors and all knowledge-edge
    evidence. Dropping unmatched edges is safe because the Pathfinder itself
    ignores edges that do not connect two mapped nodes.
    """
    nodes: list[dict[str, Any]] = []
    refs: set[str] = set()
    for node in model.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        ref = str(node.get("ref") or "")
        if not ref:
            continue
        nodes.append({
            key: deepcopy(node[key])
            for key in ("ref", "route_vector", "x", "y")
            if key in node
        })
        refs.add(ref)

    sonic_edges = [
        {
            key: deepcopy(edge[key])
            for key in ("a", "b", "similarity")
            if key in edge
        }
        for edge in model.get("edges") or []
        if (
            isinstance(edge, dict)
            and str(edge.get("a") or "") in refs
            and str(edge.get("b") or "") in refs
        )
    ]
    knowledge_edges = [
        deepcopy(edge)
        for edge in knowledge_graph.get("edges") or []
        if (
            isinstance(edge, dict)
            and str(edge.get("a") or "") in refs
            and str(edge.get("b") or "") in refs
        )
    ]
    return {"nodes": nodes, "edges": sonic_edges}, {"edges": knowledge_edges}


__all__ = ["snapshot_pathfinder_inputs"]
