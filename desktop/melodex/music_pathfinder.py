from __future__ import annotations

import heapq
import math
from collections import defaultdict
from typing import Any


_KNOWLEDGE_PRIORITY = {
    "song_relation": 0,
    "work": 1,
    "production": 2,
    "composition_credit": 3,
    "performer": 4,
    "artist_relation": 5,
    "place": 6,
    "artist": 7,
    "album": 8,
    "people": 9,
}

_KNOWLEDGE_LABELS = {
    "song_relation": "song relationship",
    "work": "shared work",
    "production": "shared production",
    "composition_credit": "shared composition credit",
    "performer": "shared performer",
    "artist_relation": "artist relationship",
    "place": "shared recording place",
    "artist": "same artist",
    "album": "same album",
    "people": "shared credit",
}


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _pair(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((str(a), str(b))))  # type: ignore[return-value]


def _distance(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 999.0
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(len(a))) / len(a))


def _sonic_similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    va = [float(x) for x in list(a.get("route_vector") or [])]
    vb = [float(x) for x in list(b.get("route_vector") or [])]
    if va and vb and len(va) == len(vb):
        return _clamp(math.exp(-0.58 * _distance(va, vb)))

    # Backward-compatible fallback for older cached/test models. The displayed
    # projection is not the preferred sonic metric, but it is deterministic and
    # better than inventing a relationship when route vectors are unavailable.
    dx = float(a.get("x") or 0.0) - float(b.get("x") or 0.0)
    dy = float(a.get("y") or 0.0) - float(b.get("y") or 0.0)
    projected = math.sqrt(dx * dx + dy * dy)
    return _clamp(math.exp(-1.45 * projected))


def _knowledge_text(edge: dict[str, Any]) -> str:
    kind = str(edge.get("kind") or "knowledge")
    label = str(edge.get("label") or "").strip()
    generic = _KNOWLEDGE_LABELS.get(kind, kind.replace("_", " "))
    if not label or label.casefold() == generic.casefold():
        return generic
    if kind in {"artist", "album", "place", "work"}:
        return f"{generic}: {label}"
    return label


def _top_knowledge(edges: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not edges:
        return None
    return min(
        edges,
        key=lambda edge: (
            _KNOWLEDGE_PRIORITY.get(str(edge.get("kind") or ""), 99),
            -float(edge.get("strength") or 0.0),
            str(edge.get("label") or "").casefold(),
        ),
    )


def _build_connections(
    model: dict[str, Any],
    knowledge_graph: dict[str, Any],
    *,
    sonic_neighbours: int = 6,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
]:
    nodes = {
        str(node.get("ref") or ""): dict(node)
        for node in list(model.get("nodes") or [])
        if isinstance(node, dict) and str(node.get("ref") or "")
    }
    pairs: dict[tuple[str, str], dict[str, Any]] = {}

    # Start with the visible sonic edges.
    for edge in list(model.get("edges") or []):
        if not isinstance(edge, dict):
            continue
        a, b = str(edge.get("a") or ""), str(edge.get("b") or "")
        if a not in nodes or b not in nodes or a == b:
            continue
        key = _pair(a, b)
        row = pairs.setdefault(
            key,
            {"a": key[0], "b": key[1], "sonic": 0.0, "knowledge": []},
        )
        row["sonic"] = max(
            float(row.get("sonic") or 0.0),
            _clamp(float(edge.get("similarity") or 0.0)),
        )

    # Pathfinder uses a slightly denser sonic graph than the visual overlay.
    # This avoids false "no route" results while still using the original
    # standardized Flow feature space, not arbitrary 2D screen distance.
    refs = sorted(nodes)
    k = max(1, min(10, int(sonic_neighbours)))
    for ref in refs:
        ranked: list[tuple[float, str]] = []
        for other in refs:
            if other == ref:
                continue
            similarity = _sonic_similarity(nodes[ref], nodes[other])
            ranked.append((similarity, other))
        ranked.sort(key=lambda row: (-row[0], row[1]))
        for similarity, other in ranked[:k]:
            if similarity < 0.16:
                continue
            key = _pair(ref, other)
            row = pairs.setdefault(
                key,
                {"a": key[0], "b": key[1], "sonic": 0.0, "knowledge": []},
            )
            row["sonic"] = max(float(row.get("sonic") or 0.0), similarity)

    for edge in list(knowledge_graph.get("edges") or []):
        if not isinstance(edge, dict):
            continue
        a, b = str(edge.get("a") or ""), str(edge.get("b") or "")
        if a not in nodes or b not in nodes or a == b:
            continue
        key = _pair(a, b)
        row = pairs.setdefault(
            key,
            {"a": key[0], "b": key[1], "sonic": 0.0, "knowledge": []},
        )
        row["knowledge"].append(dict(edge))

    return nodes, pairs


def _edge_cost(
    connection: dict[str, Any],
    *,
    mode: str,
) -> tuple[float, dict[str, Any]] | None:
    sonic = _clamp(float(connection.get("sonic") or 0.0))
    knowledge = [
        dict(edge)
        for edge in list(connection.get("knowledge") or [])
        if isinstance(edge, dict)
    ]
    top = _top_knowledge(knowledge)
    knowledge_strength = max(
        [float(edge.get("strength") or 0.0) for edge in knowledge] or [0.0]
    )
    knowledge_strength = _clamp(knowledge_strength)

    mode = str(mode or "balanced")
    if mode == "sonic" and sonic <= 0.0:
        return None
    if mode == "knowledge" and not knowledge:
        # Knowledge-first is allowed to cross a sonic bridge only when the
        # factual graph is disconnected. Make that bridge visibly expensive.
        if sonic < 0.34:
            return None
        cost = 3.25 + 1.45 * (1.0 - sonic)
    elif mode == "sonic":
        cost = 0.72 + 1.55 * (1.0 - sonic)
    elif mode == "knowledge":
        cost = 0.48 + 0.95 * (1.0 - knowledge_strength)
        if sonic > 0:
            cost -= 0.10 * sonic
    else:
        # Balanced rewards a pair that is both sonically coherent and actually
        # connected, while still allowing either signal to carry a hop.
        if sonic <= 0.0 and not knowledge:
            return None
        sonic_component = sonic
        factual_component = knowledge_strength
        combined = max(
            sonic_component,
            factual_component,
            0.58 * sonic_component + 0.56 * factual_component,
        )
        cost = 0.68 + 1.18 * (1.0 - _clamp(combined))
        if sonic > 0 and knowledge:
            cost -= 0.18

    # Per-hop penalty stops the algorithm preferring a long chain of tiny gains.
    cost = max(0.28, cost) + 0.17

    reason_bits: list[str] = []
    kinds: list[str] = []
    if top is not None:
        reason_bits.append(_knowledge_text(top))
        kinds.extend(
            sorted(
                {
                    str(edge.get("kind") or "")
                    for edge in knowledge
                    if str(edge.get("kind") or "")
                }
            )
        )
    if sonic > 0:
        sonic_text = f"Flow similarity {sonic:.0%}"
        if mode == "knowledge" and not knowledge:
            sonic_text = f"sonic bridge {sonic:.0%}"
        reason_bits.append(sonic_text)

    return cost, {
        "sonic_similarity": sonic,
        "knowledge_strength": knowledge_strength,
        "knowledge_kinds": kinds,
        "reason": " · ".join(reason_bits or ["graph connection"]),
        "knowledge_edges": knowledge,
    }


class MusicPathNetwork:
    """Reusable prepared Pathfinder graph for repeated local route queries."""

    def __init__(
        self,
        model: dict[str, Any],
        knowledge_graph: dict[str, Any],
        *,
        sonic_neighbours: int = 6,
    ):
        self.model = dict(model or {})
        self.knowledge_graph = dict(knowledge_graph or {})
        self.nodes, self.pairs = _build_connections(
            self.model,
            self.knowledge_graph,
            sonic_neighbours=sonic_neighbours,
        )
        self._adjacency_cache: dict[
            str, dict[str, list[tuple[str, float, dict[str, Any]]]]
        ] = {}

    def adjacency(
        self, mode: str
    ) -> dict[str, list[tuple[str, float, dict[str, Any]]]]:
        mode = str(mode or "balanced")
        if mode not in {"balanced", "sonic", "knowledge"}:
            mode = "balanced"
        cached = self._adjacency_cache.get(mode)
        if cached is not None:
            return cached
        adjacency: dict[str, list[tuple[str, float, dict[str, Any]]]] = defaultdict(list)
        for connection in self.pairs.values():
            weighted = _edge_cost(connection, mode=mode)
            if weighted is None:
                continue
            cost, explanation = weighted
            a, b = str(connection["a"]), str(connection["b"])
            adjacency[a].append((b, cost, dict(explanation)))
            adjacency[b].append((a, cost, dict(explanation)))
        for ref in adjacency:
            adjacency[ref].sort(key=lambda row: (row[1], row[0]))
        self._adjacency_cache[mode] = adjacency
        return adjacency

    def find(
        self,
        start_ref: str,
        end_ref: str,
        *,
        mode: str = "balanced",
        max_hops: int = 12,
    ) -> dict[str, Any]:
        start_ref, end_ref = str(start_ref), str(end_ref)
        mode = str(mode or "balanced")
        if mode not in {"balanced", "sonic", "knowledge"}:
            mode = "balanced"

        if start_ref not in self.nodes or end_ref not in self.nodes:
            return {
                "found": False,
                "mode": mode,
                "path_refs": [],
                "hops": [],
                "reason": "Both endpoints must be visible mapped tracks.",
            }
        if start_ref == end_ref:
            return {
                "found": True,
                "mode": mode,
                "path_refs": [start_ref],
                "hops": [],
                "score": 1.0,
                "cost": 0.0,
                "reason": "Start and destination are the same track.",
            }

        adjacency = self.adjacency(mode)
        max_hops = max(1, min(24, int(max_hops)))
        queue: list[tuple[float, int, str]] = [(0.0, 0, start_ref)]
        best: dict[tuple[str, int], float] = {(start_ref, 0): 0.0}
        previous: dict[
            tuple[str, int],
            tuple[tuple[str, int], dict[str, Any]],
        ] = {}
        final_state: tuple[str, int] | None = None

        while queue:
            cost_so_far, hops, ref = heapq.heappop(queue)
            state = (ref, hops)
            if cost_so_far > best.get(state, float("inf")) + 1e-12:
                continue
            if ref == end_ref:
                final_state = state
                break
            if hops >= max_hops:
                continue
            for other, edge_cost, explanation in adjacency.get(ref, []):
                nxt = (other, hops + 1)
                candidate = cost_so_far + edge_cost
                if candidate + 1e-12 >= best.get(nxt, float("inf")):
                    continue
                best[nxt] = candidate
                previous[nxt] = (state, dict(explanation))
                heapq.heappush(queue, (candidate, hops + 1, other))

        if final_state is None:
            message = (
                "No sonic route was found between these mapped tracks."
                if mode == "sonic"
                else "No route was found within the current mapped sonic/knowledge graph."
            )
            return {
                "found": False,
                "mode": mode,
                "path_refs": [],
                "hops": [],
                "reason": message,
            }

        states: list[tuple[str, int]] = [final_state]
        hop_explanations: list[dict[str, Any]] = []
        cursor = final_state
        while cursor != (start_ref, 0):
            parent, explanation = previous[cursor]
            hop_explanations.append(dict(explanation))
            states.append(parent)
            cursor = parent
        states.reverse()
        hop_explanations.reverse()

        refs = [state[0] for state in states]
        hops_out: list[dict[str, Any]] = []
        used_knowledge = 0
        used_sonic = 0
        for index, explanation in enumerate(hop_explanations):
            if explanation.get("knowledge_kinds"):
                used_knowledge += 1
            if float(explanation.get("sonic_similarity") or 0.0) > 0:
                used_sonic += 1
            hops_out.append(
                {
                    "from": refs[index],
                    "to": refs[index + 1],
                    **explanation,
                }
            )

        total_cost = float(best[final_state])
        score = _clamp(math.exp(-0.34 * total_cost))
        return {
            "found": True,
            "mode": mode,
            "path_refs": refs,
            "hops": hops_out,
            "cost": total_cost,
            "score": score,
            "used_knowledge_hops": used_knowledge,
            "used_sonic_hops": used_sonic,
            "reason": (
                f"{len(hops_out)} hop{'s' if len(hops_out) != 1 else ''} · "
                f"{used_knowledge} factual · {used_sonic} sonic"
            ),
        }


def find_music_path(
    model: dict[str, Any],
    knowledge_graph: dict[str, Any],
    start_ref: str,
    end_ref: str,
    *,
    mode: str = "balanced",
    max_hops: int = 12,
) -> dict[str, Any]:
    """Find an explainable route through mapped local tracks."""

    network = MusicPathNetwork(model, knowledge_graph)
    return network.find(
        start_ref,
        end_ref,
        mode=mode,
        max_hops=max_hops,
    )


__all__ = ["MusicPathNetwork", "find_music_path"]
