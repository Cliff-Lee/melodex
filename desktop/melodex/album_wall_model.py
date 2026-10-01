from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from typing import Any


def _norm(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _identity(track: dict[str, Any]) -> tuple[str, str]:
    for key in ("local_path", "rel", "track_id"):
        value = str(track.get(key) or "").strip()
        if value:
            return key, value
    return "meta", "|".join(_norm(track.get(k)) for k in ("artist", "album", "title"))


def _album_key(track: dict[str, Any]) -> str:
    artist = _norm(track.get("album_artist") or track.get("artist") or "Unknown artist")
    album = _norm(track.get("album"))
    if not album:
        album = "single:" + _norm(track.get("title") or track.get("track_id"))
    return f"{artist}|{album}"


def _year(track: dict[str, Any]) -> int:
    for key in ("year", "date", "original_date", "originaldate"):
        match = re.search(r"(?:19|20)\d{2}", str(track.get(key) or ""))
        if match:
            return int(match.group(0))
    return 0


def _stable_xy(key: str) -> tuple[float, float]:
    digest = hashlib.sha256(key.encode("utf-8", errors="ignore")).digest()
    a = int.from_bytes(digest[:8], "big") / float(2**64 - 1)
    b = int.from_bytes(digest[8:16], "big") / float(2**64 - 1)
    return a * 1.72 - 0.86, b * 1.72 - 0.86


def _number(track: dict[str, Any], key: str, fallback: str) -> int:
    value = track.get(key)
    if value is None:
        value = track.get(fallback)
    match = re.match(r"\s*(\d+)", str(value or ""))
    return int(match.group(1)) if match else 0


def build_album_wall(
    catalog: list[dict[str, Any]],
    map_model: dict[str, Any] | None = None,
    ref_map: dict[str, dict[str, Any]] | None = None,
    *,
    max_albums: int = 1200,
) -> dict[str, Any]:
    """Build stable album-level positions from the existing Flow Music Map."""
    nodes = {
        str(node.get("ref") or ""): dict(node)
        for node in list((map_model or {}).get("nodes") or [])
        if isinstance(node, dict)
    }
    identity_nodes: dict[tuple[str, str], dict[str, Any]] = {}
    for ref, track in dict(ref_map or {}).items():
        node = nodes.get(str(ref))
        if node and isinstance(track, dict):
            identity_nodes[_identity(track)] = node

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in catalog:
        if isinstance(raw, dict):
            track = dict(raw)
            groups[_album_key(track)].append(track)

    albums: list[dict[str, Any]] = []
    for key, tracks in groups.items():
        tracks.sort(key=lambda t: (
            _number(t, "disc_number", "discnumber"),
            _number(t, "track_number", "tracknumber"),
            _norm(t.get("title")),
        ))
        first = tracks[0]
        mapped = [
            identity_nodes[_identity(track)]
            for track in tracks
            if _identity(track) in identity_nodes
        ]
        if mapped:
            sound_x = sum(float(n.get("x") or 0) for n in mapped) / len(mapped)
            sound_y = sum(float(n.get("y") or 0) for n in mapped) / len(mapped)
            familiarity = sum(float(n.get("taste") or 0) for n in mapped) / len(mapped)
            rediscovery = max(float(n.get("rediscovery") or 0) for n in mapped)
            plays = sum(int(n.get("plays") or 0) for n in mapped)
        else:
            sound_x, sound_y = _stable_xy(key)
            familiarity = rediscovery = 0.0
            plays = 0

        years = [value for value in (_year(t) for t in tracks) if value]
        genres: list[str] = []
        for track in tracks:
            raw = track.get("genre")
            values = raw if isinstance(raw, (list, tuple)) else re.split(r"[;/]", str(raw or ""))
            for value in values:
                text = str(value).strip()
                if text and text.casefold() not in {x.casefold() for x in genres}:
                    genres.append(text)

        albums.append({
            "key": key,
            "artist": str(first.get("album_artist") or first.get("artist") or "Unknown artist"),
            "title": str(first.get("album") or first.get("title") or "Unknown album"),
            "year": min(years) if years else 0,
            "genres": genres[:5],
            "track_count": len(tracks),
            "tracks": tracks,
            "representative_track": dict(first),
            "analysed_tracks": len(mapped),
            "sound_x": sound_x,
            "sound_y": sound_y,
            "fallback_x": _stable_xy(key)[0],
            "fallback_y": _stable_xy(key)[1],
            "familiarity": max(0.0, min(1.0, familiarity)),
            "rediscovery": max(0.0, min(1.0, rediscovery)),
            "plays": plays,
            "cover_path": "",
        })

    albums.sort(key=lambda a: (_norm(a["artist"]), _norm(a["title"]), a["key"]))
    max_albums = max(1, int(max_albums))
    if len(albums) > max_albums:
        ranked = sorted(albums, key=lambda a: (
            -int(a["analysed_tracks"]),
            -float(a["rediscovery"]),
            -float(a["familiarity"]),
            -int(a["plays"]),
            a["key"],
        ))
        important = ranked[: max_albums // 2]
        used = {a["key"] for a in important}
        remainder = [a for a in albums if a["key"] not in used]
        needed = max_albums - len(important)
        step = len(remainder) / max(1, needed)
        important.extend(remainder[min(len(remainder) - 1, int(i * step))] for i in range(needed))
        albums = sorted(important[:max_albums], key=lambda a: (_norm(a["artist"]), _norm(a["title"])))

    years = sorted(a["year"] for a in albums if a["year"])
    lo = years[0] if years else 0
    hi = years[-1] if years else 0
    for album in albums:
        album["familiarity_x"] = float(album["familiarity"]) * 2 - 1
        album["familiarity_y"] = float(album["sound_y"])
        album["time_x"] = (
            ((album["year"] - lo) / (hi - lo)) * 2 - 1
            if album["year"] and hi > lo else
            (0.0 if album["year"] else 1.12)
        )
        album["time_y"] = float(album["sound_y"])

    return {
        "albums": albums,
        "album_count": len(albums),
        "track_count": sum(int(a["track_count"]) for a in albums),
        "analysed_albums": sum(1 for a in albums if int(a["analysed_tracks"]) > 0),
        "analysed_tracks": sum(int(a["analysed_tracks"]) for a in albums),
        "input_tracks": len(catalog),
    }


def _target(album: dict[str, Any], lens: str) -> tuple[float, float]:
    if lens == "time":
        return float(album.get("time_x") or 0), float(album.get("time_y") or 0)
    if lens == "familiarity":
        return float(album.get("familiarity_x") or -1), float(album.get("familiarity_y") or 0)
    if int(album.get("analysed_tracks") or 0):
        return float(album.get("sound_x") or 0), float(album.get("sound_y") or 0)
    return float(album.get("fallback_x") or 0), float(album.get("fallback_y") or 0)


def layout_album_positions(
    model: dict[str, Any],
    lens: str = "sound",
    *,
    tile_width: float = 154.0,
    tile_height: float = 184.0,
    extent_x: float = 1800.0,
    extent_y: float = 1180.0,
) -> dict[str, tuple[float, float]]:
    """Pack tiles near semantic targets while preventing cover collisions."""
    albums = [dict(a) for a in list(model.get("albums") or []) if isinstance(a, dict)]
    if not albums:
        return {}

    if lens == "shelves":
        ordered = sorted(albums, key=lambda a: (_norm(a.get("artist")), _norm(a.get("title"))))
        cols = max(1, int(math.ceil(math.sqrt(len(ordered) * tile_height / tile_width))))
        rows = int(math.ceil(len(ordered) / cols))
        return {
            a["key"]: (
                (i % cols - (cols - 1) / 2) * tile_width,
                (i // cols - (rows - 1) / 2) * tile_height,
            )
            for i, a in enumerate(ordered)
        }

    cols = max(9, int(2 * extent_x / tile_width))
    rows = max(7, int(2 * extent_y / tile_height))
    occupied: set[tuple[int, int]] = set()
    positions: dict[str, tuple[float, float]] = {}
    ordered = sorted(albums, key=lambda a: (
        -int(a.get("analysed_tracks") or 0),
        -float(a.get("familiarity") or 0),
        -int(a.get("plays") or 0),
        str(a.get("key") or ""),
    ))

    def cell_for(x: float, y: float) -> tuple[int, int]:
        col = round(((max(-1.18, min(1.18, x)) + 1.18) / 2.36) * (cols - 1))
        row = round(((max(-1.18, min(1.18, y)) + 1.18) / 2.36) * (rows - 1))
        return int(col), int(row)

    def nearest_free(origin: tuple[int, int]) -> tuple[int, int]:
        if origin not in occupied:
            return origin
        ox, oy = origin
        for radius in range(1, max(cols, rows) + 1):
            candidates = []
            for x in range(max(0, ox - radius), min(cols, ox + radius + 1)):
                for y in range(max(0, oy - radius), min(rows, oy + radius + 1)):
                    if max(abs(x - ox), abs(y - oy)) == radius and (x, y) not in occupied:
                        candidates.append(((x - ox) ** 2 + (y - oy) ** 2, y, x))
            if candidates:
                _, y, x = min(candidates)
                return x, y
        return origin

    for album in ordered:
        x, y = _target(album, lens)
        col, row = nearest_free(cell_for(x, y))
        occupied.add((col, row))
        px = (col / max(1, cols - 1) * 2 - 1) * extent_x
        py = (row / max(1, rows - 1) * 2 - 1) * extent_y
        positions[str(album.get("key") or "")] = (px, py)

    return positions


__all__ = ["build_album_wall", "layout_album_positions"]
