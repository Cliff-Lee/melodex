#!/usr/bin/env python3
"""Check that the PulseAudio null-sink monitor actually received decoded PCM.

This is an audio-energy check, not a listening preference, fidelity, or
physical-speaker check. Accept only s16le stereo PCM recorded at 44100 Hz.
"""
from __future__ import annotations

import argparse
from array import array
import json
import math
from pathlib import Path
import sys


def inspect(path: Path) -> dict:
    pcm = path.read_bytes()
    if len(pcm) % 2:
        pcm = pcm[:-1]
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    length = len(samples)
    seconds = length / (44100 * 2)
    if not length:
        peak = 0
        rms = 0.0
        active = 0
    else:
        peak = max(abs(int(x)) for x in samples)
        rms = math.sqrt(sum(int(x) * int(x) for x in samples) / length)
        active = sum(abs(int(x)) >= 100 for x in samples)
    # Require at least one second of captured samples, meaningful energy,
    # and thousands of non-silent samples; silence/no sink must fail.
    passed = bool(seconds >= 1.0 and peak >= 250 and rms >= 25
                  and active >= 2000)
    return {
        "passed": passed,
        "capture_seconds": round(seconds, 2),
        "peak_pcm16": peak,
        "rms_pcm16": round(rms, 1),
        "non_silent_samples": active,
        "scope": "virtual PulseAudio sink monitor, not a physical speaker",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pcm", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = inspect(args.pcm)
    except (OSError, ValueError):
        result = {"passed": False, "scope": "virtual sink capture unavailable"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", "utf-8")
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
