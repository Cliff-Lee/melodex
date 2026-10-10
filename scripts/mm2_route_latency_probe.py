#!/usr/bin/env python3
"""MM2 synthetic UI-thread snapshot latency and async Pathfinder probe.

This probe isolates the synchronous work that occurs *before* scheduling a
route preview. Route completion is recorded separately; it is background
work and must not be confused with UI click acknowledgement.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop"))

from melodex.music_map_route_snapshot import snapshot_pathfinder_inputs  # noqa: E402
from melodex.music_pathfinder import find_music_path  # noqa: E402


def build_fixture(tracks: int) -> tuple[dict, dict]:
    n = max(2, int(tracks))
    nodes = [
        {
            "ref": f"mapped-{i}",
            "route_vector": [
                round(math.sin((i + 1) * (j + 1) / 101.0), 7)
                for j in range(8)
            ],
            "x": ((i * 37) % n) / n * 2 - 1,
            "y": ((i * 53) % n) / n * 2 - 1,
            # The UI model can carry non-routing metadata. It should not be
            # copied or transported to the Pathfinder worker.
            "artist": "Benchmark library",
            "unused_art_metadata": {"details": ["album art"] * 12},
        }
        for i in range(n)
    ]
    sonic_edges = [
        {
            "a": f"mapped-{i}",
            "b": f"mapped-{(i + step) % n}",
            "similarity": 0.75,
        }
        for step in (1, 7, 13, 31)
        for i in range(n)
    ]
    knowledge_edges = [
        {
            "a": f"mapped-{i}",
            "b": f"mapped-{(i + step) % n}",
            "kind": "artist" if step % 2 else "album",
            "strength": 0.56,
            "label": "Actual local relationship",
            "evidence": "Synthetic benchmark",
        }
        for step in (1, 3, 5, 7, 11, 17, 23, 29)
        for i in range(n)
    ]
    return {"nodes": nodes, "edges": sonic_edges}, {"edges": knowledge_edges}


def measure(tracks: int, iterations: int) -> dict:
    model, knowledge = build_fixture(tracks)
    samples: list[float] = []
    snapshots = []
    for index in range(max(5, iterations) + 2):
        start = time.perf_counter()
        snapshot = snapshot_pathfinder_inputs(model, knowledge)
        elapsed = (time.perf_counter() - start) * 1000
        if index >= 2:
            samples.append(elapsed)
        snapshots.append(snapshot)
    del snapshots[:-1]
    ordered = sorted(samples)
    p95 = ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]
    routing_started = time.perf_counter()
    found = find_music_path(
        *snapshots[-1], "mapped-0", f"mapped-{max(2,tracks)-1}",
        mode="balanced", max_hops=12
    )
    routed_ms = (time.perf_counter() - routing_started) * 1000
    return {
        "mapped_tracks": max(2, tracks),
        "sonic_edges": len(model["edges"]),
        "knowledge_edges": len(knowledge["edges"]),
        "snapshot_samples": len(samples),
        "snapshot_p50_ms": round(ordered[len(ordered) // 2], 3),
        "snapshot_p95_ms": round(p95, 3),
        "snapshot_max_ms": round(max(samples), 3),
        "background_pathfinder_ms": round(routed_ms, 3),
        "route_found": bool(found.get("found")),
        "route_hops": len(found.get("hops") or []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracks", type=int, default=700)
    parser.add_argument("--iterations", type=int, default=15)
    parser.add_argument("--snapshot-p95-limit-ms", type=float, default=100.0)
    parser.add_argument("--enforce", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    metrics = measure(args.tracks, args.iterations)
    metrics["snapshot_p95_limit_ms"] = args.snapshot_p95_limit_ms
    metrics["snapshot_gate_passed"] = (
        metrics["snapshot_p95_ms"] <= args.snapshot_p95_limit_ms
    )
    payload = json.dumps(metrics, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if args.enforce and not metrics["snapshot_gate_passed"]:
        print("MM2 FAIL: route request snapshot exceeded UI budget.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
