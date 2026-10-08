from __future__ import annotations

import math
from typing import Any

from .music_pathfinder import MusicPathNetwork


STAGE_LABELS = {
    "calm": "Calm",
    "dark": "Darker",
    "forgotten": "Forgotten",
    "energetic": "Energetic",
    "bright": "Bright",
    "rhythmic": "Rhythmic",
    "familiar": "Familiar",
    "surprising": "Surprising",
}


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _sigmoid(value: float) -> float:
    x = max(-8.0, min(8.0, float(value)))
    return 1.0 / (1.0 + math.exp(-x))


def _vector(node: dict[str, Any]) -> list[float]:
    return [float(x) for x in list(node.get("route_vector") or [])]


def _distance(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 999.0
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(len(a))) / len(a))


def _progress_score(
    node: dict[str, Any],
    start: dict[str, Any],
    end: dict[str, Any],
    fraction: float,
) -> float:
    nv, sv, ev = _vector(node), _vector(start), _vector(end)
    if not nv or len(nv) != len(sv) or len(sv) != len(ev):
        return 0.5
    f = _clamp(fraction)
    target = [sv[i] * (1.0 - f) + ev[i] * f for i in range(len(sv))]
    return _clamp(math.exp(-0.58 * _distance(nv, target)))


def _track_similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    av, bv = _vector(a), _vector(b)
    if not av or len(av) != len(bv):
        return 0.0
    return _clamp(math.exp(-0.58 * _distance(av, bv)))


def _map_region_score(a: dict[str, Any], b: dict[str, Any]) -> float:
    distance = math.hypot(
        float(a.get("x") or 0.0) - float(b.get("x") or 0.0),
        float(a.get("y") or 0.0) - float(b.get("y") or 0.0),
    )
    return _clamp(math.exp(-2.0 * distance))


def stage_score(node: dict[str, Any], constraint: str) -> tuple[float, str]:
    """Return transparent 0..1 satisfaction score for a journey stage."""

    constraint = str(constraint or "").strip().lower()
    vector = _vector(node)
    energy = _clamp(float(node.get("energy") or 0.0))
    taste = _clamp(float(node.get("taste") or 0.0))
    rediscovery = _clamp(float(node.get("rediscovery") or 0.0))
    plays = max(0, int(node.get("plays") or 0))
    mode = str(node.get("key_mode") or "")

    tempo_high = _sigmoid(vector[1]) if len(vector) > 1 else 0.5
    brightness_high = _sigmoid(vector[2]) if len(vector) > 2 else 0.5
    rhythm_high = _sigmoid(vector[3]) if len(vector) > 3 else 0.5
    mixability = _sigmoid(vector[7]) if len(vector) > 7 else 0.5
    minor = 1.0 if mode == "minor" else 0.15 if mode == "major" else 0.5
    major = 1.0 if mode == "major" else 0.15 if mode == "minor" else 0.5

    if constraint == "calm":
        score = (
            0.46 * (1.0 - energy)
            + 0.28 * (1.0 - tempo_high)
            + 0.20 * (1.0 - rhythm_high)
            + 0.06 * mixability
        )
        return _clamp(score), (
            f"low energy {1.0-energy:.0%} · gentle tempo {1.0-tempo_high:.0%} · "
            f"low rhythmic density {1.0-rhythm_high:.0%}"
        )

    if constraint == "dark":
        darker_timbre = 1.0 - brightness_high
        mid_low_energy = _clamp(1.0 - abs(energy - 0.36) / 0.64)
        score = 0.50 * darker_timbre + 0.30 * minor + 0.20 * mid_low_energy
        return _clamp(score), (
            f"darker timbre {darker_timbre:.0%} · "
            f"{'minor' if mode == 'minor' else 'tonal'} character · "
            f"energy fit {mid_low_energy:.0%}"
        )

    if constraint == "forgotten":
        score = 0.82 * rediscovery + 0.18 * taste
        reason = f"rediscovery {rediscovery:.0%} · taste {taste:.0%}"
        library_reason = str(node.get("rediscovery_reason") or "").strip()
        if library_reason:
            reason += f" · {library_reason}"
        return _clamp(score), reason

    if constraint == "energetic":
        score = 0.52 * energy + 0.25 * tempo_high + 0.23 * rhythm_high
        return _clamp(score), (
            f"energy {energy:.0%} · tempo drive {tempo_high:.0%} · "
            f"rhythmic density {rhythm_high:.0%}"
        )

    if constraint == "bright":
        score = 0.56 * brightness_high + 0.24 * major + 0.20 * energy
        return _clamp(score), (
            f"bright timbre {brightness_high:.0%} · "
            f"{'major' if mode == 'major' else 'tonal'} character · energy {energy:.0%}"
        )

    if constraint == "rhythmic":
        score = 0.56 * rhythm_high + 0.24 * tempo_high + 0.20 * mixability
        return _clamp(score), (
            f"rhythmic density {rhythm_high:.0%} · tempo drive {tempo_high:.0%} · "
            f"mixability {mixability:.0%}"
        )

    if constraint == "familiar":
        play_strength = _clamp(math.log1p(plays) / math.log(16.0))
        score = 0.72 * taste + 0.28 * play_strength
        return _clamp(score), (
            f"taste {taste:.0%} · familiarity {play_strength:.0%}"
        )

    if constraint == "surprising":
        unheard = 1.0 if plays == 0 else _clamp(1.0 - math.log1p(plays) / math.log(12.0))
        score = 0.62 * unheard + 0.38 * (1.0 - taste)
        return _clamp(score), (
            f"novelty {unheard:.0%} · low familiarity {1.0-taste:.0%}"
        )

    return 0.0, "unknown stage constraint"


def _normalise_stage(stage: Any) -> dict[str, Any]:
    if isinstance(stage, str):
        key = stage.strip().lower()
        return {
            "type": "constraint",
            "constraint": key,
            "label": STAGE_LABELS.get(key, key.title()),
        }
    if not isinstance(stage, dict):
        return {}
    kind = str(stage.get("type") or "constraint")
    if kind == "track":
        return {
            "type": "track",
            "ref": str(stage.get("ref") or ""),
            "label": str(stage.get("label") or "Track waypoint"),
        }
    if kind == "similar":
        return {
            "type": "similar",
            "target_ref": str(stage.get("target_ref") or ""),
            "label": str(stage.get("label") or "More like this"),
        }
    if kind == "artist":
        return {
            "type": "artist",
            "artist": str(stage.get("artist") or "").strip(),
            "label": str(stage.get("label") or "Toward this artist"),
        }
    if kind == "region":
        return {
            "type": "region",
            "target_ref": str(stage.get("target_ref") or ""),
            "label": str(stage.get("label") or "Toward this map area"),
        }
    key = str(stage.get("constraint") or "").strip().lower()
    return {
        "type": "constraint",
        "constraint": key,
        "label": str(stage.get("label") or STAGE_LABELS.get(key, key.title())),
    }


def build_music_journey(
    model: dict[str, Any],
    knowledge_graph: dict[str, Any],
    start_ref: str,
    end_ref: str,
    stages: list[Any],
    *,
    mode: str = "balanced",
    max_hops_per_segment: int = 8,
    candidates_per_stage: int = 10,
    forbidden_refs: set[str] | None = None,
) -> dict[str, Any]:
    """Build an explainable staged journey using reusable Pathfinder segments."""

    network = MusicPathNetwork(model, knowledge_graph)
    nodes = network.nodes
    start_ref, end_ref = str(start_ref), str(end_ref)
    normalised = [stage for stage in (_normalise_stage(x) for x in stages) if stage]
    forbidden = {str(ref) for ref in set(forbidden_refs or set()) if str(ref)}
    forbidden.discard(start_ref)
    forbidden.discard(end_ref)

    if start_ref not in nodes or end_ref not in nodes:
        return {
            "found": False,
            "mode": mode,
            "path_refs": [],
            "hops": [],
            "stages": [],
            "reason": "Journey start and destination must both be visible mapped tracks.",
        }
    if not normalised:
        direct = network.find(
            start_ref,
            end_ref,
            mode=mode,
            max_hops=max_hops_per_segment,
            forbidden_refs=forbidden,
        )
        direct["stages"] = []
        direct["waypoint_refs"] = []
        direct["journey"] = True
        return direct

    combined_refs = [start_ref]
    combined_hops: list[dict[str, Any]] = []
    chosen_stages: list[dict[str, Any]] = []
    waypoint_refs: list[str] = []
    used_refs = {start_ref}
    current_ref = start_ref
    route_scores: list[float] = []
    stage_scores: list[float] = []

    start_node = nodes[start_ref]
    end_node = nodes[end_ref]
    count = len(normalised)

    for index, stage in enumerate(normalised):
        fraction = (index + 1) / (count + 1)
        if stage["type"] == "track":
            candidates = [
                (
                    1.0,
                    str(stage.get("ref") or ""),
                    1.0,
                    "explicit track waypoint",
                )
            ]
        elif stage["type"] == "similar":
            target_ref = str(stage.get("target_ref") or "")
            target_node = nodes.get(target_ref)
            ranked = []
            if target_node is not None:
                for ref, node in nodes.items():
                    if ref in used_refs or ref in {end_ref, target_ref} or ref in forbidden:
                        continue
                    similarity = _track_similarity(node, target_node)
                    progress = _progress_score(node, start_node, end_node, fraction)
                    priority = 0.82 * similarity + 0.18 * progress
                    target_name = (
                        f"{target_node.get('artist') or 'Unknown artist'} — "
                        f"{target_node.get('title') or 'Unknown track'}"
                    )
                    explanation = (
                        f"similarity {similarity:.0%} to {target_name}"
                    )
                    ranked.append((priority, ref, similarity, explanation))
            ranked.sort(key=lambda row: (-row[0], row[1]))
            candidates = ranked[: max(1, min(24, int(candidates_per_stage)))]
        elif stage["type"] == "artist":
            target_artist = " ".join(
                str(stage.get("artist") or "").strip().casefold().split()
            )
            ranked = []
            for ref, node in nodes.items():
                artist = " ".join(
                    str(node.get("artist") or "").strip().casefold().split()
                )
                if (
                    not target_artist
                    or artist != target_artist
                    or ref in used_refs
                    or ref in {end_ref}
                    or ref in forbidden
                ):
                    continue
                progress = _progress_score(node, start_node, end_node, fraction)
                explanation = f"artist match: {node.get('artist') or target_artist}"
                ranked.append((0.76 + 0.24 * progress, ref, 1.0, explanation))
            ranked.sort(key=lambda row: (-row[0], row[1]))
            candidates = ranked[: max(1, min(24, int(candidates_per_stage)))]
        elif stage["type"] == "region":
            target_ref = str(stage.get("target_ref") or "")
            target_node = nodes.get(target_ref)
            ranked = []
            if target_node is not None:
                for ref, node in nodes.items():
                    if ref in used_refs or ref in {end_ref, target_ref} or ref in forbidden:
                        continue
                    proximity = _map_region_score(node, target_node)
                    progress = _progress_score(node, start_node, end_node, fraction)
                    priority = 0.82 * proximity + 0.18 * progress
                    target_name = (
                        f"{target_node.get('artist') or 'Unknown artist'} — "
                        f"{target_node.get('title') or 'Unknown track'}"
                    )
                    explanation = f"map proximity {proximity:.0%} to {target_name}"
                    ranked.append((priority, ref, proximity, explanation))
            ranked.sort(key=lambda row: (-row[0], row[1]))
            candidates = ranked[: max(1, min(24, int(candidates_per_stage)))]
        else:
            constraint = str(stage.get("constraint") or "")
            ranked: list[tuple[float, str, float, str]] = []
            for ref, node in nodes.items():
                if ref in used_refs or ref == end_ref or ref in forbidden:
                    continue
                satisfaction, explanation = stage_score(node, constraint)
                progress = _progress_score(node, start_node, end_node, fraction)
                priority = 0.76 * satisfaction + 0.24 * progress
                ranked.append((priority, ref, satisfaction, explanation))
            ranked.sort(key=lambda row: (-row[0], row[1]))
            candidates = ranked[: max(1, min(24, int(candidates_per_stage)))]

        selected: tuple[str, dict[str, Any], float, str] | None = None
        for _priority, candidate_ref, satisfaction, explanation in candidates:
            if not candidate_ref or candidate_ref not in nodes:
                continue
            if candidate_ref in used_refs and candidate_ref != current_ref:
                continue
            if stage["type"] == "constraint" and satisfaction < 0.30:
                continue
            if stage["type"] == "similar" and satisfaction < 0.30:
                continue
            if stage["type"] == "region" and satisfaction < 0.15:
                continue
            segment = network.find(
                current_ref,
                candidate_ref,
                mode=mode,
                max_hops=max_hops_per_segment,
                forbidden_refs=forbidden,
            )
            if not segment.get("found"):
                continue

            refs = [str(x) for x in list(segment.get("path_refs") or []) if str(x)]
            # Avoid reaching the final destination before all requested stages
            # are satisfied and avoid loops through earlier journey regions.
            if end_ref in refs[1:] and candidate_ref != end_ref:
                continue
            if any(ref in used_refs for ref in refs[1:-1]):
                continue

            future = network.find(
                candidate_ref,
                end_ref,
                mode=mode,
                max_hops=max_hops_per_segment,
                forbidden_refs=forbidden,
            )
            if not future.get("found"):
                continue

            selected = (candidate_ref, dict(segment), satisfaction, explanation)
            break

        if selected is None:
            label = str(stage.get("label") or "requested stage")
            return {
                "found": False,
                "mode": mode,
                "path_refs": combined_refs,
                "hops": combined_hops,
                "stages": chosen_stages,
                "waypoint_refs": waypoint_refs,
                "failed_stage": dict(stage),
                "reason": f"Could not find a routable {label} waypoint in the current map.",
            }

        candidate_ref, segment, satisfaction, explanation = selected
        refs = [str(x) for x in list(segment.get("path_refs") or []) if str(x)]
        hops = [
            dict(x)
            for x in list(segment.get("hops") or [])
            if isinstance(x, dict)
        ]
        if refs:
            combined_refs.extend(refs[1:])
            used_refs.update(refs[1:])
        if hops:
            hops[-1]["journey_stage"] = str(stage.get("label") or "")
            hops[-1]["journey_stage_score"] = float(satisfaction)
            hops[-1]["journey_stage_reason"] = explanation
            combined_hops.extend(hops)

        waypoint_refs.append(candidate_ref)
        chosen_stages.append(
            {
                **dict(stage),
                "ref": candidate_ref,
                "score": float(satisfaction),
                "reason": explanation,
            }
        )
        stage_scores.append(float(satisfaction))
        route_scores.append(float(segment.get("score") or 0.0))
        current_ref = candidate_ref

    final_segment = network.find(
        current_ref,
        end_ref,
        mode=mode,
        max_hops=max_hops_per_segment,
        forbidden_refs=forbidden,
    )
    if not final_segment.get("found"):
        return {
            "found": False,
            "mode": mode,
            "path_refs": combined_refs,
            "hops": combined_hops,
            "stages": chosen_stages,
            "waypoint_refs": waypoint_refs,
            "reason": "All requested stages were found, but the destination is not routable from the final waypoint.",
        }

    final_refs = [
        str(x) for x in list(final_segment.get("path_refs") or []) if str(x)
    ]
    if any(ref in used_refs for ref in final_refs[1:-1]):
        # This is still a valid route, but make the reuse explicit rather than
        # silently pretending every stage occupies a unique region.
        reused = True
    else:
        reused = False
    combined_refs.extend(final_refs[1:])
    combined_hops.extend(
        dict(x)
        for x in list(final_segment.get("hops") or [])
        if isinstance(x, dict)
    )
    route_scores.append(float(final_segment.get("score") or 0.0))

    route_mean = sum(route_scores) / max(1, len(route_scores))
    stage_mean = sum(stage_scores) / max(1, len(stage_scores)) if stage_scores else 1.0
    score = _clamp(0.58 * route_mean + 0.42 * stage_mean)

    return {
        "found": True,
        "journey": True,
        "mode": mode,
        "path_refs": combined_refs,
        "hops": combined_hops,
        "stages": chosen_stages,
        "waypoint_refs": waypoint_refs,
        "score": score,
        "reused_region": reused,
        "reason": (
            f"{len(chosen_stages)} stage{'s' if len(chosen_stages) != 1 else ''} · "
            f"{len(combined_hops)} hop{'s' if len(combined_hops) != 1 else ''} · "
            f"stage fit {stage_mean:.0%}"
            + (" · one region revisited" if reused else "")
        ),
    }


__all__ = ["STAGE_LABELS", "stage_score", "build_music_journey"]
