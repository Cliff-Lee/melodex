#!/usr/bin/env python3
"""Qualify first-session outcomes without confusing simulations with audio evidence.

The report combines synthetic first-five queue quality, pure queue-handoff
stability, and optional scanner timing. Real TTFA requires a redacted desktop
diagnostics export and remains explicitly unmeasured without one.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
for directory in (ROOT, TOOLS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from melodex.first_play_policy import light_shuffle
from melodex.session_handoff import refined_upcoming, track_key
from qualify_first_session_quality import _known, quality_profiles


def qualify_queue_journeys(*, seeds: int = 32) -> dict[str, Any]:
    """Measure first-five breadth and prove late plans respect listener edits."""
    profiles = quality_profiles()
    selected = {
        "fresh_local": "small_mixed",
        "partial_nas": "broad_interleaved",
        "returning_cache": "artist_clustered",
    }
    journeys: list[dict[str, Any]] = []
    for journey, profile in selected.items():
        tracks = profiles[profile]
        artist_counts: list[int] = []
        album_counts: list[int] = []
        retained_all = True
        for seed in range(max(1, int(seeds))):
            queue = light_shuffle(tracks, rng=random.Random(seed))
            retained_all &= sorted(map(track_key, queue)) == sorted(map(track_key, tracks))
            first_five = queue[:5]
            artist_counts.append(len({
                identity for track in first_five
                if (identity := _known(track.get("artist"), {"unknown", "unknown artist"}))
            }))
            album_counts.append(len({
                identity for track in first_five
                if (identity := _known(track.get("album"), {"unknown", "unknown album"}))
            }))

        quick_queue = light_shuffle(tracks[: min(10, len(tracks))], rng=random.Random(0))
        snapshot = tuple(map(track_key, quick_queue))
        refined = refined_upcoming(
            quick_queue, 0, tracks, snapshot
        )
        edited_queue = [*quick_queue, {"track_id": "listener-added-track"}]
        edited = refined_upcoming(edited_queue, 0, tracks, snapshot)
        stability = bool(refined is not None and edited is None)
        journeys.append({
            "journey": journey,
            "synthetic_profile": profile,
            "pool_tracks": len(tracks),
            "first_five_known_artists_median": statistics.median(artist_counts),
            "first_five_known_albums_median": statistics.median(album_counts),
            "all_candidates_preserved": retained_all,
            "late_plan_respects_queue_edits": stability,
            "time_to_first_choice_ms": None,
            "time_to_queue_ms": None,
            "time_to_audio_ms": None,
            "timing_note": "Requires desktop diagnostics; pure policy timing is not user latency.",
        })
    return {"seeds": max(1, int(seeds)), "journeys": journeys}


def qualify_diagnostics(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Retain measured diagnostics separately; never synthesize missing TTFA."""
    if payload is None:
        return {
            "available": False,
            "time_to_first_choice_ms": None,
            "time_to_queue_ms": None,
            "time_to_audio_ms": None,
            "note": "No desktop diagnostics export supplied; audio latency is unmeasured.",
        }
    performance = dict(payload.get("performance") or {})
    first_music = dict(performance.get("first_music") or {})
    if not first_music:
        return {
            "available": False,
            "time_to_first_choice_ms": None,
            "time_to_queue_ms": None,
            "time_to_audio_ms": None,
            "note": "The export contains no first-music diagnostics; timings are unmeasured.",
        }
    journeys = dict(first_music.get("journeys") or {})
    sources = [row for row in journeys.get("sources", []) if isinstance(row, dict)]
    plays = [row for row in journeys.get("plays", []) if isinstance(row, dict)]
    source = sources[-1] if sources else {}
    play = plays[-1] if plays else {}
    return {
        "available": True,
        "time_to_first_choice_ms": source.get("source_selected_to_first_track_visible_ms"),
        "time_to_queue_ms": source.get("source_selected_to_first_queue_ready_ms"),
        "time_to_first_playable_ms": source.get("source_selected_to_first_playable_track_ms"),
        "time_to_audio_ms": play.get("play_requested_to_audio_output_ms"),
        "audio_output_measurement": first_music.get("audio_output_measurement"),
        "source_id": source.get("source_id"),
        "play_id": play.get("play_id"),
    }


def build_report(*, seeds: int = 32, diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    queue_report = qualify_queue_journeys(seeds=seeds)
    audio_report = qualify_diagnostics(diagnostics)
    passed = all(
        row["all_candidates_preserved"] and row["late_plan_respects_queue_edits"]
        for row in queue_report["journeys"]
    )
    return {
        "campaign": "P14f",
        "scope": "synthetic first-session queue journeys plus optional real desktop diagnostics",
        "passed": passed,
        "journey_qualification_passed": passed,
        "real_audio_qualification": "measured" if audio_report["available"] and audio_report["time_to_audio_ms"] is not None else "pending",
        "queue_quality": queue_report,
        "desktop_diagnostics": audio_report,
        "interpretation": (
            "Queue quality and handoff stability are synthetic checks. Scanner discovery, "
            "visible UI, decoder, and audio timings are separate; this report does not "
            "claim TTFA without a desktop diagnostics export."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=32)
    parser.add_argument("--diagnostics", type=Path, help="redacted Melodex diagnostics JSON export")
    parser.add_argument("--json", action="store_true", help="accepted for consistency; output is always JSON")
    args = parser.parse_args()
    payload = json.loads(args.diagnostics.read_text("utf-8")) if args.diagnostics else None
    report = build_report(seeds=args.seeds, diagnostics=payload)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
