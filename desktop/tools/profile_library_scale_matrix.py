#!/usr/bin/env python3
"""P10a multi-scale baseline for Melodex library scanning.

This deliberately measures the *current* scanner before P10 changes its
architecture.  It reuses the synthetic scanner probe, adds retained/peak Python
memory measurements, and runs the same workload at several library sizes.

The default profile is safe for ordinary developer/CI machines.  The expensive
250k/500k/1m stress sizes are opt-in with --release-scale so a normal pull
request cannot accidentally allocate a million-track snapshot.
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import tracemalloc
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.profile_library_scan import run_probe

DEFAULT_PROFILES = (500, 5_000, 12_700, 50_000, 100_000)
RELEASE_PROFILES = (250_000, 500_000, 1_000_000)

SCALE_CONTRACT = {
    "interaction_ack_p95_ms": 100,
    "small_library_max_regression_pct": 10,
    "normal_pr_profiles": list(DEFAULT_PROFILES[:3]),
    "extended_profiles": list(DEFAULT_PROFILES[3:]),
    "release_profiles": list(RELEASE_PROFILES),
    "rules": [
        "small libraries must not materially regress",
        "scan work must not block playback or UI interaction",
        "queues and worker counts must stay bounded",
        "unchanged files must not reread metadata",
        "million-file scale must not require million UI objects",
        "optional artwork and analysis must not block the core index",
    ],
}


def parse_profiles(raw: str) -> tuple[int, ...]:
    values = []
    for part in str(raw or "").split(","):
        part = part.strip().replace("_", "")
        if not part:
            continue
        value = int(part)
        if value < 0:
            raise ValueError("profile sizes must be non-negative")
        values.append(value)
    if not values:
        raise ValueError("at least one profile size is required")
    return tuple(values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure Melodex library-scan scaling across multiple sizes."
    )
    parser.add_argument(
        "--profiles",
        default=",".join(str(value) for value in DEFAULT_PROFILES),
        help="Comma-separated track counts.",
    )
    parser.add_argument(
        "--release-scale",
        action="store_true",
        help="Append the opt-in 250k/500k/1m release stress sizes.",
    )
    parser.add_argument("--tracks-per-directory", type=int, default=25)
    parser.add_argument("--metadata-delay-ms", type=float, default=0.0)
    parser.add_argument("--directory-delay-ms", type=float, default=0.0)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def run_profile(
    track_count: int,
    *,
    tracks_per_directory: int,
    metadata_delay_ms: float,
    directory_delay_ms: float,
) -> dict[str, object]:
    args = SimpleNamespace(
        tracks=max(0, int(track_count)),
        tracks_per_directory=max(1, int(tracks_per_directory)),
        metadata_delay_ms=max(0.0, float(metadata_delay_ms)),
        directory_delay_ms=max(0.0, float(directory_delay_ms)),
        non_audio_per_directory=1,
        json=True,
    )

    gc.collect()
    tracemalloc.start()
    metrics = dict(run_probe(args))
    retained, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    total_seconds = float(metrics.get("total_seconds") or 0.0)
    tracks_indexed = int(metrics.get("tracks_indexed") or 0)
    tracks_per_second = (
        tracks_indexed / total_seconds if total_seconds > 0 else 0.0
    )
    return {
        "tracks": int(track_count),
        "tracks_indexed": tracks_indexed,
        "total_seconds": round(total_seconds, 6),
        "metadata_seconds": round(float(metrics.get("metadata_seconds") or 0.0), 6),
        "tracks_per_second": round(tracks_per_second, 2),
        "python_retained_mib": round(retained / (1024 * 1024), 3),
        "python_peak_mib": round(peak / (1024 * 1024), 3),
        "directories_seen": int(metrics.get("directories_seen") or 0),
        "files_seen": int(metrics.get("files_seen") or 0),
        "metadata_reads": int(metrics.get("metadata_attempts") or 0),
        "stat_failures": int(metrics.get("stat_failures") or 0),
    }


def run_matrix(args: argparse.Namespace) -> dict[str, object]:
    profiles = list(parse_profiles(args.profiles))
    if args.release_scale:
        for value in RELEASE_PROFILES:
            if value not in profiles:
                profiles.append(value)

    rows = [
        run_profile(
            track_count,
            tracks_per_directory=args.tracks_per_directory,
            metadata_delay_ms=args.metadata_delay_ms,
            directory_delay_ms=args.directory_delay_ms,
        )
        for track_count in profiles
    ]
    return {
        "campaign": "P10a",
        "purpose": "pre-optimization elastic-library scaling baseline",
        "contract": SCALE_CONTRACT,
        "profiles": rows,
    }


def main() -> int:
    args = parse_args()
    payload = run_matrix(args)

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print("Melodex P10a elastic-library baseline")
    print("------------------------------------")
    print(
        "Tracks       Total(s)   Tracks/s   Peak Python MiB   Metadata reads"
    )
    for row in payload["profiles"]:
        print(
            f"{int(row['tracks']):>10,}   "
            f"{float(row['total_seconds']):>8.3f}   "
            f"{float(row['tracks_per_second']):>8.1f}   "
            f"{float(row['python_peak_mib']):>15.2f}   "
            f"{int(row['metadata_reads']):>14,}"
        )
    print()
    print(
        "Release-scale 250k/500k/1m profiles are opt-in with --release-scale."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
