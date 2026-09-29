from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ALLOWED_MODES = {"balanced", "sonic", "knowledge"}
ALLOWED_CONSTRAINTS = {
    "calm",
    "dark",
    "forgotten",
    "energetic",
    "bright",
    "rhythmic",
    "familiar",
    "surprising",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _norm(value: Any) -> str:
    return _text(value).casefold()


def portable_track_selector(track: dict[str, Any]) -> dict[str, Any]:
    """Return a share-safe identity selector for a track waypoint."""
    track = dict(track or {})
    out: dict[str, Any] = {}
    recording_mbid = _text(
        track.get("musicbrainz_recording_id")
        or track.get("recording_mbid")
    )
    if recording_mbid:
        out["musicbrainz_recording_id"] = recording_mbid
    for key in ("artist", "title", "album"):
        value = _text(track.get(key))
        if value:
            out[key] = value
    return out


def _normalise_stage(
    stage: dict[str, Any],
    ref_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    stage = dict(stage or {})
    kind = str(stage.get("type") or "constraint").strip().lower()
    if kind == "track":
        selector = (
            dict(stage.get("selector") or {})
            if isinstance(stage.get("selector"), dict)
            else {}
        )
        if not selector and ref_map is not None:
            ref = str(stage.get("ref") or "")
            track = ref_map.get(ref)
            if isinstance(track, dict):
                selector = portable_track_selector(track)
        if not selector:
            raise ValueError("Track waypoint needs a portable selector")
        safe = portable_track_selector(selector)
        if not safe.get("title") and not safe.get("musicbrainz_recording_id"):
            raise ValueError("Track waypoint selector needs a title or MusicBrainz recording ID")
        return {
            "type": "track",
            "label": _text(stage.get("label") or safe.get("title") or "Track waypoint"),
            "selector": safe,
        }

    constraint = _text(stage.get("constraint")).lower()
    if constraint not in ALLOWED_CONSTRAINTS:
        raise ValueError(f"Unsupported journey constraint: {constraint or '(empty)'}")
    return {
        "type": "constraint",
        "constraint": constraint,
        "label": _text(stage.get("label") or constraint.title()),
    }


def make_journey_recipe(
    *,
    name: str,
    description: str = "",
    mode: str = "balanced",
    stages: list[dict[str, Any]],
    ref_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    mode = str(mode or "balanced").strip().lower()
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Unsupported journey routing mode: {mode}")
    rows = [
        _normalise_stage(dict(stage), ref_map)
        for stage in list(stages or [])
        if isinstance(stage, dict)
    ]
    if not rows:
        raise ValueError("Journey recipe needs at least one stage")
    return {
        "melodex_journey": SCHEMA_VERSION,
        "name": _text(name) or "Journey recipe",
        "description": _text(description),
        "routing_mode": mode,
        "stages": rows,
    }


def validate_journey_recipe(data: dict[str, Any]) -> dict[str, Any]:
    data = dict(data or {})
    version = int(data.get("melodex_journey") or 0)
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported Melodex journey recipe version: {version or '(missing)'}"
        )
    return make_journey_recipe(
        name=str(data.get("name") or "Journey recipe"),
        description=str(data.get("description") or ""),
        mode=str(data.get("routing_mode") or "balanced"),
        stages=[
            dict(stage)
            for stage in list(data.get("stages") or [])
            if isinstance(stage, dict)
        ],
        ref_map=None,
    )


def save_journey_recipe(path: Path, recipe: dict[str, Any]) -> Path:
    path = Path(path)
    if path.suffix.lower() != ".mdxjourney":
        path = path.with_suffix(".mdxjourney")
    data = validate_journey_recipe(recipe)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_journey_recipe(path: Path) -> dict[str, Any]:
    path = Path(path)
    try:
        raw = json.loads(path.read_text("utf-8"))
    except Exception as exc:
        raise ValueError(f"Could not read journey recipe: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("Journey recipe must be a JSON object")
    return validate_journey_recipe(raw)


def _selector_score(
    selector: dict[str, Any],
    track: dict[str, Any],
) -> tuple[int, tuple[str, str, str]]:
    selector = dict(selector or {})
    track = dict(track or {})
    wanted_mbid = _norm(selector.get("musicbrainz_recording_id"))
    got_mbid = _norm(
        track.get("musicbrainz_recording_id")
        or track.get("recording_mbid")
    )
    if wanted_mbid and got_mbid:
        if wanted_mbid != got_mbid:
            return -1, ("", "", "")
        return 1000, (
            _norm(track.get("artist")),
            _norm(track.get("title")),
            _norm(track.get("album")),
        )

    wanted_title = _norm(selector.get("title"))
    wanted_artist = _norm(selector.get("artist"))
    wanted_album = _norm(selector.get("album"))
    got_title = _norm(track.get("title"))
    got_artist = _norm(track.get("artist"))
    got_album = _norm(track.get("album"))

    if wanted_title and got_title != wanted_title:
        return -1, ("", "", "")
    if wanted_artist and got_artist != wanted_artist:
        return -1, ("", "", "")
    score = 100
    if wanted_title and got_title == wanted_title:
        score += 400
    if wanted_artist and got_artist == wanted_artist:
        score += 300
    if wanted_album and got_album == wanted_album:
        score += 150
    elif wanted_album:
        score -= 25
    return score, (got_artist, got_title, got_album)


def resolve_track_selector(
    selector: dict[str, Any],
    ref_map: dict[str, dict[str, Any]],
) -> str:
    ranked: list[tuple[int, tuple[str, str, str], str]] = []
    for ref, track in ref_map.items():
        score, tie = _selector_score(selector, dict(track or {}))
        if score >= 0:
            ranked.append((score, tie, str(ref)))
    if not ranked:
        return ""
    ranked.sort(key=lambda row: (-row[0], row[1], row[2]))
    return ranked[0][2]


def materialize_recipe_stages(
    recipe: dict[str, Any],
    ref_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    recipe = validate_journey_recipe(recipe)
    stages: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for raw in list(recipe.get("stages") or []):
        stage = dict(raw)
        if stage.get("type") != "track":
            stages.append(stage)
            continue
        ref = resolve_track_selector(
            dict(stage.get("selector") or {}),
            ref_map,
        )
        if not ref:
            unresolved.append(stage)
            continue
        stages.append(
            {
                "type": "track",
                "ref": ref,
                "label": str(stage.get("label") or "Track waypoint"),
            }
        )
    return {
        "recipe": recipe,
        "stages": stages,
        "unresolved": unresolved,
    }


def public_recipe_snapshot(recipe: dict[str, Any]) -> dict[str, Any]:
    """Return only the intentionally shareable recipe payload."""
    return validate_journey_recipe(recipe)


__all__ = [
    "SCHEMA_VERSION",
    "ALLOWED_MODES",
    "ALLOWED_CONSTRAINTS",
    "portable_track_selector",
    "make_journey_recipe",
    "validate_journey_recipe",
    "save_journey_recipe",
    "load_journey_recipe",
    "resolve_track_selector",
    "materialize_recipe_stages",
    "public_recipe_snapshot",
]
