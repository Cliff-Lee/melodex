from __future__ import annotations

import re
from typing import Any


def _tag_number(track: dict[str, Any], primary: str, fallback: str) -> tuple[int | None, bool]:
    """Read a leading positive number from common MusicBrainz-style tag values."""
    value = track.get(primary)
    if value in (None, ""):
        value = track.get(fallback)
    if value in (None, ""):
        return None, False
    if isinstance(value, bool):
        return None, True
    match = re.match(r"\s*(\d+)", str(value))
    if not match:
        return None, True
    number = int(match.group(1))
    return (number, False) if number > 0 else (None, True)


def album_track_order_key(track: dict[str, Any]) -> tuple[Any, ...]:
    """Stable disc/track ordering that tolerates incomplete and malformed tags."""
    disc, _bad_disc = _tag_number(track, "disc_number", "discnumber")
    number, _bad_number = _tag_number(track, "track_number", "tracknumber")
    title = " ".join(str(track.get("title") or "").casefold().split())
    identity = next(
        (
            str(track.get(key) or "").casefold()
            for key in ("local_path", "rel", "track_id")
            if str(track.get(key) or "").strip()
        ),
        title,
    )
    return (
        disc if disc is not None else 1,
        0 if number is not None else 1,
        number if number is not None else 0,
        title,
        identity,
    )


def album_order_diagnostics(tracks: list[dict[str, Any]]) -> dict[str, int | bool]:
    """Summarize order quality using structural counts only."""
    rows = [track for track in tracks if isinstance(track, dict)]
    parsed: list[tuple[int, int | None, bool, bool, bool]] = []
    for track in rows:
        disc_value = track.get("disc_number")
        if disc_value in (None, ""):
            disc_value = track.get("discnumber")
        number_value = track.get("track_number")
        if number_value in (None, ""):
            number_value = track.get("tracknumber")
        disc, bad_disc = _tag_number({"value": disc_value}, "value", "value")
        number, bad_number = _tag_number({"value": number_value}, "value", "value")
        parsed.append(
            (
                disc if disc is not None else 1,
                number,
                disc is not None,
                bad_disc,
                bad_number,
            )
        )

    positions = [
        (disc, number)
        for disc, number, _has_disc, _bad_disc, _bad_number in parsed
        if number is not None
    ]
    duplicate_positions = len(positions) - len(set(positions))
    tags_usable = bool(rows) and all(
        number is not None and not bad_disc and not bad_number
        for _disc, number, _has_disc, bad_disc, bad_number in parsed
    )
    ordered_keys = [album_track_order_key(track) for track in rows]
    ordering_valid = (
        tags_usable
        and duplicate_positions == 0
        and ordered_keys == sorted(ordered_keys)
    )
    return {
        "track_count": len(rows),
        "disc_numbered_tracks": sum(1 for _d, _n, has_disc, _bd, _bn in parsed if has_disc),
        "track_numbered_tracks": sum(1 for _d, n, _hd, _bd, _bn in parsed if n is not None),
        "malformed_disc_numbers": sum(1 for _d, _n, _hd, bad, _bn in parsed if bad),
        "malformed_track_numbers": sum(1 for _d, _n, _hd, _bd, bad in parsed if bad),
        "duplicate_positions": duplicate_positions,
        "ordering_valid": bool(ordering_valid),
    }
