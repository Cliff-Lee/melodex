from __future__ import annotations

import json
import math
import sys


_FEATURE_ORDER = ("tempo", "energy", "harmony", "timbre", "rhythm", "mixability")
_FEATURE_LABELS = {
    "tempo": ("the pulse", "pulse"),
    "energy": ("energy", "energy"),
    "harmony": ("harmonic colour", "harmony"),
    "timbre": ("tone colour", "tone"),
    "rhythm": ("rhythmic density", "rhythm"),
    "mixability": ("mix shape", "mix shape"),
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _number(analysis: dict, key: str) -> float | None:
    try:
        value = float(analysis.get(key))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _near(a: float | None, b: float | None, scale: float) -> float | None:
    if a is None or b is None:
        return None
    return _clamp(math.exp(-abs(a - b) / max(1e-9, scale)))


def _tempo(a: dict, b: dict) -> float | None:
    aa, bb = _number(a, "bpm"), _number(b, "bpm")
    if aa is None or bb is None or aa <= 0 or bb <= 0:
        return None
    ratios = (bb / aa, (bb * 0.5) / aa, (bb * 2.0) / aa)
    difference = min(abs(math.log(max(1e-6, ratio), 2.0)) for ratio in ratios)
    return _clamp(math.exp(-9.0 * difference * difference))


def _harmony(a: dict, b: dict) -> float | None:
    try:
        left, right = int(a.get("key_pc", -1)), int(b.get("key_pc", -1))
    except (TypeError, ValueError):
        return None
    if left not in range(12) or right not in range(12):
        return None
    distance = (right - left) % 12
    left_mode, right_mode = str(a.get("key_mode") or ""), str(b.get("key_mode") or "")
    if distance == 0:
        if left_mode not in {"major", "minor"} or right_mode not in {"major", "minor"}:
            return 0.88
        return 1.0 if left_mode == right_mode else 0.92
    if left_mode != right_mode and distance in {3, 9}:
        return 0.90
    if distance in {5, 7}:
        return 0.84
    if distance in {2, 10}:
        return 0.66
    if distance in {1, 11}:
        return 0.48
    return 0.35


def _timbre(a: dict, b: dict) -> float | None:
    aa, bb = _number(a, "spectral_centroid"), _number(b, "spectral_centroid")
    if aa is None or bb is None or aa < 0 or bb < 0:
        return None
    return _clamp(math.exp(-1.8 * abs(math.log((bb + 120.0) / (aa + 120.0)))))


def _mixability(a: dict, b: dict) -> float | None:
    pairs = (
        (_number(a, "intro_mixability"), _number(b, "intro_mixability")),
        (_number(a, "outro_mixability"), _number(b, "outro_mixability")),
    )
    scores = [_near(left, right, 0.35) for left, right in pairs]
    valid = [score for score in scores if score is not None]
    return sum(valid) / len(valid) if valid else None


def _similarities(seed: dict, candidate: dict) -> dict[str, float]:
    if not isinstance(seed.get("analysis"), dict):
        return {}
    if not isinstance(candidate.get("analysis"), dict):
        return {}
    left, right = seed["analysis"], candidate["analysis"]
    raw = {
        "tempo": _tempo(left, right),
        "energy": _near(_number(left, "energy"), _number(right, "energy"), 0.22),
        "harmony": _harmony(left, right),
        "timbre": _timbre(left, right),
        "rhythm": _near(_number(left, "onset_density"), _number(right, "onset_density"), 0.12),
        "mixability": _mixability(left, right),
    }
    return {key: value for key, value in raw.items() if value is not None}


def _score(seed: dict, candidate: dict, adventure: float) -> dict | None:
    similarities = _similarities(seed, candidate)
    if len(similarities) < 4:
        return None

    adventure = _clamp(adventure)
    anchor_floor = 0.78 - 0.10 * adventure
    contrast_floor = 0.30 + 0.12 * adventure
    anchor_weight = 0.64 - 0.24 * adventure
    contrast_weight = 1.0 - anchor_weight
    best: dict | None = None

    for anchor_index, anchor in enumerate(_FEATURE_ORDER):
        anchor_score = similarities.get(anchor)
        if anchor_score is None or anchor_score < anchor_floor:
            continue
        other = sorted(
            (
                (value, key)
                for key, value in similarities.items()
                if key != anchor
            ),
            key=lambda item: (item[0], _FEATURE_ORDER.index(item[1])),
        )
        if len(other) < 3 or sum(value <= 0.72 for value, _key in other) < 2:
            continue
        contrasts = other[:2]
        contrast_score = 1.0 - (contrasts[0][0] + contrasts[1][0]) / 2.0
        if contrast_score < contrast_floor:
            continue
        score = _clamp(anchor_weight * anchor_score + contrast_weight * contrast_score)
        tie_key = (score, anchor_score, -anchor_index)
        if best is None or tie_key > best["_tie_key"]:
            best = {
                "score": score,
                "anchor": anchor,
                "contrasts": [key for _value, key in contrasts],
                "_tie_key": tie_key,
            }

    return best


def _reason(scored: dict) -> tuple[str, list[str]]:
    anchor_phrase, anchor_badge = _FEATURE_LABELS[scored["anchor"]]
    contrast_phrases = [_FEATURE_LABELS[key][0] for key in scored["contrasts"]]
    contrast_badges = [f"new {_FEATURE_LABELS[key][1]}" for key in scored["contrasts"]]
    reason = (
        f"Shares {anchor_phrase}; moves away from "
        f"{contrast_phrases[0]} and {contrast_phrases[1]}."
    )
    return reason, [f"shared {anchor_badge}", *contrast_badges]


def suggest(params: dict) -> dict:
    intent = str(params.get("intent") or "")
    empty = {
        "schema_version": "0.1",
        "capability": "library_suggestions",
        "intent": intent,
        "suggestions": [],
    }
    if intent != "detour":
        return empty

    tracks = [item for item in (params.get("tracks") or []) if isinstance(item, dict)]
    by_ref = {
        str(item.get("ref") or ""): item
        for item in tracks
        if str(item.get("ref") or "")
    }
    seeds = [str(ref) for ref in (params.get("seed_refs") or []) if str(ref)]
    seed = by_ref.get(seeds[0]) if seeds else None
    if seed is None:
        return empty

    try:
        adventure = float(params.get("adventure", 0.35))
    except (TypeError, ValueError):
        adventure = 0.35
    if not math.isfinite(adventure):
        adventure = 0.35
    adventure = _clamp(adventure)
    try:
        limit = int(params.get("limit", 12))
    except (TypeError, ValueError):
        limit = 12
    limit = max(1, min(50, limit))

    rows: list[dict] = []
    for candidate in tracks:
        ref = str(candidate.get("ref") or "")
        if not ref or ref in seeds:
            continue
        taste = candidate.get("taste") if isinstance(candidate.get("taste"), dict) else {}
        try:
            if int(taste.get("dislikes") or 0) > 0:
                continue
        except (TypeError, ValueError):
            continue
        scored = _score(seed, candidate, adventure)
        if scored is None:
            continue
        reason, badges = _reason(scored)
        rows.append(
            {
                "ref": ref,
                "score": scored["score"],
                "reason": reason,
                "badges": badges,
                "_anchor": scored["anchor"],
            }
        )

    rows.sort(
        key=lambda row: (
            -float(row["score"]),
            _FEATURE_ORDER.index(row["_anchor"]),
            str(row["ref"]).casefold(),
        )
    )
    # Keep the shortlist from becoming six versions of the same kind of detour.
    max_per_anchor = max(2, math.ceil(limit / len(_FEATURE_ORDER)))
    selected: list[dict] = []
    counts = {key: 0 for key in _FEATURE_ORDER}
    for row in rows:
        anchor = row["_anchor"]
        if counts[anchor] >= max_per_anchor:
            continue
        selected.append(row)
        counts[anchor] += 1
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        selected_refs = {row["ref"] for row in selected}
        for row in rows:
            if row["ref"] in selected_refs:
                continue
            selected.append(row)
            selected_refs.add(row["ref"])
            if len(selected) >= limit:
                break
    suggestions = [
        {key: value for key, value in row.items() if not key.startswith("_")}
        for row in selected[:limit]
    ]
    return {
        "schema_version": "0.1",
        "capability": "library_suggestions",
        "intent": intent,
        "suggestions": suggestions,
    }


def respond(request: dict) -> dict:
    if request.get("method") == "library.suggest":
        return suggest(request.get("params") or {})
    raise RuntimeError("unsupported method")


def run_jsonrpc() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        request = None
        try:
            request = json.loads(line)
            payload = {"jsonrpc": "2.0", "id": request.get("id"), "result": respond(request)}
        except Exception as exc:
            request_id = request.get("id") if isinstance(request, dict) else None
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(exc)},
            }
        print(json.dumps(payload, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    run_jsonrpc()
