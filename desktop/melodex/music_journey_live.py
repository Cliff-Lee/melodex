from __future__ import annotations

from typing import Any

from .music_journey import STAGE_LABELS, build_music_journey


STEERING_STAGES = {
    "calmer": ("calm", "Calmer next"),
    "more_energy": ("energetic", "More energy next"),
    "darker": ("dark", "Darker next"),
    "brighter": ("bright", "Brighter next"),
    "more_rhythmic": ("rhythmic", "More rhythmic next"),
    "more_familiar": ("familiar", "More familiar next"),
    "more_surprising": ("surprising", "More surprising next"),
    "rediscover": ("forgotten", "Rediscover next"),
}


def _stage_spec(stage: dict[str, Any]) -> dict[str, Any]:
    kind = str(stage.get("type") or "constraint")
    if kind == "track":
        return {
            "type": "track",
            "ref": str(stage.get("ref") or ""),
            "label": str(stage.get("label") or "Track waypoint"),
        }
    key = str(stage.get("constraint") or "").strip().lower()
    return {
        "type": "constraint",
        "constraint": key,
        "label": str(stage.get("label") or STAGE_LABELS.get(key, key.title())),
    }


def remaining_journey_stages(
    route_result: dict[str, Any],
    current_ref: str,
) -> list[dict[str, Any]]:
    """Return only stages whose chosen waypoint has not yet been reached."""

    route = dict(route_result or {})
    refs = [str(x) for x in list(route.get("path_refs") or []) if str(x)]
    current_ref = str(current_ref or "")
    if current_ref in refs:
        current_index = refs.index(current_ref)
    else:
        current_index = -1

    remaining: list[dict[str, Any]] = []
    for raw in list(route.get("stages") or []):
        if not isinstance(raw, dict):
            continue
        stage = dict(raw)
        chosen_ref = str(stage.get("ref") or "")
        if chosen_ref and chosen_ref in refs and refs.index(chosen_ref) <= current_index:
            continue
        remaining.append(_stage_spec(stage))
    return remaining


def _forbidden_for_artists(
    model: dict[str, Any],
    avoid_artists: set[str],
) -> set[str]:
    artists = {
        " ".join(str(value or "").strip().casefold().split())
        for value in set(avoid_artists or set())
        if str(value or "").strip()
    }
    if not artists:
        return set()
    refs: set[str] = set()
    for node in list(model.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        artist = " ".join(str(node.get("artist") or "").strip().casefold().split())
        ref = str(node.get("ref") or "")
        if ref and artist and artist in artists:
            refs.add(ref)
    return refs


def live_steering_stage(steering: str) -> dict[str, Any] | None:
    item = STEERING_STAGES.get(str(steering or "").strip().lower())
    if item is None:
        return None
    constraint, label = item
    return {
        "type": "constraint",
        "constraint": constraint,
        "label": label,
        "_live_steering": True,
    }


def replan_live_journey(
    model: dict[str, Any],
    knowledge_graph: dict[str, Any],
    active_route: dict[str, Any],
    current_ref: str,
    destination_ref: str,
    *,
    mode: str = "balanced",
    steering: str = "",
    avoid_refs: set[str] | None = None,
    avoid_artists: set[str] | None = None,
    max_hops_per_segment: int = 8,
) -> dict[str, Any]:
    """Replan only the unfinished tail of an active designed journey."""

    current_ref = str(current_ref or "")
    destination_ref = str(destination_ref or "")
    remaining = remaining_journey_stages(active_route, current_ref)

    steering_stage = live_steering_stage(steering)
    requested_stages = list(remaining)
    if steering_stage is not None:
        requested_stages.insert(0, steering_stage)

    forbidden = {
        str(ref)
        for ref in set(avoid_refs or set())
        if str(ref)
    }
    forbidden.update(_forbidden_for_artists(model, set(avoid_artists or set())))
    forbidden.discard(current_ref)
    forbidden.discard(destination_ref)

    result = build_music_journey(
        model,
        knowledge_graph,
        current_ref,
        destination_ref,
        requested_stages,
        mode=mode,
        max_hops_per_segment=max_hops_per_segment,
        candidates_per_stage=10,
        forbidden_refs=forbidden,
    )
    result = dict(result or {})
    result["live"] = True
    result["steering"] = str(steering or "")
    result["remaining_original_stages"] = remaining
    result["avoided_artists"] = sorted(
        {
            " ".join(str(value or "").strip().split())
            for value in set(avoid_artists or set())
            if str(value or "").strip()
        },
        key=str.casefold,
    )
    result["forbidden_refs"] = sorted(forbidden)
    if result.get("found"):
        if steering_stage is not None:
            result["reason"] = (
                f"Live steer: {steering_stage['label']} · "
                + str(result.get("reason") or "route replanned")
            )
        else:
            result["reason"] = "Live replan · " + str(
                result.get("reason") or "route replanned"
            )
    return result


__all__ = [
    "STEERING_STAGES",
    "live_steering_stage",
    "remaining_journey_stages",
    "replan_live_journey",
]
