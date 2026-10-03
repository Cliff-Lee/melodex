from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
if str(DESKTOP) not in sys.path:
    sys.path.insert(0, str(DESKTOP))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from melodex.lyrics_state import LyricFrame  # noqa: E402
from melodex.visualization_models import MemoryMark, VisualNeighbour  # noqa: E402
from melodex.visualization_profile import build_visual_profile  # noqa: E402
from melodex.visualization_scene import LivingScene  # noqa: E402


MODES = (
    "living",
    "lyrics",
    "weather",
    "album_world",
    "constellation",
    "memory",
    "journey",
    "minimal",
)


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return ordered[position]


def _configure(scene: LivingScene) -> None:
    scene.set_profile(
        build_visual_profile(
            {"artist": "Visual Probe", "title": "Representative Track", "duration": 240},
            {
                "bpm": 124,
                "energy": 0.72,
                "spectral_centroid": 1850,
                "onset_density": 0.14,
                "energy_curve": [
                    0.18, 0.28, 0.42, 0.71, 0.84, 0.62, 0.48, 0.77,
                    0.92, 0.66, 0.39, 0.55, 0.81, 0.70, 0.46, 0.30,
                ],
            },
        )
    )
    scene.set_lyrics(
        LyricFrame(
            "Previous line of the song",
            "Current lyric glowing in the centre",
            "Following line arrives next",
            True,
            "probe",
            7,
        )
    )
    neighbours = []
    for index in range(24):
        angle = index / 24.0
        neighbours.append(
            VisualNeighbour(
                index,
                f"Artist {index}",
                f"Track {index}",
                f"Album {index // 3}",
                "Same artist" if index < 4 else "Recently heard",
                0.12 + 0.76 * ((index * 7) % 23) / 22.0,
                0.14 + 0.68 * ((index * 11) % 23) / 22.0,
                0.48 + 0.48 * (1.0 - index / 24.0),
            )
        )
    scene.set_neighbours(tuple(neighbours))

    marks = []
    for index in range(96):
        marks.append(
            MemoryMark(
                f"Session {index}",
                f"Artist {index % 12}",
                1 + index % 9,
                (205 + index * 17) % 360,
                index / 95.0,
                0.14 + 0.68 * ((index * 7) % 24) / 23.0,
                0.004 + (index % 6) * 0.003,
                f"Oct {1 + index // 6:02d} · {index % 24:02d}:00",
                f"Track {index} · Artist {index % 12}",
                ("Late night", "Morning", "Afternoon", "Evening")[index % 4],
            )
        )
    scene.set_memory(tuple(marks), "sessions")


def run_probe(width: int, height: int, frames: int, quality: str) -> dict[str, object]:
    app = QApplication.instance() or QApplication([])
    scene = LivingScene()
    scene.resize(max(320, int(width)), max(240, int(height)))
    scene.set_quality(quality)
    _configure(scene)

    image = QImage(scene.size(), QImage.Format_ARGB32)
    image.fill(QColor("#000000"))

    results: dict[str, object] = {}
    for mode in MODES:
        scene.set_mode(mode)
        timings: list[float] = []

        # Warm caches / text layout before measuring.
        for _ in range(3):
            scene.render(image)

        for index in range(max(5, int(frames))):
            scene._phase = (scene._phase + 0.19) % 6.283185307179586
            scene.set_position_fraction((index % max(1, frames)) / max(1, frames - 1))
            started = time.perf_counter()
            scene.render(image)
            timings.append((time.perf_counter() - started) * 1000.0)

        results[mode] = {
            "mean_ms": round(statistics.fmean(timings), 3),
            "median_ms": round(statistics.median(timings), 3),
            "p95_ms": round(_percentile(timings, 0.95), 3),
            "peak_ms": round(max(timings), 3),
        }

    payload = {
        "size": [scene.width(), scene.height()],
        "frames_per_mode": max(5, int(frames)),
        "requested_quality": quality,
        "final_performance": scene.performance_stats,
        "modes": results,
    }
    scene.deleteLater()
    app.processEvents()
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure Melodex visual paint cost without audio playback."
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument(
        "--quality",
        choices=("auto", "eco", "high", "battery"),
        default="auto",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = run_probe(args.width, args.height, args.frames, args.quality)
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", "utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
