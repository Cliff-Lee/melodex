#!/usr/bin/env python3
"""P13o scanner journey matrix for time-to-first-music qualification.

This runs the real local discovery code over a synthetic filesystem. It reports
first directory/audio discovery separately from full catalog completion. It
does not start Qt, a decoder, or an audio device; use the application's
first-music diagnostics export for TTFA evidence and qualify_nas_faults.py for
isolated-worker NAS fault scenarios.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from qualify_first_music_discovery import run_case


def _ints(raw: str) -> list[int]:
    return [max(0, int(part.strip())) for part in str(raw).split(",") if part.strip()]


def _floats(raw: str) -> list[float]:
    return [max(0.0, float(part.strip())) for part in str(raw).split(",") if part.strip()]


def _scanner_row(**kwargs: Any) -> dict[str, Any]:
    row = run_case(**kwargs)
    # The scanner-only harness can report when the persistent catalog commits.
    # It cannot prove that the UI/player can play before that point.
    row["source_selected_to_catalog_commit_ms"] = row.pop(
        "source_selected_to_first_playable_track_ms"
    )
    return row


def run_matrix(
    profiles: list[int],
    *,
    latency_tracks: int,
    latencies_ms: list[float],
) -> dict[str, Any]:
    local = [_scanner_row(track_count=count) for count in profiles]
    latency = [
        _scanner_row(
            track_count=max(1, int(latency_tracks)),
            stat_delay_ms=delay,
            directory_delay_ms=delay,
        )
        for delay in latencies_ms
    ]
    return {
        "campaign": "P13o",
        "measurement_scope": (
            "scanner discovery and full scan only; no Qt, decoder, audio device, "
            "or hardware loopback"
        ),
        "ttfa_measured": False,
        "local_profiles": local,
        "nas_latency_profiles": latency,
        "fault_scenarios": "Run desktop/tools/qualify_nas_faults.py separately.",
        "playback_evidence": (
            "Use Melodex diagnostics export for play_requested_to_audio_output_ms; "
            "that metric ends at first playback-position advance, not hardware loopback."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", default="10,1000,12700,100000")
    parser.add_argument(
        "--latency-tracks",
        type=int,
        default=10,
        help="Small synthetic collection used for the per-operation latency sweep.",
    )
    parser.add_argument("--latencies-ms", default="1,5,20,50,200")
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Fail if synthetic local first-audio discovery exceeds its CI limit.",
    )
    parser.add_argument("--first-audio-limit-ms", type=float, default=1000.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_matrix(
        _ints(args.profiles),
        latency_tracks=max(1, args.latency_tracks),
        latencies_ms=_floats(args.latencies_ms),
    )
    limit_ms = max(0.0, float(args.first_audio_limit_ms))
    failed = [
        row
        for row in result["local_profiles"]
        if row["source_selected_to_first_audio_file_ms"] is None
        or float(row["source_selected_to_first_audio_file_ms"]) > limit_ms
    ]
    result["scanner_gate"] = {
        "enforced": bool(args.enforce),
        "first_audio_limit_ms": limit_ms,
        "passed": not failed,
        "scope": "synthetic first audio filename discovery; not playback readiness or TTFA",
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("P13o time-to-first-music scanner matrix")
        for row in result["local_profiles"]:
            print(
                f"local {row['tracks_requested']:>7,} tracks | "
                f"first directory {row['source_selected_to_first_directory_ms']} ms | "
                f"first audio {row['source_selected_to_first_audio_file_ms']} ms | "
                f"catalog commit {row['source_selected_to_catalog_commit_ms']} ms | "
                f"full scan {row['source_selected_to_full_scan_ms']} ms"
            )
        for row in result["nas_latency_profiles"]:
            print(
                f"NAS {row['stat_delay_ms']:>5g} ms/op | "
                f"first audio {row['source_selected_to_first_audio_file_ms']} ms | "
                f"full scan {row['source_selected_to_full_scan_ms']} ms"
            )
        print("TTFA is not measured by this scanner-only matrix.")
    return 1 if args.enforce and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
