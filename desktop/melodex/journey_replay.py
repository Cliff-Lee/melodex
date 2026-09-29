from __future__ import annotations

from collections import Counter
from typing import Any

from .journey_recipe import portable_track_selector, resolve_track_selector


def portable_route_snapshot(
    route: dict[str, Any],
    ref_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Persist a route without depending on request-local map refs."""
    route = dict(route or {})
    refs = [str(x) for x in list(route.get("path_refs") or []) if str(x)]
    tracks: list[dict[str, Any]] = []
    ref_to_index: dict[str, int] = {}
    for ref in refs:
        track = ref_map.get(ref)
        if not isinstance(track, dict):
            continue
        selector = portable_track_selector(track)
        if not selector:
            continue
        ref_to_index[ref] = len(tracks)
        tracks.append(
            {
                "selector": selector,
                "display": (
                    f"{str(track.get('artist') or 'Unknown artist')} — "
                    f"{str(track.get('title') or 'Unknown track')}"
                ),
            }
        )

    hops: list[dict[str, Any]] = []
    for raw in list(route.get("hops") or []):
        if not isinstance(raw, dict):
            continue
        a = str(raw.get("from") or "")
        b = str(raw.get("to") or "")
        if a not in ref_to_index or b not in ref_to_index:
            continue
        hops.append(
            {
                "from_index": ref_to_index[a],
                "to_index": ref_to_index[b],
                "reason": str(raw.get("reason") or ""),
                "journey_stage": str(raw.get("journey_stage") or ""),
                "journey_stage_score": float(raw.get("journey_stage_score") or 0.0),
                "journey_stage_reason": str(raw.get("journey_stage_reason") or ""),
                "knowledge_kinds": [
                    str(x)
                    for x in list(raw.get("knowledge_kinds") or [])
                    if str(x)
                ],
                "sonic_similarity": float(raw.get("sonic_similarity") or 0.0),
            }
        )

    stages: list[dict[str, Any]] = []
    for raw in list(route.get("stages") or []):
        if not isinstance(raw, dict):
            continue
        stage = {
            "type": str(raw.get("type") or "constraint"),
            "label": str(raw.get("label") or ""),
            "constraint": str(raw.get("constraint") or ""),
            "score": float(raw.get("score") or 0.0),
            "reason": str(raw.get("reason") or ""),
        }
        ref = str(raw.get("ref") or "")
        if ref in ref_to_index:
            stage["track_index"] = ref_to_index[ref]
        stages.append(stage)

    return {
        "snapshot_version": 1,
        "mode": str(route.get("mode") or "balanced"),
        "journey": bool(route.get("journey")),
        "live": bool(route.get("live")),
        "score": float(route.get("score") or 0.0),
        "reason": str(route.get("reason") or ""),
        "tracks": tracks,
        "hops": hops,
        "stages": stages,
    }


def materialize_route_snapshot(
    snapshot: dict[str, Any],
    ref_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Resolve a historical portable route onto the current Music Map."""
    snapshot = dict(snapshot or {})
    refs: list[str] = []
    unresolved: list[dict[str, Any]] = []
    for index, raw in enumerate(list(snapshot.get("tracks") or [])):
        row = dict(raw) if isinstance(raw, dict) else {}
        selector = (
            dict(row.get("selector") or {})
            if isinstance(row.get("selector"), dict)
            else {}
        )
        ref = resolve_track_selector(selector, ref_map)
        if not ref:
            unresolved.append(
                {
                    "index": index,
                    "display": str(row.get("display") or selector.get("title") or "Unknown track"),
                    "selector": selector,
                }
            )
            refs.append("")
        else:
            refs.append(ref)
    complete = not unresolved and bool(refs)
    hops: list[dict[str, Any]] = []
    if complete:
        for raw in list(snapshot.get("hops") or []):
            if not isinstance(raw, dict):
                continue
            try:
                a = refs[int(raw.get("from_index"))]
                b = refs[int(raw.get("to_index"))]
            except Exception:
                continue
            row = dict(raw)
            row.pop("from_index", None)
            row.pop("to_index", None)
            row["from"] = a
            row["to"] = b
            hops.append(row)

    stages: list[dict[str, Any]] = []
    waypoint_refs: list[str] = []
    if complete:
        for raw in list(snapshot.get("stages") or []):
            if not isinstance(raw, dict):
                continue
            stage = dict(raw)
            index = stage.pop("track_index", None)
            if index is not None:
                try:
                    ref = refs[int(index)]
                except Exception:
                    ref = ""
                if ref:
                    stage["ref"] = ref
                    waypoint_refs.append(ref)
            stages.append(stage)

    route = {
        "found": complete,
        "journey": bool(snapshot.get("journey")),
        "mode": str(snapshot.get("mode") or "balanced"),
        "score": float(snapshot.get("score") or 0.0),
        "reason": str(snapshot.get("reason") or "Historical journey replay"),
        "path_refs": refs if complete else [],
        "hops": hops,
        "stages": stages,
        "waypoint_refs": waypoint_refs,
        "replay": True,
    }
    return {
        "refs": refs,
        "unresolved": unresolved,
        "complete": complete,
        "route": route,
    }


def summarize_journey_run(
    run: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    original = dict(run.get("original_route") or {})
    final = dict(run.get("final_route") or {})
    original_tracks = [
        str(row.get("display") or "")
        for row in list(original.get("tracks") or [])
        if isinstance(row, dict)
    ]
    final_tracks = [
        str(row.get("display") or "")
        for row in list(final.get("tracks") or [])
        if isinstance(row, dict)
    ]

    common_prefix = 0
    for a, b in zip(original_tracks, final_tracks):
        if a != b:
            break
        common_prefix += 1

    event_counts = Counter(
        str(event.get("event_type") or "")
        for event in events
        if isinstance(event, dict)
    )
    decisions: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        kind = str(event.get("event_type") or "")
        payload = (
            dict(event.get("payload") or {})
            if isinstance(event.get("payload"), dict)
            else {}
        )
        if kind == "steer":
            decisions.append(f"Steer · {payload.get('label') or payload.get('steering') or 'change'}")
        elif kind == "manual_skip":
            decisions.append(f"Skip · {payload.get('track') or 'track'}")
        elif kind == "avoid_artist":
            decisions.append(f"Avoid artist · {payload.get('artist') or 'unknown'}")
        elif kind == "restore":
            decisions.append("Restore designed route")
        elif kind == "replan_failed":
            decisions.append(f"Replan failed · {payload.get('reason') or ''}".rstrip(" ·"))
        elif kind == "replan":
            decisions.append(f"Replan · {payload.get('reason') or 'remaining route'}")

    changed = original_tracks != final_tracks and bool(final_tracks)
    return {
        "run_id": str(run.get("id") or ""),
        "status": str(run.get("status") or ""),
        "started_at": float(run.get("started_at") or 0.0),
        "ended_at": float(run.get("ended_at") or 0.0),
        "original_tracks": original_tracks,
        "final_tracks": final_tracks,
        "original_track_count": len(original_tracks),
        "final_track_count": len(final_tracks),
        "common_prefix": common_prefix,
        "changed": changed,
        "event_counts": dict(event_counts),
        "decisions": decisions,
    }


__all__ = [
    "portable_route_snapshot",
    "materialize_route_snapshot",
    "summarize_journey_run",
]
