from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from typing import Any


_GENRE_SEPARATOR = re.compile(r"[;|]")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _genres(track: dict[str, Any]) -> list[str]:
    value = track.get("genres") or track.get("genre")
    raw = value if isinstance(value, (list, tuple, set)) else _GENRE_SEPARATOR.split(_text(value))
    result: list[str] = []
    seen: set[str] = set()
    for item in raw:
        name = _text(item)
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            result.append(name[:80])
        if len(result) >= 8:
            break
    return result


def _track_metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("track_json")
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _evidence(row: dict[str, Any]) -> tuple[float, float, float, float]:
    """Return durable positive, explicit negative, completions and plays.

    Skips are intentionally absent: the current aggregate skip counter has no
    session timestamp, so it cannot safely be treated as a lasting preference.
    """
    plays = _count(row.get("plays"))
    completes = _count(row.get("completes"))
    loves = _count(row.get("loves"))
    keeps = _count(row.get("keeps"))
    dislikes = _count(row.get("dislikes"))
    positive = (
        4.0 * min(loves, 1)
        + 2.0 * min(keeps, 2)
        + 0.45 * min(completes, 5)
        + 0.16 * math.log1p(plays)
    )
    negative = 4.5 * min(dislikes, 1)
    return positive, negative, float(completes), float(plays)


def _summarize_entities(groups: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for key, group in groups.items():
        positive = float(group["positive"])
        negative = float(group["negative"])
        evidence = positive + negative
        output[key] = {
            "name": str(group["name"]),
            "score": max(-1.0, min(1.0, (positive - negative) / (evidence + 2.0))),
            "confidence": max(0.0, min(1.0, 1.0 - math.exp(-evidence / 4.0))),
            "tracks": int(group["tracks"]),
            "plays": int(group["plays"]),
            "completions": int(group["completions"]),
            "loved_tracks": int(group["loved_tracks"]),
            "kept_tracks": int(group["kept_tracks"]),
            "disliked_tracks": int(group["disliked_tracks"]),
            "more_corrections": int(group["more_corrections"]),
            "less_corrections": int(group["less_corrections"]),
        }
    return output


def _recent_entities(
    recent_tracks: list[dict[str, Any]], *, genres: bool = False
) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for track in list(recent_tracks or [])[:20]:
        if not isinstance(track, dict):
            continue
        names = _genres(track) if genres else [_text(track.get("artist") or track.get("album_artist"))]
        for name in names:
            key = name.casefold()
            if key:
                entry = counts.setdefault(key, {"name": name, "tracks": 0})
                entry["tracks"] += 1
    return sorted(counts.values(), key=lambda item: (-item["tracks"], item["name"].casefold()))[:5]


def _session_reaction_entities(
    session_tracks: list[dict[str, Any]], *, now: float
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], int, int]:
    """Summarize completed listens and quick skips from the latest session.

    An incomplete play is neutral unless the next track started within the
    same 30-second window Melodex already uses to record an explicit skip.
    Recent reactions decay over time and expire after 14 days.
    """
    groups: dict[str, dict[str, dict[str, Any]]] = {"artist": {}, "genre": {}}
    tracks = [dict(row) for row in list(session_tracks or []) if isinstance(row, dict)]
    completed_tracks = 0
    quick_skips = 0

    for index, track in enumerate(tracks):
        try:
            played_at = float(track.get("_played_at") or 0.0)
        except (TypeError, ValueError, OverflowError):
            continue
        if played_at <= 0.0:
            continue
        age_hours = max(0.0, (float(now) - played_at) / 3600.0)
        if age_hours > 14.0 * 24.0:
            continue

        if bool(track.get("_completed")):
            direction = "positive"
            completed_tracks += 1
        elif index + 1 < len(tracks):
            try:
                next_played_at = float(tracks[index + 1].get("_played_at") or 0.0)
            except (TypeError, ValueError, OverflowError):
                next_played_at = 0.0
            gap = next_played_at - played_at
            if not 0.0 <= gap < 30.0:
                continue
            direction = "negative"
            quick_skips += 1
        else:
            continue

        weight = 0.5 ** (age_hours / 24.0)
        artist = _text(track.get("artist") or track.get("album_artist"))
        entities: list[tuple[str, str, float]] = []
        if artist:
            entities.append(("artist", artist, 1.0))
        genre_names = _genres(track)
        if genre_names:
            entities.extend(("genre", name, 1.0 / len(genre_names)) for name in genre_names)

        for kind, name, share in entities:
            key = name.casefold()
            group = groups[kind].setdefault(
                key,
                {
                    "name": name,
                    "positive": 0.0,
                    "negative": 0.0,
                    "completed_tracks": 0,
                    "quick_skips": 0,
                },
            )
            group[direction] += weight * share
            group["completed_tracks"] += int(direction == "positive")
            group["quick_skips"] += int(direction == "negative")

    def summarize(source: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        for key, group in source.items():
            positive = float(group["positive"])
            negative = float(group["negative"])
            evidence = positive + negative
            output[key] = {
                "name": str(group["name"]),
                "score": max(-1.0, min(1.0, (positive - negative) / (evidence + 2.0))),
                "confidence": max(0.0, min(1.0, 1.0 - math.exp(-evidence / 1.5))),
                "completed_tracks": int(group["completed_tracks"]),
                "quick_skips": int(group["quick_skips"]),
            }
        return output

    return (
        summarize(groups["artist"]),
        summarize(groups["genre"]),
        completed_tracks,
        quick_skips,
    )


@dataclass(frozen=True)
class TasteModel:
    """Small, local-only model with separate identity, context and exploration."""

    artists: dict[str, dict[str, Any]]
    genres: dict[str, dict[str, Any]]
    context_tracks: int
    recent_artists: list[dict[str, Any]]
    recent_genres: list[dict[str, Any]]
    session_artists: dict[str, dict[str, Any]]
    session_genres: dict[str, dict[str, Any]]
    session_completed_tracks: int
    session_quick_skips: int
    adventure: float

    def as_dict(self) -> dict[str, Any]:
        def visible(source: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
            entries = sorted(
                source.values(),
                key=lambda item: (
                    -float(item["score"]) * float(item["confidence"]),
                    -int(item["tracks"]),
                    str(item["name"]).casefold(),
                ),
            )[:8]
            return [
                {
                    "name": str(item["name"]),
                    "score": round(float(item["score"]), 3),
                    "confidence": round(float(item["confidence"]), 3),
                    "tracks": int(item["tracks"]),
                    "plays": int(item["plays"]),
                    "completions": int(item["completions"]),
                    "loved_tracks": int(item["loved_tracks"]),
                    "kept_tracks": int(item["kept_tracks"]),
                    "disliked_tracks": int(item["disliked_tracks"]),
                    "more_corrections": int(item["more_corrections"]),
                    "less_corrections": int(item["less_corrections"]),
                }
                for item in entries
            ]

        def visible_session(source: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
            entries = sorted(
                source.values(),
                key=lambda item: (
                    -abs(float(item["score"]) * float(item["confidence"])),
                    str(item["name"]).casefold(),
                ),
            )[:5]
            return [
                {
                    "name": str(item["name"]),
                    "score": round(float(item["score"]), 3),
                    "confidence": round(float(item["confidence"]), 3),
                    "completed_tracks": int(item["completed_tracks"]),
                    "quick_skips": int(item["quick_skips"]),
                }
                for item in entries
            ]

        adventure_label = (
            "comfortable" if self.adventure < 0.25
            else "balanced" if self.adventure < 0.7
            else "adventurous"
        )
        return {
            "version": 1,
            "storage": "on-device",
            "identity": {
                "artists": visible(self.artists),
                "genres": visible(self.genres),
            },
            "context": {
                "recent_tracks": max(0, int(self.context_tracks)),
                "artists": [dict(item) for item in self.recent_artists],
                "genres": [dict(item) for item in self.recent_genres],
            },
            "session_reactions": {
                "completed_tracks": max(0, int(self.session_completed_tracks)),
                "quick_skips": max(0, int(self.session_quick_skips)),
                "artists": visible_session(self.session_artists),
                "genres": visible_session(self.session_genres),
            },
            "exploration": {
                "adventure": round(self.adventure, 3),
                "label": adventure_label,
            },
        }


def build_taste_model(
    track_signals: list[dict[str, Any]],
    recent_tracks: list[dict[str, Any]] | None = None,
    *,
    adventure: float = 0.35,
    corrections: list[dict[str, Any]] | None = None,
    session_tracks: list[dict[str, Any]] | None = None,
    now: float | None = None,
) -> TasteModel:
    """Build an inspectable taste model from local playback memory.

    Identity uses explicit likes/keeps/dislikes and completed listens. Plays
    alone contribute very weakly. Recent context is reported separately, and
    the exploration value comes from the user's current session control.
    """
    groups: dict[str, dict[str, dict[str, Any]]] = {
        "artist": {},
        "genre": {},
    }
    for row in list(track_signals or []):
        if not isinstance(row, dict):
            continue
        track = _track_metadata(row)
        artist = _text(row.get("artist") or track.get("artist") or track.get("album_artist"))
        genre_names = _genres(track)
        positive, negative, completions, plays = _evidence(row)
        if not positive and not negative:
            continue

        entities: list[tuple[str, str, float]] = []
        if artist:
            entities.append(("artist", artist, 1.0))
        if genre_names:
            entities.extend(("genre", name, 1.0 / len(genre_names)) for name in genre_names)
        loved = _count(row.get("loves")) > 0
        kept = _count(row.get("keeps")) > 0
        disliked = _count(row.get("dislikes")) > 0
        for kind, name, share in entities:
            key = name.casefold()
            group = groups[kind].setdefault(
                key,
                {
                    "name": name,
                    "positive": 0.0,
                    "negative": 0.0,
                    "tracks": 0,
                    "plays": 0,
                    "completions": 0,
                    "loved_tracks": 0,
                    "kept_tracks": 0,
                    "disliked_tracks": 0,
                    "more_corrections": 0,
                    "less_corrections": 0,
                },
            )
            group["positive"] += positive * share
            group["negative"] += negative * share
            group["tracks"] += 1
            group["plays"] += _count(plays)
            group["completions"] += _count(completions)
            group["loved_tracks"] += int(loved)
            group["kept_tracks"] += int(kept)
            group["disliked_tracks"] += int(disliked)

    for correction in list(corrections or []):
        if not isinstance(correction, dict):
            continue
        direction = str(correction.get("direction") or "").strip().lower()
        if direction not in {"more", "less"}:
            continue
        artist = _text(correction.get("artist"))
        genre_names = _genres(correction)
        if not artist and not genre_names:
            continue
        positive = 6.0 if direction == "more" else 0.0
        negative = 7.0 if direction == "less" else 0.0
        entities: list[tuple[str, str, float]] = []
        if artist:
            entities.append(("artist", artist, 1.0))
        if genre_names:
            entities.extend(("genre", name, 1.0 / len(genre_names)) for name in genre_names)
        for kind, name, share in entities:
            key = name.casefold()
            group = groups[kind].setdefault(
                key,
                {
                    "name": name,
                    "positive": 0.0,
                    "negative": 0.0,
                    "tracks": 0,
                    "plays": 0,
                    "completions": 0,
                    "loved_tracks": 0,
                    "kept_tracks": 0,
                    "disliked_tracks": 0,
                    "more_corrections": 0,
                    "less_corrections": 0,
                },
            )
            group["positive"] += positive * share
            group["negative"] += negative * share
            group["tracks"] += 1
            group["more_corrections"] += int(direction == "more")
            group["less_corrections"] += int(direction == "less")

    recent = [dict(item) for item in list(recent_tracks or [])[:20] if isinstance(item, dict)]
    try:
        session_now = float(now) if now is not None else time.time()
    except (TypeError, ValueError, OverflowError):
        session_now = time.time()
    session_artists, session_genres, completed_count, quick_skip_count = (
        _session_reaction_entities(session_tracks or [], now=session_now)
    )
    try:
        requested_adventure = float(adventure)
    except (TypeError, ValueError):
        requested_adventure = 0.35
    requested_adventure = max(0.0, min(1.0, requested_adventure))
    return TasteModel(
        artists=_summarize_entities(groups["artist"]),
        genres=_summarize_entities(groups["genre"]),
        context_tracks=len(recent),
        recent_artists=_recent_entities(recent),
        recent_genres=_recent_entities(recent, genres=True),
        session_artists=session_artists,
        session_genres=session_genres,
        session_completed_tracks=completed_count,
        session_quick_skips=quick_skip_count,
        adventure=requested_adventure,
    )


def build_local_taste_model(
    state: Any,
    *,
    adventure: float = 0.35,
    recent_limit: int = 20,
    signal_limit: int = 5000,
    track_signals: list[dict[str, Any]] | None = None,
) -> TasteModel:
    """Build the shared taste model from local UserState data only."""
    if state is None:
        return build_taste_model([], adventure=adventure)
    latest_session = state.sessions(1)
    return build_taste_model(
        (
            list(track_signals)
            if track_signals is not None
            else state.track_signals(max(1, int(signal_limit)))
        ),
        state.recent_tracks(max(1, int(recent_limit))),
        adventure=adventure,
        corrections=state.taste_corrections(max(1, int(signal_limit))),
        session_tracks=latest_session[0]["tracks"] if latest_session else [],
    )


def score_taste_match(track: dict[str, Any], model: TasteModel) -> tuple[float, str]:
    """Return a small confidence-weighted ranking adjustment and its reason."""
    artist = _text(track.get("artist") or track.get("album_artist"))
    artist_signal = model.artists.get(artist.casefold(), {}) if artist else {}
    artist_value = (
        float(artist_signal.get("score") or 0.0)
        * float(artist_signal.get("confidence") or 0.0)
    )
    genre_signals = [model.genres[name.casefold()] for name in _genres(track) if name.casefold() in model.genres]
    genre_value = (
        sum(
            float(item.get("score") or 0.0) * float(item.get("confidence") or 0.0)
            for item in genre_signals
        ) / len(genre_signals)
        if genre_signals else 0.0
    )
    values = []
    if artist_signal:
        values.append((0.72, artist_value))
    if genre_signals:
        values.append((0.28, genre_value))
    weight = sum(item[0] for item in values)
    adjustment = sum(factor * value for factor, value in values) / weight if weight else 0.0
    adjustment = max(-1.0, min(1.0, adjustment))
    identity_adjustment = adjustment

    session_artist_signal = model.session_artists.get(artist.casefold(), {}) if artist else {}
    session_artist_value = (
        float(session_artist_signal.get("score") or 0.0)
        * float(session_artist_signal.get("confidence") or 0.0)
    )
    session_genre_signals = [
        model.session_genres[name.casefold()]
        for name in _genres(track)
        if name.casefold() in model.session_genres
    ]
    session_genre_value = (
        sum(
            float(item.get("score") or 0.0) * float(item.get("confidence") or 0.0)
            for item in session_genre_signals
        ) / len(session_genre_signals)
        if session_genre_signals else 0.0
    )
    session_values = []
    if session_artist_signal:
        session_values.append((0.72, session_artist_value))
    if session_genre_signals:
        session_values.append((0.28, session_genre_value))
    session_weight = sum(item[0] for item in session_values)
    session_adjustment = (
        sum(factor * value for factor, value in session_values) / session_weight
        if session_weight else 0.0
    )
    adjustment = max(-1.0, min(1.0, identity_adjustment + 0.65 * session_adjustment))

    best_genre = max(
        genre_signals,
        key=lambda item: float(item.get("score") or 0.0)
        * float(item.get("confidence") or 0.0),
        default={},
    )
    best_genre_value = (
        float(best_genre.get("score") or 0.0)
        * float(best_genre.get("confidence") or 0.0)
    )
    least_genre = min(
        genre_signals,
        key=lambda item: float(item.get("score") or 0.0)
        * float(item.get("confidence") or 0.0),
        default={},
    )
    least_genre_value = (
        float(least_genre.get("score") or 0.0)
        * float(least_genre.get("confidence") or 0.0)
    )
    if artist_value >= 0.2:
        reason = (
            f"matches your request for more {artist_signal['name']}"
            if int(artist_signal.get("more_corrections") or 0)
            else f"matches your listening history with {artist_signal['name']}"
        )
    elif artist_value <= -0.2 and int(artist_signal.get("less_corrections") or 0):
        reason = f"reflects your request for less {artist_signal['name']}"
    elif best_genre_value >= 0.2:
        reason = (
            f"matches your request for more {best_genre['name']}"
            if int(best_genre.get("more_corrections") or 0)
            else f"matches {best_genre['name']} in your listening history"
        )
    elif genre_value <= -0.2 and least_genre_value <= -0.2 and int(
        least_genre.get("less_corrections") or 0
    ):
        reason = f"reflects your request for less {least_genre['name']}"
    else:
        reason = ""
    session_reason = ""
    if session_artist_value >= 0.15 and int(session_artist_signal.get("completed_tracks") or 0):
        session_reason = f"follows your recent session with {session_artist_signal['name']}"
    elif session_artist_value <= -0.15 and int(session_artist_signal.get("quick_skips") or 0):
        session_reason = f"reflects a recent quick skip near {session_artist_signal['name']}"
    elif session_genre_signals:
        best_session_genre = max(
            session_genre_signals,
            key=lambda item: float(item.get("score") or 0.0)
            * float(item.get("confidence") or 0.0),
        )
        worst_session_genre = min(
            session_genre_signals,
            key=lambda item: float(item.get("score") or 0.0)
            * float(item.get("confidence") or 0.0),
        )
        best_session_genre_value = (
            float(best_session_genre.get("score") or 0.0)
            * float(best_session_genre.get("confidence") or 0.0)
        )
        worst_session_genre_value = (
            float(worst_session_genre.get("score") or 0.0)
            * float(worst_session_genre.get("confidence") or 0.0)
        )
        if best_session_genre_value >= 0.15 and int(best_session_genre.get("completed_tracks") or 0):
            session_reason = f"follows your recent session with {best_session_genre['name']}"
        elif worst_session_genre_value <= -0.15 and int(worst_session_genre.get("quick_skips") or 0):
            session_reason = f"reflects a recent quick skip near {worst_session_genre['name']}"
    if session_reason:
        reason = f"{reason} · {session_reason}" if reason else session_reason
    return adjustment, reason


__all__ = [
    "TasteModel",
    "build_local_taste_model",
    "build_taste_model",
    "score_taste_match",
]
