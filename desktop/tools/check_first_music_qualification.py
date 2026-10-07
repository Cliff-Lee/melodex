#!/usr/bin/env python3
"""Check a redacted Melodex diagnostics export against a P13 journey gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


LIMITS: dict[str, dict[str, float]] = {
    "local": {
        "process_to_shell_ms": 1000.0,
        "source_selected_to_first_track_visible_ms": 500.0,
        "source_selected_to_first_playable_track_ms": 1000.0,
        "play_requested_to_audio_output_ms": 500.0,
    },
    "nas": {
        "process_to_shell_ms": 1000.0,
        "source_selected_to_first_directory_ms": 1000.0,
        "source_selected_to_first_track_visible_ms": 2000.0,
        "source_selected_to_first_playable_track_ms": 3000.0,
        "play_requested_to_audio_output_ms": 1000.0,
    },
    "warm": {
        "process_to_shell_ms": 1000.0,
        "process_to_cached_library_ms": 1000.0,
    },
    "offline": {
        "process_to_shell_ms": 1000.0,
        "process_to_cached_library_ms": 1000.0,
    },
}


def _attempt_ids(
    first_music: dict[str, Any],
    journeys: dict[str, Any],
    *,
    source_id: int | None,
    play_id: int | None,
) -> tuple[int | None, int | None]:
    events = [row for row in first_music.get("events", []) if isinstance(row, dict)]
    selected_source_id = source_id
    selected_play_id = play_id
    if play_id is not None:
        matching_play_events = [
            event
            for event in events
            if event.get("event") == "play_requested"
            and event.get("play_id") == play_id
        ]
        if not matching_play_events:
            return selected_source_id if selected_source_id is not None else -1, -1
        play_source_id = matching_play_events[-1].get("source_id")
        if selected_source_id is None:
            selected_source_id = play_source_id
        elif play_source_id != selected_source_id:
            return selected_source_id, -1
    elif selected_source_id is None:
        sources = [row for row in journeys.get("sources", []) if isinstance(row, dict)]
        if sources:
            selected_source_id = sources[-1].get("source_id")

    if selected_play_id is None and selected_source_id is not None:
        matching_play_ids = [
            event.get("play_id")
            for event in events
            if event.get("event") == "play_requested"
            and event.get("source_id") == selected_source_id
            and event.get("play_id") is not None
        ]
        selected_play_id = matching_play_ids[-1] if matching_play_ids else None
    return selected_source_id, selected_play_id


def _find_timing(
    first_music: dict[str, Any],
    journey: str,
    *,
    source_id: int | None,
    play_id: int | None,
) -> dict[str, float | None]:
    journeys = dict(first_music.get("journeys") or {})
    result: dict[str, float | None] = {}
    for name in ("process_to_shell_ms", "process_to_cached_library_ms"):
        if name in LIMITS[journey]:
            value = journeys.get(name)
            result[name] = None if value is None else float(value)

    sources = [row for row in journeys.get("sources", []) if isinstance(row, dict)]
    plays = [row for row in journeys.get("plays", []) if isinstance(row, dict)]
    if source_id is not None:
        sources = [row for row in sources if row.get("source_id") == source_id]
    source = sources[-1] if sources else {}
    if play_id is not None:
        plays = [row for row in plays if row.get("play_id") == play_id]
    elif source_id is not None:
        source_play_ids = {
            event.get("play_id")
            for event in list(first_music.get("events") or [])
            if isinstance(event, dict)
            and event.get("event") == "play_requested"
            and event.get("source_id") == source_id
            and event.get("play_id") is not None
        }
        plays = [row for row in plays if row.get("play_id") in source_play_ids]
    play = plays[-1] if plays else {}
    for name in LIMITS[journey]:
        if name.startswith("source_selected_to_"):
            value = source.get(name)
            result[name] = None if value is None else float(value)
        elif name == "play_requested_to_audio_output_ms":
            value = play.get(name)
            result[name] = None if value is None else float(value)
    return result


def qualify(
    payload: dict[str, Any],
    journey: str,
    *,
    source_id: int | None = None,
    play_id: int | None = None,
) -> dict[str, Any]:
    performance = dict(payload.get("performance") or {})
    first_music = dict(performance.get("first_music") or {})
    journeys = dict(first_music.get("journeys") or {})
    effective_source_id, effective_play_id = _attempt_ids(
        first_music,
        journeys,
        source_id=source_id,
        play_id=play_id,
    )
    timings = _find_timing(
        first_music,
        journey,
        source_id=effective_source_id,
        play_id=effective_play_id,
    )
    limits = dict(LIMITS[journey])
    violations = []
    for metric, limit in limits.items():
        value = timings.get(metric)
        if value is None:
            violations.append(f"missing measurement: {metric}")
        elif float(value) >= limit:
            violations.append(f"{metric} {float(value):.1f} ms >= {limit:.1f} ms")
    return {
        "journey": journey,
        "source_id": None if effective_source_id == -1 else effective_source_id,
        "play_id": None if effective_play_id == -1 else effective_play_id,
        "measurements_ms": timings,
        "limits_ms": limits,
        "audio_output_measurement": str(
            first_music.get("audio_output_measurement") or "not specified"
        ),
        "violations": violations,
        "passed": not violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate an Export redacted diagnostics JSON file against one P13 "
            "first-music journey."
        )
    )
    parser.add_argument("diagnostics", type=Path)
    parser.add_argument("--journey", choices=tuple(LIMITS), required=True)
    parser.add_argument("--source-id", type=int)
    parser.add_argument("--play-id", type=int)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.diagnostics.read_text("utf-8"))
    result = qualify(
        payload,
        args.journey,
        source_id=args.source_id,
        play_id=args.play_id,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.enforce and not result["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
