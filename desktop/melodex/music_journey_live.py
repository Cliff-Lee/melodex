from __future__ import annotations

from typing import Any

from .living_queue import queue_track_key
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
    if kind == "similar":
        return {
            "type": "similar",
            "target_ref": str(stage.get("target_ref") or ""),
            "label": str(stage.get("label") or "More like this"),
        }
    if kind == "artist":
        return {
            "type": "artist",
            "artist": str(stage.get("artist") or ""),
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


def route_track_reasons(
    result: dict[str, Any], ref_map: dict[str, dict[str, Any]]
) -> dict[tuple[str, ...], str]:
    """Map each adapted route track to its concise stage or hop explanation."""
    result = dict(result or {})
    stages_by_ref = {
        str(stage.get("ref") or ""): dict(stage)
        for stage in list(result.get("stages") or [])
        if isinstance(stage, dict) and str(stage.get("ref") or "")
    }
    hops_by_ref = {
        str(hop.get("to") or ""): dict(hop)
        for hop in list(result.get("hops") or [])
        if isinstance(hop, dict) and str(hop.get("to") or "")
    }
    reasons = {}
    for ref in list(result.get("path_refs") or [])[1:]:
        track = ref_map.get(str(ref))
        if not isinstance(track, dict):
            continue
        stage = stages_by_ref.get(str(ref), {})
        hop = hops_by_ref.get(str(ref), {})
        if stage:
            label = str(stage.get("label") or "Journey direction").strip()
            detail = str(stage.get("reason") or "").strip()
            reason = label + (f" · {detail}" if detail else "")
        else:
            reason = str(hop.get("reason") or "").strip()
        if reason:
            reasons[queue_track_key(track)] = reason
    return reasons


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
    reopen_stage_refs: set[str] | None = None,
    similar_to_ref: str = "",
    target_artist: str = "",
    target_region_ref: str = "",
    max_hops_per_segment: int = 8,
) -> dict[str, Any]:
    """Replan only the unfinished tail of an active designed journey."""

    current_ref = str(current_ref or "")
    destination_ref = str(destination_ref or "")
    remaining = remaining_journey_stages(active_route, current_ref)
    reopen = {str(ref) for ref in set(reopen_stage_refs or set()) if str(ref)}
    if reopen:
        reopened: list[dict[str, Any]] = []
        existing = {
            (
                str(stage.get("type") or "constraint"),
                str(stage.get("constraint") or ""),
                str(stage.get("ref") or ""),
            )
            for stage in remaining
        }
        for raw in list(active_route.get("stages") or []):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("ref") or "") not in reopen:
                continue
            spec = _stage_spec(dict(raw))
            key = (
                str(spec.get("type") or "constraint"),
                str(spec.get("constraint") or ""),
                str(spec.get("ref") or ""),
            )
            if key not in existing:
                reopened.append(spec)
                existing.add(key)
        remaining = reopened + remaining

    steering_stage = live_steering_stage(steering)
    requested_stages = list(remaining)
    target_artist = " ".join(str(target_artist or "").strip().split())
    target_region_ref = str(target_region_ref or "")
    if target_artist:
        requested_stages.insert(
            0,
            {
                "type": "artist",
                "artist": target_artist,
                "label": f"Toward {target_artist}",
            },
        )
    similar_to_ref = str(similar_to_ref or "")
    if similar_to_ref:
        target = next(
            (
                dict(node)
                for node in list(model.get("nodes") or [])
                if isinstance(node, dict)
                and str(node.get("ref") or "") == similar_to_ref
            ),
            {},
        )
        target_label = (
            f"{target.get('artist') or 'Unknown artist'} — "
            f"{target.get('title') or 'Unknown track'}"
        )
        requested_stages.insert(
            0,
            {
                "type": "similar",
                "target_ref": similar_to_ref,
                "label": f"More like {target_label}",
            },
        )
    if target_region_ref:
        target = next(
            (
                dict(node)
                for node in list(model.get("nodes") or [])
                if isinstance(node, dict)
                and str(node.get("ref") or "") == target_region_ref
            ),
            {},
        )
        target_label = (
            f"{target.get('artist') or 'Unknown artist'} — "
            f"{target.get('title') or 'Unknown track'}"
        )
        requested_stages.insert(
            0,
            {
                "type": "region",
                "target_ref": target_region_ref,
                "label": f"Toward this map area · {target_label}",
            },
        )
    if steering_stage is not None:
        requested_stages.insert(
            1 if similar_to_ref or target_artist or target_region_ref else 0,
            steering_stage,
        )

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
    result["similar_to_ref"] = similar_to_ref
    result["target_artist"] = target_artist
    result["target_region_ref"] = target_region_ref
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
        if target_artist:
            direction_label = f"Toward {target_artist}"
        elif target_region_ref:
            target = next(
                (
                    dict(node)
                    for node in list(model.get("nodes") or [])
                    if isinstance(node, dict)
                    and str(node.get("ref") or "") == target_region_ref
                ),
                {},
            )
            direction_label = (
                "Toward this map area · "
                f"{target.get('artist') or 'Unknown artist'} — "
                f"{target.get('title') or 'Unknown track'}"
            )
        elif similar_to_ref:
            target = next(
                (
                    dict(node)
                    for node in list(model.get("nodes") or [])
                    if isinstance(node, dict)
                    and str(node.get("ref") or "") == similar_to_ref
                ),
                {},
            )
            direction_label = (
                "More like "
                f"{target.get('artist') or 'Unknown artist'} — "
                f"{target.get('title') or 'Unknown track'}"
            )
        elif steering_stage is not None:
            direction_label = str(steering_stage["label"])
        else:
            direction_label = ""

        if direction_label:
            result["reason"] = (
                f"Live steer: {direction_label} · "
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
    "route_track_reasons",
]
