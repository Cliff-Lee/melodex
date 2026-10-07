"""Small, discovery-order-preserving first-play choices."""

from __future__ import annotations

import random
from typing import Any


def _identity(track: dict[str, Any], field: str) -> str:
    value = str(track.get(field) or "").strip().casefold()
    return "" if value in {"unknown", "unknown artist", "unknown album"} else value


def light_shuffle(
    tracks: list[dict[str, Any]],
    *,
    rng: Any = random,
    window_size: int = 5,
    recent_context: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Shuffle locally, spacing artists and adjacent albums when possible.

    Each choice comes from a short lookahead window, so early breadth-first
    discoveries stay near the front instead of being displaced by a global
    filesystem-wide random ordering. ``recent_context`` lets streamed batches
    continue the same spacing from the current queue tail.
    """
    remaining = [dict(row) for row in tracks if isinstance(row, dict)]
    output: list[dict[str, Any]] = []
    context = [dict(row) for row in (recent_context or []) if isinstance(row, dict)]
    previous_album = _identity(context[-1], "album") if context else ""
    recent_artists = [
        artist
        for artist in (_identity(row, "artist") for row in context[-2:])
        if artist
    ]
    width = max(1, int(window_size))
    while remaining:
        candidates = list(range(min(width, len(remaining))))
        # A cold-start queue should reveal breadth early. Prefer tracks that
        # change artist and album within the bounded lookahead, but never let
        # incomplete tags empty the candidate set or delay the first play.
        def repeat_cost(index: int) -> int:
            track = remaining[index]
            artist = _identity(track, "artist")
            album = _identity(track, "album")
            cost = 0
            if artist and artist in recent_artists:
                cost += 2
            if previous_album and album and album == previous_album:
                cost += 1
            return cost

        best_cost = min(repeat_cost(index) for index in candidates)
        candidates = [index for index in candidates if repeat_cost(index) == best_cost]
        selected = rng.choice(candidates)
        row = remaining.pop(selected)
        output.append(row)
        previous_album = _identity(row, "album")
        artist = _identity(row, "artist")
        if artist:
            recent_artists.append(artist)
            recent_artists = recent_artists[-2:]
    return output


__all__ = ["light_shuffle"]
