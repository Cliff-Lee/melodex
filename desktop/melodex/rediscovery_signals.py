from __future__ import annotations

import math
from typing import Any

from .user_state import UserState


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any) -> int:
    """Read common track tags such as ``4`` or ``4/12`` safely."""
    raw = _text(value).split("/", 1)[0].strip()
    try:
        number = int(raw)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _track_number(track: dict[str, Any]) -> int:
    for name in ("track_no", "track_number", "tracknumber"):
        number = _positive_int(track.get(name))
        if number:
            return number
    return 0


def _declared_track_total(track: dict[str, Any]) -> int:
    for name in ("track_no", "track_number", "tracknumber"):
        parts = _text(track.get(name)).split("/", 1)
        if len(parts) == 2:
            total = _positive_int(parts[1])
            if total:
                return total
    return 0


def _album_key(track: dict[str, Any]) -> str:
    album = _text(track.get("album")).casefold()
    if not album:
        return ""
    artist = _text(track.get("album_artist") or track.get("artist")).casefold()
    year = _text(track.get("year") or track.get("date"))[:4]
    return "|".join((artist, album, year))


def _artist_key(track: dict[str, Any]) -> str:
    return _text(track.get("album_artist") or track.get("artist")).casefold()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def build_rediscovery_signals(
    catalog: list[dict[str, Any]],
    track_signals: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build private, metadata-aware rediscovery context for a library slice.

    The result combines per-track listening state with album completeness,
    track order and artist coverage. Metadata signals stay useful before the
    listener has built up any playback history.
    """
    tracks: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    albums: dict[str, list[str]] = {}
    artists: dict[str, set[str]] = {}
    track_numbers: dict[str, int] = {}
    declared_totals: dict[str, int] = {}

    for raw in catalog:
        if not isinstance(raw, dict):
            continue
        track = dict(raw)
        key = UserState.track_key(track)
        if not key or key in seen:
            continue
        seen.add(key)
        tracks.append((key, track))

        album = _album_key(track)
        if album:
            albums.setdefault(album, []).append(key)
        artist = _artist_key(track)
        if artist:
            artists.setdefault(artist, set()).add(key)
        track_numbers[key] = _track_number(track)
        declared_totals[key] = _declared_track_total(track)

    album_played: dict[str, int] = {}
    for album, keys in albums.items():
        album_played[album] = sum(
            max(0, int((track_signals.get(key) or {}).get("plays") or 0)) > 0
            for key in keys
        )

    artist_played: dict[str, int] = {}
    for artist, keys in artists.items():
        artist_played[artist] = sum(
            max(0, int((track_signals.get(key) or {}).get("plays") or 0)) > 0
            for key in keys
        )

    # Include artists represented in history even when the old track is no
    # longer in the current catalog. This helps newly imported albums connect
    # to listening memory without retaining a second history index.
    for row in track_signals.values():
        artist = _text(row.get("artist")).casefold()
        if artist and int(row.get("plays") or 0) > 0:
            artist_played[artist] = max(1, artist_played.get(artist, 0))

    album_max_number = {
        album: max((track_numbers.get(key, 0) for key in keys), default=0)
        for album, keys in albums.items()
    }

    result: dict[str, dict[str, Any]] = {}
    for key, track in tracks:
        album = _album_key(track)
        artist = _artist_key(track)
        album_keys = albums.get(album, []) if album else []
        album_count = len(album_keys)
        played_in_album = album_played.get(album, 0) if album else 0
        album_gap = (
            1.0 - played_in_album / album_count
            if album_count >= 3 else 0.0
        )

        number = track_numbers.get(key, 0)
        total = max(
            declared_totals.get(key, 0),
            album_max_number.get(album, 0),
            album_count,
        )
        deep_cut = 0.0
        if number >= 3 and total >= 5:
            deep_cut = _clamp((number - 2) / max(1, total - 2))

        artist_tracks = max(1, len(artists.get(artist, ()))) if artist else 1
        played_artist_tracks = artist_played.get(artist, 0) if artist else 0
        artist_signal = _clamp(
            math.log1p(played_artist_tracks) / math.log(5.0)
        )

        library_score = _clamp(
            0.48 * deep_cut
            + 0.32 * album_gap
            + 0.20 * artist_signal
        )
        if deep_cut >= 0.55:
            reason = "deep cut in your library"
        elif played_in_album and album_gap >= 0.5:
            reason = "unheard part of an album you know"
        elif artist_signal >= 0.4:
            reason = "unplayed track from an artist you know"
        elif album_gap >= 0.5:
            reason = "unexplored album in your library"
        else:
            reason = ""

        result[key] = {
            "library_score": library_score,
            "deep_cut": deep_cut,
            "album_gap": _clamp(album_gap),
            "artist_familiarity": artist_signal,
            "album_track_count": album_count,
            "album_played_tracks": played_in_album,
            "artist_played_tracks": played_artist_tracks,
            "artist_library_tracks": artist_tracks,
            "reason": reason,
        }
    return result


__all__ = ["build_rediscovery_signals"]
