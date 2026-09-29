"""Small, deterministic models shared by the Living Canvas modes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import math
import re
from typing import Any, Iterable, Mapping

from .visualization_profile import VisualProfile


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _key(value: Any) -> str:
    return _text(value).casefold()


def _digest(value: str) -> bytes:
    return hashlib.blake2b(value.encode("utf-8", "replace"), digest_size=8, person=b"mdx-viz").digest()


def _identity(track: Mapping[str, Any]) -> str:
    artist = _key(track.get("artist"))
    title = _key(track.get("title"))
    if artist or title:
        return f"{artist}\x1f{title}"
    provider = _key(track.get("provider_id"))
    track_id = _key(track.get("track_id") or track.get("id"))
    return f"{provider}\x1f{track_id}" if provider or track_id else ""


@dataclass(frozen=True, slots=True)
class VisualNeighbour:
    """A display-only constellation node. It never contains a local path."""

    token: int
    artist: str
    title: str
    album: str
    relation: str
    x: float
    y: float


def build_constellation(
    current: Mapping[str, Any] | None,
    candidates: Iterable[Mapping[str, Any]],
    *,
    limit: int = 24,
) -> tuple[VisualNeighbour, ...]:
    """Lay out queue/history neighbours deterministically around the current track.

    Candidates may carry an integer ``_visual_token`` that the UI can map back
    to its private playback record. The renderer receives only display fields.
    """

    current = current if isinstance(current, Mapping) else {}
    current_artist = _key(current.get("artist"))
    current_album = _key(current.get("album"))
    current_key = _identity(current)
    clean: list[tuple[int, dict[str, str], str]] = []
    seen = {current_key} if current_key else set()
    for ordinal, raw in enumerate(candidates):
        if not isinstance(raw, Mapping):
            continue
        track = raw.get("track") if isinstance(raw.get("track"), Mapping) else raw
        key = _identity(track)
        if not key or key in seen:
            continue
        seen.add(key)
        try:
            token = int(raw.get("_visual_token", ordinal))
        except (TypeError, ValueError, OverflowError):
            token = ordinal
        artist = _text(track.get("artist"))
        title = _text(track.get("title"))
        album = _text(track.get("album"))
        explicit = _text(raw.get("_visual_relation"))
        if explicit in {"Up next", "Played earlier"}:
            relation = explicit
        elif current_album and _key(album) == current_album:
            relation = "Same album"
        elif current_artist and _key(artist) == current_artist:
            relation = "Same artist"
        else:
            relation = "Recently heard"
        item = {"artist": artist, "title": title, "album": album}
        clean.append((token, item, relation))

    clean = clean[: max(0, min(24, int(limit)))]
    if not clean:
        return ()
    phase = int.from_bytes(_digest(current_key or "melodex")[:4], "big") / 2**32 * math.tau
    count = len(clean)
    result: list[VisualNeighbour] = []
    for index, (token, track, relation) in enumerate(clean):
        seed = int.from_bytes(_digest("\x1f".join((track["artist"], track["title"])))[:4], "big")
        angle = phase + math.tau * index / count
        wobble = (seed % 1000) / 1000.0
        radius = 0.28 + 0.13 * wobble
        result.append(
            VisualNeighbour(
                token=token,
                artist=track["artist"],
                title=track["title"],
                album=track["album"],
                relation=relation,
                x=max(0.08, min(0.92, 0.5 + radius * math.cos(angle))),
                y=max(0.10, min(0.90, 0.5 + radius * 0.70 * math.sin(angle))),
            )
        )
    return tuple(result)


@dataclass(frozen=True, slots=True)
class SonicWeather:
    motion: str
    tone: str
    density: str
    summary: str
    based_on_flow: bool


def describe_weather(profile: VisualProfile) -> SonicWeather:
    """Translate cached musical features into plain, repeatable listening weather."""

    bpm = profile.bpm
    if bpm < 75:
        motion = "slow-moving"
    elif bpm < 112:
        motion = "drifting"
    elif bpm < 145:
        motion = "rolling"
    else:
        motion = "fast-moving"

    if profile.brightness < 0.34:
        tone = "warm and shadowed"
    elif profile.brightness > 0.68:
        tone = "bright and open"
    else:
        tone = "balanced in tone"

    combined = profile.energy * 0.62 + profile.rhythm * 0.38
    if combined < 0.30:
        density = "spacious"
    elif combined > 0.68:
        density = "dense and active"
    else:
        density = "gently layered"

    available = bool(profile.flow_available)
    if not available:
        summary = "Identity-based weather · cached Flow analysis is not available"
    else:
        summary = f"{tone} · {density} · {motion}"
    return SonicWeather(motion, tone, density, summary, available)


@dataclass(frozen=True, slots=True)
class LyricFrame:
    previous: str
    current: str
    following: str
    synced: bool
    source: str


def lyric_frame(lyrics: Mapping[str, Any] | None, position_ms: int, duration_ms: int) -> LyricFrame:
    """Select the current lyric from local synced lines or gently paced plain text."""

    lyrics = lyrics if isinstance(lyrics, Mapping) else {}
    synced = [row for row in lyrics.get("synced", ()) if isinstance(row, Mapping)]
    if synced:
        idx = -1
        for i, row in enumerate(synced):
            try:
                stamp = int(row.get("time_ms") or 0)
            except (TypeError, ValueError, OverflowError):
                continue
            if stamp <= max(0, int(position_ms)):
                idx = i
            else:
                break
        if idx < 0:
            next_line = _text(synced[0].get("text")) if synced else ""
            return LyricFrame("", "", next_line, True, _text(lyrics.get("source")))
        previous = _text(synced[idx - 1].get("text")) if idx > 0 else ""
        current = _text(synced[idx].get("text"))
        following = _text(synced[idx + 1].get("text")) if idx + 1 < len(synced) else ""
        return LyricFrame(previous, current, following, True, _text(lyrics.get("source")))

    raw = str(lyrics.get("text") or "")
    lines = [_text(line) for line in re.split(r"[\r\n]+", raw) if _text(line)]
    if not lines:
        return LyricFrame("", "", "", False, _text(lyrics.get("source")))
    try:
        position = max(0, int(position_ms))
        duration = max(0, int(duration_ms))
    except (TypeError, ValueError, OverflowError):
        position, duration = 0, 0
    fraction = min(1.0, position / duration) if duration else 0.0
    idx = min(len(lines) - 1, int(fraction * len(lines)))
    return LyricFrame(
        lines[idx - 1] if idx else "",
        lines[idx],
        lines[idx + 1] if idx + 1 < len(lines) else "",
        False,
        _text(lyrics.get("source")),
    )


@dataclass(frozen=True, slots=True)
class MemoryMark:
    label: str
    detail: str
    count: int
    hue: int
    x: float
    y: float


def build_visual_memory(
    tracks: Iterable[Mapping[str, Any]],
    granularity: str = "sessions",
    *,
    limit: int = 128,
) -> tuple[MemoryMark, ...]:
    """Aggregate existing local play records into a bounded visual atlas."""

    mode = str(granularity or "sessions").casefold()
    if mode not in {"sessions", "albums", "weeks", "years"}:
        mode = "sessions"
    rows: list[tuple[float, Mapping[str, Any]]] = []
    for track in tracks:
        if not isinstance(track, Mapping):
            continue
        try:
            stamp = float(track.get("_played_at") or 0.0)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(stamp) and stamp > 0:
            try:
                datetime.fromtimestamp(stamp)
            except (OverflowError, OSError, ValueError):
                continue
            rows.append((stamp, track))
    rows.sort(key=lambda item: item[0])
    if not rows:
        return ()

    groups: list[list[tuple[float, Mapping[str, Any]]]] = []
    if mode == "sessions":
        for item in rows:
            if not groups or item[0] - groups[-1][-1][0] > 45 * 60:
                groups.append([item])
            else:
                groups[-1].append(item)
    else:
        grouped: dict[str, list[tuple[float, Mapping[str, Any]]]] = {}
        for item in rows:
            moment = datetime.fromtimestamp(item[0])
            if mode == "albums":
                group_key = "\x1f".join((_key(item[1].get("artist")), _key(item[1].get("album"))))
                group_key = group_key if group_key.strip("\x1f") else _identity(item[1])
            elif mode == "weeks":
                iso = moment.isocalendar()
                group_key = f"{iso.year}-W{iso.week:02d}"
            else:
                group_key = str(moment.year)
            grouped.setdefault(group_key, []).append(item)
        groups = [grouped[key] for key in sorted(grouped, key=lambda key: grouped[key][0][0])]

    groups = groups[-max(1, min(128, int(limit))):]
    first_stamp, last_stamp = rows[0][0], rows[-1][0]
    span = max(1.0, last_stamp - first_stamp)
    result: list[MemoryMark] = []
    for index, group in enumerate(groups):
        start = group[0][0]
        first = group[0][1]
        album = _text(first.get("album"))
        artist = _text(first.get("artist"))
        if mode == "albums":
            label = album or _text(first.get("title")) or "Untitled album"
            detail = artist or "Unknown artist"
        elif mode == "years":
            label = datetime.fromtimestamp(start).strftime("%Y")
            detail = f"{len(group)} plays"
        elif mode == "weeks":
            label = datetime.fromtimestamp(start).strftime("%b %d")
            detail = f"{len(group)} plays · {datetime.fromtimestamp(start).strftime('%Y') }"
        else:
            label = datetime.fromtimestamp(start).strftime("%a %H:%M")
            artists = list(dict.fromkeys(_text(row.get("artist")) for _, row in group if _text(row.get("artist"))))
            detail = ", ".join(artists[:2]) or f"{len(group)} tracks"
        identity = "\x1f".join((_key(label), _key(detail), mode))
        seed = int.from_bytes(_digest(identity), "big")
        x = (start - first_stamp) / span if len(groups) > 1 else 0.5
        y = 0.22 + ((seed % 10000) / 10000.0) * 0.56
        if len(groups) == 1:
            x = 0.5 + (index - (len(groups) - 1) / 2) * 0.08
        result.append(MemoryMark(label, detail, len(group), seed % 360, x, y))
    return tuple(result)
