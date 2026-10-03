from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
if str(DESKTOP) not in sys.path:
    sys.path.insert(0, str(DESKTOP))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from melodex.living_canvas import LivingCanvasView  # noqa: E402
from melodex.lyrics_state import LyricFrame  # noqa: E402
from melodex.visualization_models import (  # noqa: E402
    MemoryMark,
    VisualNeighbour,
    build_constellation,
)
from melodex.visualization_profile import build_visual_profile  # noqa: E402
from melodex.visualization_scene import LivingScene  # noqa: E402


TRACK = {
    "artist": "Night Transit",
    "title": "Glass Horizons",
    "album": "Afterimage",
    "duration": 242,
}
ANALYSIS = {
    "bpm": 124,
    "energy": 0.74,
    "spectral_centroid": 1780,
    "onset_density": 0.14,
    "energy_curve": [
        0.18, 0.22, 0.30, 0.45, 0.61, 0.78, 0.86, 0.72,
        0.54, 0.48, 0.66, 0.82, 0.91, 0.70, 0.52, 0.34,
    ],
}
PALETTE = ("#75b8ff", "#4f7fdc", "#8d79d8", "#d574a9", "#6aa8c7", "#bed7ff")


def _album_art(path: Path) -> None:
    image = QImage(640, 640, QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor("#07111d"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)

    bg = QLinearGradient(0, 0, 640, 640)
    bg.setColorAt(0.0, QColor("#0b1630"))
    bg.setColorAt(0.42, QColor("#274f7d"))
    bg.setColorAt(1.0, QColor("#101120"))
    painter.fillRect(image.rect(), bg)

    for x, y, radius, color in (
        (155, 180, 150, QColor(95, 177, 255, 110)),
        (470, 250, 190, QColor(107, 92, 220, 80)),
        (330, 500, 175, QColor(220, 91, 159, 65)),
    ):
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(x, y), radius, radius)

    painter.setPen(QColor(240, 247, 255, 210))
    painter.drawLine(70, 500, 570, 145)
    painter.setPen(QColor(180, 213, 245, 100))
    for offset in range(5):
        painter.drawLine(80, 535 + offset * 12, 520, 235 + offset * 7)
    painter.end()
    image.save(str(path))


def _save_widget(widget, path: Path, width: int, height: int) -> None:
    widget.resize(width, height)
    widget.show()
    QApplication.processEvents()
    image = QImage(widget.size(), QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor("#050910"))
    widget.render(image)
    if not image.save(str(path)):
        raise RuntimeError(f"Could not save {path.name}")
    widget.hide()
    QApplication.processEvents()


def _profile():
    return build_visual_profile(TRACK, ANALYSIS)


def _scene(width: int, height: int) -> LivingScene:
    scene = LivingScene()
    scene.resize(width, height)
    scene.set_profile(_profile())
    scene.set_palette(PALETTE)
    scene.set_accent_color(QColor("#79b9ff"))
    scene.set_position_fraction(0.58)
    scene.set_quality("auto")
    scene._phase = 2.35
    scene._refresh_visual_state()
    return scene


def _neighbours() -> tuple[VisualNeighbour, ...]:
    relations = ("Up next", "Played earlier", "Recently heard")
    candidates = []
    titles = ("Neon Return", "Parallel Lines", "Afterimage", "Soft Signal")
    for index in range(18):
        artist = (
            "Night Transit"
            if index < 4
            else ("Blue Static" if index < 9 else f"Artist {index + 1}")
        )
        title = titles[index] if index < 4 else f"Track {index + 1}"
        candidates.append(
            {
                "_visual_token": index + 1,
                "_visual_relation": relations[index % len(relations)],
                "artist": artist,
                "title": title,
                "album": "Afterimage" if index < 3 else f"Album {1 + index // 3}",
            }
        )
    return build_constellation(TRACK, candidates, limit=18)


def _memory() -> tuple[MemoryMark, ...]:
    marks = []
    for index in range(36):
        hour = (index * 5) % 24
        daypart = (
            "Late night" if hour < 5 or hour >= 22
            else "Morning" if hour < 12
            else "Afternoon" if hour < 17
            else "Evening"
        )
        marks.append(
            MemoryMark(
                label=f"Session {index + 1}",
                detail=f"Artist {1 + index % 8}",
                count=1 + index % 7,
                hue=(205 + index * 17) % 360,
                x=index / 35.0,
                y=0.14 + 0.68 * hour / 24.0,
                span=0.008 + (index % 5) * 0.006,
                time_label=f"Sep {10 + index // 3:02d} · {hour:02d}:{(index * 7) % 60:02d}",
                representative=f"Track {index + 1} · Artist {1 + index % 8}",
                daypart=daypart,
            )
        )
    return tuple(marks)


def capture(out: Path, width: int = 1440, height: int = 900) -> dict[str, object]:
    app = QApplication.instance() or QApplication([])
    out.mkdir(parents=True, exist_ok=True)

    art_path = out / "_fixture_art.png"
    _album_art(art_path)

    manifest: dict[str, object] = {"size": [width, height], "captures": []}

    def record(name: str, description: str) -> None:
        manifest["captures"].append({"file": name, "description": description})

    overview = LivingCanvasView()
    overview.set_track(TRACK, ANALYSIS)
    overview.set_palette(PALETTE)
    overview.set_accent_color(QColor("#79b9ff"))
    overview.set_artwork(str(art_path))
    overview.set_position(141000, 242000)
    _save_widget(overview, out / "00-visuals-overview.png", width, height)
    record(
        "00-visuals-overview.png",
        "Visuals shell with Track Sigil, grouped selector and Profile Pulse.",
    )
    overview.deleteLater()

    profile = _scene(width, height)
    profile.set_mode("living")
    _save_widget(profile, out / "01-profile-pulse.png", width, height)
    record("01-profile-pulse.png", "Profile Pulse energetic representative track.")
    profile.deleteLater()

    lyrics = _scene(width, height)
    lyrics.set_mode("lyrics")
    lyrics.set_immersive(True)
    lyrics.set_artwork(str(art_path))
    lyrics.set_lyrics(
        LyricFrame(
            "We left the city sleeping",
            "All the glass horizons open",
            "Every signal turns to blue",
            True,
            "LRCLIB",
            14,
        )
    )
    _save_widget(lyrics, out / "02-lyric-flow.png", width, height)
    record("02-lyric-flow.png", "Immersive synced Lyric Flow with artwork atmosphere.")
    lyrics.deleteLater()

    unsynced = _scene(width, height)
    unsynced.set_mode("lyrics")
    unsynced.set_immersive(True)
    unsynced.set_artwork(str(art_path))
    unsynced.set_lyrics(
        LyricFrame(
            "First unsynced line",
            "The words should still feel deliberate",
            "Even without timing metadata",
            False,
            "Embedded lyrics",
            6,
        )
    )
    _save_widget(unsynced, out / "03-lyric-flow-unsynced.png", width, height)
    record("03-lyric-flow-unsynced.png", "Untimed Lyric Flow fallback.")
    unsynced.deleteLater()

    constellation = _scene(width, height)
    constellation.set_mode("constellation")
    constellation.set_neighbours(_neighbours())
    constellation._selected_token = 2
    constellation.set_neighbour_artwork(2, str(art_path))
    _save_widget(constellation, out / "04-constellation.png", width, height)
    record("04-constellation.png", "Dense Constellation with pinned recognition card.")
    constellation.deleteLater()

    weather = _scene(width, height)
    weather.set_mode("weather")
    _save_widget(weather, out / "05-sonic-weather.png", width, height)
    record("05-sonic-weather.png", "Sonic Weather energetic atmospheric field.")
    weather.deleteLater()

    memory = _scene(width, height)
    memory.set_mode("memory")
    memory.set_memory(_memory(), "sessions")
    memory._selected_memory_index = 23
    _save_widget(memory, out / "06-memory-atlas.png", width, height)
    record("06-memory-atlas.png", "Memory Atlas with pinned session card.")
    memory.deleteLater()

    journey = _scene(width, height)
    journey.set_mode("journey")
    _save_widget(journey, out / "07-musical-journey.png", width, height)
    record("07-musical-journey.png", "Musical Journey context view.")
    journey.deleteLater()

    album = _scene(width, height)
    album.set_mode("album_world")
    _save_widget(album, out / "08-album-world-legacy.png", width, height)
    record(
        "08-album-world-legacy.png",
        "Legacy/internal Album World compatibility renderer; no longer in the public selector.",
    )
    album.deleteLater()

    minimal = _scene(width, height)
    minimal.set_mode("minimal")
    _save_widget(minimal, out / "09-minimal.png", width, height)
    record("09-minimal.png", "Minimal watch scene.")
    minimal.deleteLater()

    reduced = _scene(width, height)
    reduced.set_mode("weather")
    reduced.set_quality("auto")
    reduced._effective_quality = "eco"
    reduced._performance.effective = "eco"
    reduced._phase = 2.35
    reduced._refresh_visual_state()
    _save_widget(reduced, out / "10-auto-reduced-weather.png", width, height)
    record("10-auto-reduced-weather.png", "Sonic Weather with Auto reduced rendering budget.")
    reduced.deleteLater()

    empty = _scene(width, height)
    empty.set_mode("lyrics")
    empty.set_immersive(True)
    empty.set_lyrics(LyricFrame("", "", "", False, "", -1))
    _save_widget(empty, out / "11-lyrics-empty.png", width, height)
    record("11-lyrics-empty.png", "Lyric Flow empty state.")
    empty.deleteLater()

    QApplication.processEvents()
    art_path.unlink(missing_ok=True)
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture deterministic Melodex visual QA scenes.")
    parser.add_argument("--output", type=Path, default=Path("visual-qa"))
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    args = parser.parse_args()
    manifest = capture(args.output, args.width, args.height)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
