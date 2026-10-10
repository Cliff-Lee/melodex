from __future__ import annotations

"""Match mapped Music Map regions to the canonical local playback catalogue.

This is a membership filter, not an alternative recommendation engine.
Session ordering remains the responsibility of the existing Mind engine.
"""

from collections.abc import Callable, Iterable, Mapping
from typing import Any


def local_tracks_for_region(
    mapped: Iterable[Mapping[str, Any]],
    catalog: Iterable[Mapping[str, Any]],
    track_key: Callable[[dict[str, Any]], str],
    *,
    max_tracks: int = 200,
) -> list[dict[str, Any]]:
    """Return locally playable catalogue rows matching the mapped region.

    Only exact nonempty identity keys are used: never infer region membership
    from artist or album labels. Output follows catalogue order and is bounded.
    """
    keys: set[str] = set()
    for row in mapped:
        if not isinstance(row, Mapping):
            continue
        try:
            key = str(track_key(dict(row)) or "")
        except (ValueError, TypeError, KeyError):
            continue
        if key:
            keys.add(key)
    if not keys:
        return []

    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()
    cap = max(1, int(max_tracks))
    for row in catalog:
        if not isinstance(row, Mapping):
            continue
        track = dict(row)
        if not (track.get("local_path") or (track.get("track_id") and track.get("rel"))):
            continue
        try:
            key = str(track_key(track) or "")
        except (ValueError, TypeError, KeyError):
            continue
        if key and key in keys and key not in seen:
            chosen.append(track)
            seen.add(key)
        if len(chosen) >= cap:
            break
    return chosen


__all__ = ["local_tracks_for_region"]
