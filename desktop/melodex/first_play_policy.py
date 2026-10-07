"""Small, discovery-order-preserving first-play choices."""

from __future__ import annotations

import random
from typing import Any


def light_shuffle(
    tracks: list[dict[str, Any]],
    *,
    rng: Any = random,
    window_size: int = 5,
) -> list[dict[str, Any]]:
    """Shuffle locally within discovery order and avoid adjacent albums.

    Each choice comes from a short lookahead window, so early breadth-first
    discoveries stay near the front instead of being displaced by a global
    filesystem-wide random ordering.
    """
    remaining = [dict(row) for row in tracks if isinstance(row, dict)]
    output: list[dict[str, Any]] = []
    previous_album = ""
    width = max(1, int(window_size))
    while remaining:
        candidates = list(range(min(width, len(remaining))))
        if previous_album:
            different_album = [
                index
                for index in candidates
                if str(remaining[index].get("album") or "").strip().casefold()
                != previous_album
            ]
            if different_album:
                candidates = different_album
        selected = rng.choice(candidates)
        row = remaining.pop(selected)
        output.append(row)
        previous_album = str(row.get("album") or "").strip().casefold()
    return output


__all__ = ["light_shuffle"]
