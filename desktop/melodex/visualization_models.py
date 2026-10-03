"""Small, deterministic models shared by the Living Canvas modes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import math
import re
from typing import Any, Iterable, Mapping

from .lyrics_state import LyricFrame, lyric_frame
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
    strength: float = 0.5


def build_constellation(
    current: Mapping[str, Any] | None,
    candidates: Iterable[Mapping[str, Any]],
    *,
    limit: int = 24,
) -> tuple[VisualNeighbour, ...]:
    """Lay out queue/history neighbours as an organic musical neighbourhood.

    The renderer receives only display fields and a normalized relationship
    strength. Stronger relationships sit nearer the current track while a
    deterministic golden-angle layout avoids the old equal-radius spoke wheel.
    Candidates may carry an integer visual token that the UI privately maps
    back to its playback record.
    """

    current = current if isinstance(current, Mapping) else {}
    current_artist = _key(current.get("artist"))
    current_album = _key(current.get("album"))
    current_key = _identity(current)
    clean: list[tuple[int, dict[str, str], str, float]] = []
    seen = {current_key} if current_key else set()

    relation_strength = {
        "Same album": 0.96,
        "Same artist": 0.88,
        "Up next": 0.76,
        "Played earlier": 0.66,
        "Recently heard": 0.54,
    }

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
        same_album = bool(current_album and _key(album) == current_album)
        same_artist = bool(current_artist and _key(artist) == current_artist)
        explicit = _text(raw.get("_visual_relation"))

        if explicit in {"Up next", "Played earlier"}:
            relation = explicit
        elif same_album:
            relation = "Same album"
        elif same_artist:
            relation = "Same artist"
        else:
            relation = "Recently heard"

        strength = relation_strength[relation]
        if same_album:
            strength = max(strength, relation_strength["Same album"])
        elif same_artist:
            strength = max(strength, relation_strength["Same artist"])

        seed = int.from_bytes(_digest(key)[:4], "big")
        variation = ((seed % 1001) / 1000.0 - 0.5) * 0.06
        strength = max(0.40, min(0.99, strength + variation))
        item = {"artist": artist, "title": title, "album": album}
        clean.append((token, item, relation, strength))

    clean = clean[: max(0, min(24, int(limit)))]
    if not clean:
        return ()

    phase = int.from_bytes(_digest(current_key or "melodex")[:4], "big") / 2**32 * math.tau
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    result: list[VisualNeighbour] = []
    for index, (token, track, relation, strength) in enumerate(clean):
        seed = int.from_bytes(_digest("\x1f".join((track["artist"], track["title"])))[:4], "big")
        jitter = (seed % 1000) / 1000.0
        angle = phase + index * golden_angle + (jitter - 0.5) * 0.68

        radius = 0.15 + (1.0 - strength) * 0.48 + 0.035 * jitter
        x = 0.5 + math.cos(angle) * radius
        y = 0.5 + math.sin(angle) * radius * 0.72

        result.append(
            VisualNeighbour(
                token=token,
                artist=track["artist"],
                title=track["title"],
                album=track["album"],
                relation=relation,
                x=max(0.07, min(0.93, x)),
                y=max(0.09, min(0.91, y)),
                strength=strength,
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
class MemoryMark:
    label: str
    detail: str
    count: int
    hue: int
    x: float
    y: float
    span: float = 0.0
    time_label: str = ""
    representative: str = ""
    daypart: str = ""


def _average_clock_hour(group: list[tuple[float, Mapping[str, Any]]]) -> float:
    """Circular mean of local listening time so 23:55 + 00:05 stays near midnight."""

    if not group:
        return 12.0
    sin_total = 0.0
    cos_total = 0.0
    for stamp, _track in group:
        moment = datetime.fromtimestamp(stamp)
        hour = moment.hour + moment.minute / 60.0 + moment.second / 3600.0
        angle = math.tau * hour / 24.0
        sin_total += math.sin(angle)
        cos_total += math.cos(angle)
    if abs(sin_total) < 1e-9 and abs(cos_total) < 1e-9:
        return 12.0
    angle = math.atan2(sin_total, cos_total) % math.tau
    return 24.0 * angle / math.tau


def _daypart(hour: float) -> str:
    hour = float(hour) % 24.0
    if hour < 5:
        return "Late night"
    if hour < 12:
        return "Morning"
    if hour < 17:
        return "Afternoon"
    if hour < 22:
        return "Evening"
    return "Late night"


def build_visual_memory(
    tracks: Iterable[Mapping[str, Any]],
    granularity: str = "sessions",
    *,
    limit: int = 128,
) -> tuple[MemoryMark, ...]:
    """Aggregate local play records into a readable listening map.

    Horizontal position is chronological time. Vertical position is the
    circular-average time of day for the group. Size remains play count.
    Nothing is placed on an arbitrary random Y coordinate.
    """

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
    span_seconds = max(1.0, last_stamp - first_stamp)
    result: list[MemoryMark] = []
    for group in groups:
        start = group[0][0]
        finish = group[-1][0]
        midpoint = (start + finish) * 0.5
        first = group[0][1]
        album = _text(first.get("album"))
        artist = _text(first.get("artist"))
        title = _text(first.get("title"))
        average_hour = _average_clock_hour(group)
        daypart = _daypart(average_hour)

        if mode == "albums":
            label = album or title or "Untitled album"
            detail = artist or "Unknown artist"
        elif mode == "years":
            label = datetime.fromtimestamp(start).strftime("%Y")
            detail = f"{len(group)} plays"
        elif mode == "weeks":
            iso = datetime.fromtimestamp(start).isocalendar()
            label = f"Week {iso.week}"
            detail = f"{len(group)} plays · {iso.year}"
        else:
            label = datetime.fromtimestamp(start).strftime("%a %H:%M")
            artists = list(dict.fromkeys(
                _text(row.get("artist"))
                for _, row in group
                if _text(row.get("artist"))
            ))
            detail = ", ".join(artists[:2]) or f"{len(group)} tracks"

        representative = title
        if artist and title:
            representative = f"{title} · {artist}"
        elif artist and not representative:
            representative = artist

        start_dt = datetime.fromtimestamp(start)
        finish_dt = datetime.fromtimestamp(finish)
        if start_dt.date() == finish_dt.date():
            if finish - start < 60:
                time_label = start_dt.strftime("%a %b %d · %H:%M")
            else:
                time_label = f"{start_dt.strftime('%a %b %d · %H:%M')}–{finish_dt.strftime('%H:%M')}"
        else:
            time_label = f"{start_dt.strftime('%b %d')}–{finish_dt.strftime('%b %d')}"

        identity = "\x1f".join((_key(label), _key(detail), mode))
        seed = int.from_bytes(_digest(identity), "big")
        x = (midpoint - first_stamp) / span_seconds if len(groups) > 1 else 0.5
        horizontal_span = (finish - start) / span_seconds if len(groups) > 1 else 0.0
        y = 0.14 + (average_hour / 24.0) * 0.68

        result.append(
            MemoryMark(
                label=label,
                detail=detail,
                count=len(group),
                hue=seed % 360,
                x=max(0.0, min(1.0, x)),
                y=max(0.14, min(0.82, y)),
                span=max(0.0, min(1.0, horizontal_span)),
                time_label=time_label,
                representative=representative,
                daypart=daypart,
            )
        )
    return tuple(result)

