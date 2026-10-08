from __future__ import annotations

import math
from typing import Any


FEATURE_NAMES = (
    "energy",
    "tempo",
    "brightness",
    "rhythm",
    "key_x",
    "key_y",
    "mode",
    "mixability",
)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _feature_vector(profile: dict[str, Any]) -> list[float] | None:
    analysis = profile.get("analysis")
    if not isinstance(analysis, dict):
        return None

    bpm = max(0.0, float(analysis.get("bpm") or 0.0))
    tempo = math.log2(max(60.0, bpm) / 60.0) if bpm > 0 else 0.75
    brightness = math.log(max(120.0, float(analysis.get("spectral_centroid") or 120.0)))
    energy = _clamp(float(analysis.get("energy") or 0.0))
    rhythm = _clamp(float(analysis.get("onset_density") or 0.0) * 4.0)
    mix = (
        _clamp(float(analysis.get("intro_mixability") or 0.0))
        + _clamp(float(analysis.get("outro_mixability") or 0.0))
    ) / 2.0

    pc = int(analysis.get("key_pc", -1))
    key_conf = _clamp(float(analysis.get("key_confidence") or 0.0))
    if 0 <= pc < 12:
        angle = 2.0 * math.pi * pc / 12.0
        key_x = math.cos(angle) * key_conf
        key_y = math.sin(angle) * key_conf
    else:
        key_x = 0.0
        key_y = 0.0
    mode_raw = str(analysis.get("key_mode") or "")
    mode = (1.0 if mode_raw == "major" else -1.0 if mode_raw == "minor" else 0.0) * key_conf

    return [energy, tempo, brightness, rhythm, key_x, key_y, mode, mix]


def _mean_std(rows: list[list[float]]) -> tuple[list[float], list[float]]:
    dims = len(rows[0])
    means = [sum(row[i] for row in rows) / len(rows) for i in range(dims)]
    stds: list[float] = []
    for i in range(dims):
        variance = sum((row[i] - means[i]) ** 2 for row in rows) / max(1, len(rows) - 1)
        stds.append(max(1e-6, math.sqrt(variance)))
    return means, stds


def _standardize(rows: list[list[float]]) -> list[list[float]]:
    means, stds = _mean_std(rows)
    return [
        [(row[i] - means[i]) / stds[i] for i in range(len(row))]
        for row in rows
    ]


def _covariance(rows: list[list[float]]) -> list[list[float]]:
    dims = len(rows[0])
    denom = max(1, len(rows) - 1)
    return [
        [
            sum(row[i] * row[j] for row in rows) / denom
            for j in range(dims)
        ]
        for i in range(dims)
    ]


def _mat_vec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(row[i] * vector[i] for i in range(len(vector))) for row in matrix]


def _normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm <= 1e-12:
        return [0.0 for _ in vector]
    out = [x / norm for x in vector]
    # Eigenvectors are sign-ambiguous. Force the largest loading positive so
    # the same library does not randomly mirror between runs.
    idx = max(range(len(out)), key=lambda i: abs(out[i]))
    if out[idx] < 0:
        out = [-x for x in out]
    return out


def _power_component(
    covariance: list[list[float]],
    seed: list[float],
    orthogonal_to: list[float] | None = None,
) -> list[float]:
    vector = _normalise(seed)
    for _ in range(64):
        nxt = _mat_vec(covariance, vector)
        if orthogonal_to is not None:
            dot = sum(nxt[i] * orthogonal_to[i] for i in range(len(nxt)))
            nxt = [nxt[i] - dot * orthogonal_to[i] for i in range(len(nxt))]
        nxt = _normalise(nxt)
        if not any(abs(x) > 1e-10 for x in nxt):
            break
        delta = sum(abs(nxt[i] - vector[i]) for i in range(len(nxt)))
        vector = nxt
        if delta < 1e-9:
            break
    return vector


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(x) for x in values)
    if len(ordered) == 1:
        return ordered[0]
    pos = _clamp(q) * (len(ordered) - 1)
    lo = int(math.floor(pos))
    hi = min(len(ordered) - 1, lo + 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def _scale_axis(values: list[float]) -> list[float]:
    if not values:
        return []
    lo = _percentile(values, 0.02)
    hi = _percentile(values, 0.98)
    if hi <= lo + 1e-9:
        lo, hi = min(values), max(values)
    if hi <= lo + 1e-9:
        return [0.0 for _ in values]
    return [
        _clamp((value - lo) / (hi - lo), 0.0, 1.0) * 2.0 - 1.0
        for value in values
    ]


def _taste_metrics(profile: dict[str, Any]) -> tuple[float, float]:
    taste = profile.get("taste") if isinstance(profile.get("taste"), dict) else {}
    plays = max(0, int(taste.get("plays") or 0))
    completion = _clamp(float(taste.get("completion_rate") or 0.0))
    skip = _clamp(float(taste.get("skip_rate") or 0.0))
    love = 1.0 if int(taste.get("loves") or 0) > 0 else 0.0
    keep = _clamp(int(taste.get("keeps") or 0) / 3.0)
    positive = _clamp(
        0.34 * love
        + 0.18 * keep
        + 0.24 * completion
        + 0.12 * _clamp(math.log1p(plays) / math.log(20.0))
        - 0.30 * skip
    )

    days = taste.get("days_since_last_played")
    if days is None or plays <= 0:
        rediscovery = 0.0
    else:
        days = max(0.0, float(days))
        spacing = (
            math.exp(-((math.log(days + 1.0) - math.log(76.0)) ** 2) / 1.35)
            if days >= 7.0
            else 0.0
        )
        rediscovery = _clamp(positive * spacing)

    library_signal = profile.get("library_rediscovery")
    if isinstance(library_signal, dict):
        try:
            rediscovery = max(
                rediscovery,
                _clamp(float(library_signal.get("library_score") or 0.0)),
            )
        except (TypeError, ValueError, OverflowError):
            pass
    return positive, rediscovery


def _distance(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 999.0
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(len(a))) / len(a))


def build_music_map(
    profiles: list[dict[str, Any]],
    *,
    max_nodes: int = 700,
    neighbours: int = 2,
) -> dict[str, Any]:
    """Project analysed local-library profiles into a deterministic 2D graph."""

    analysed: list[tuple[dict[str, Any], list[float]]] = []
    for raw in profiles:
        profile = dict(raw or {})
        vector = _feature_vector(profile)
        if vector is None:
            continue
        analysed.append((profile, vector))

    if not analysed:
        return {
            "nodes": [],
            "edges": [],
            "analysed": 0,
            "input_profiles": len(profiles),
            "feature_names": list(FEATURE_NAMES),
        }

    # Large libraries stay responsive by keeping strong/rediscoverable tracks
    # plus a deterministic breadth sample across the analysed collection.
    if len(analysed) > max_nodes:
        scored: list[tuple[float, str, tuple[dict[str, Any], list[float]]]] = []
        for item in analysed:
            profile = item[0]
            taste, rediscovery = _taste_metrics(profile)
            ref = str(profile.get("ref") or "")
            scored.append((2.0 * rediscovery + taste, ref, item))
        scored.sort(key=lambda row: (-row[0], row[1]))
        priority_count = max_nodes // 2
        selected = [row[2] for row in scored[:priority_count]]
        selected_refs = {str(row[0].get("ref") or "") for row in selected}
        remainder = [
            item for _score, _ref, item in sorted(scored[priority_count:], key=lambda row: row[1])
            if str(item[0].get("ref") or "") not in selected_refs
        ]
        needed = max_nodes - len(selected)
        if remainder and needed > 0:
            step = len(remainder) / needed
            for i in range(needed):
                selected.append(remainder[min(len(remainder) - 1, int(i * step))])
        analysed = selected[:max_nodes]

    raw_vectors = [vector for _profile, vector in analysed]
    standardized = _standardize(raw_vectors)

    if len(standardized) >= 3:
        cov = _covariance(standardized)
        dims = len(standardized[0])
        first = _power_component(cov, [1.0 + 0.07 * i for i in range(dims)])
        second = _power_component(
            cov,
            [0.31 + 0.13 * ((i * 3) % 5) for i in range(dims)],
            orthogonal_to=first,
        )
        xs = [sum(row[i] * first[i] for i in range(dims)) for row in standardized]
        ys = [sum(row[i] * second[i] for i in range(dims)) for row in standardized]
    else:
        xs = [row[2] if len(row) > 2 else row[0] for row in standardized]
        ys = [row[0] for row in standardized]

    scaled_x = _scale_axis(xs)
    scaled_y = _scale_axis(ys)

    nodes: list[dict[str, Any]] = []
    for index, ((profile, _raw), z) in enumerate(zip(analysed, standardized)):
        taste, rediscovery = _taste_metrics(profile)
        analysis = profile.get("analysis") if isinstance(profile.get("analysis"), dict) else {}
        library_signal = profile.get("library_rediscovery")
        rediscovery_reason = (
            str(library_signal.get("reason") or "").strip()
            if isinstance(library_signal, dict)
            else ""
        )
        nodes.append(
            {
                "ref": str(profile.get("ref") or f"t{index}"),
                "title": str(profile.get("title") or ""),
                "artist": str(profile.get("artist") or ""),
                "album": str(profile.get("album") or ""),
                "x": scaled_x[index],
                "y": scaled_y[index],
                "energy": _clamp(float(analysis.get("energy") or 0.0)),
                "bpm": float(analysis.get("bpm") or 0.0),
                "key_pc": int(analysis.get("key_pc", -1)),
                "key_mode": str(analysis.get("key_mode") or ""),
                "taste": taste,
                "rediscovery": rediscovery,
                "rediscovery_reason": rediscovery_reason,
                "plays": int((profile.get("taste") or {}).get("plays") or 0)
                if isinstance(profile.get("taste"), dict)
                else 0,
                "route_vector": [float(value) for value in z],
            }
        )

    edge_set: set[tuple[int, int]] = set()
    edges: list[dict[str, Any]] = []
    k = max(0, min(4, int(neighbours)))
    if k <= 0:
        return {
            "nodes": nodes,
            "edges": [],
            "analysed": len(nodes),
            "input_profiles": len(profiles),
            "feature_names": list(FEATURE_NAMES),
        }
    for i, node in enumerate(nodes):
        candidates: list[tuple[float, int]] = []
        for j, other in enumerate(nodes):
            if i == j:
                continue
            candidates.append((_distance(node["route_vector"], other["route_vector"]), j))
        candidates.sort(key=lambda row: (row[0], nodes[row[1]]["ref"]))
        for distance, j in candidates[:k]:
            pair = (min(i, j), max(i, j))
            if pair in edge_set:
                continue
            similarity = math.exp(-0.58 * distance)
            # Avoid drawing meaningless long outlier links. A node with no close
            # neighbour may therefore appear as an island, which is informative.
            if similarity < 0.34:
                continue
            edge_set.add(pair)
            edges.append(
                {
                    "a": nodes[pair[0]]["ref"],
                    "b": nodes[pair[1]]["ref"],
                    "similarity": _clamp(similarity),
                }
            )

    return {
        "nodes": nodes,
        "edges": edges,
        "analysed": len(nodes),
        "input_profiles": len(profiles),
        "feature_names": list(FEATURE_NAMES),
    }


__all__ = ["FEATURE_NAMES", "build_music_map"]
