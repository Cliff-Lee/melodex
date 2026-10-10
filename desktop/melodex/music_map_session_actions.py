from __future__ import annotations

"""Music Map listening actions extracted from MainWindow.

These functions retain the established Mind + Flow scheduling, catalogue
filtering and status messaging. MainWindow keeps only the connected signal
entry points; its inherited line-count guardrail is not weakened.
"""

from typing import Any

from .music_map_region import local_tracks_for_region


def start_session_from_map_region(host: Any, request: object) -> None:
    """Play within a mapped region using the existing local Mind engine."""
    payload = dict(request) if isinstance(request, dict) else {}
    mapped = [
        dict(row) for row in list(payload.get("tracks") or [])[:700]
        if isinstance(row, dict)
    ]
    if not mapped:
        host.statusBar().showMessage(
            "This region has no available mapped tracks.", 5000
        )
        return
    catalog = host.providers.local_catalog()
    pool = local_tracks_for_region(
        mapped, catalog, host.mind.track_key, max_tracks=200
    )
    if not pool:
        host.statusBar().showMessage(
            "No locally playable tracks from this region are available. "
            "Try another region or refresh your library.",
            6000,
        )
        return
    seed = dict(payload.get("seed") or {})
    seed_key = host.mind.track_key(seed) if seed else ""
    matched_seed = next(
        (track for track in pool if host.mind.track_key(track) == seed_key),
        pool[0],
    )
    host.statusBar().showMessage(
        f"Building a listening session from {len(pool)} tracks in this region…"
    )
    host._run_async(
        lambda: host.mind.build_session(
            pool,
            host._path_for,
            minutes=int(host.minutes.currentText()),
            adventure=host.adventure.value() / 100,
            mode=str(host.mode.currentData() or "balanced"),
            start_track=matched_seed,
        ),
        host._apply_mind,
        priority="foreground",
        task_name="map-region-session",
        replace_key="journey-build",
    )


def start_session_from_map_track(host: Any, track: object) -> None:
    seed = dict(track or {}) if isinstance(track, dict) else {}
    if not seed:
        return
    catalog = host.providers.local_catalog()
    if not catalog:
        host.statusBar().showMessage(
            "No local tracks available for a listening session. Add a music source and try again.",
            6000,
        )
        return
    host.statusBar().showMessage("Building a listening session from this track…")
    host._run_async(
        lambda: host.mind.build_session(
            catalog,
            host._path_for,
            minutes=int(host.minutes.currentText()),
            adventure=host.adventure.value() / 100,
            mode=str(host.mode.currentData() or "balanced"),
            start_track=seed,
        ),
        lambda plan: host._apply_mind(plan),
        priority="foreground",
        task_name="journey-build",
        replace_key="journey-build",
    )


__all__ = ["start_session_from_map_region", "start_session_from_map_track"]
