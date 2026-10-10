from __future__ import annotations

import argparse
import ast
import json
import math
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
from melodex.album_wall import AlbumWallWidget  # noqa: E402
from melodex.music_map import MusicMapWidget  # noqa: E402
from melodex.rich_now_playing import RichNowPlayingWidget  # noqa: E402
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


def _application_stylesheet() -> str:
    source = (DESKTOP / "melodex" / "main_window.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "setStyleSheet" or not node.args:
            continue
        value = node.args[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            if "QMainWindow,QWidget" in value.value:
                return value.value
    raise RuntimeError("Could not find the app stylesheet for visual QA captures")


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


def _album_fixture(count: int = 18) -> tuple[dict[str, object], dict[str, object]]:
    albums = []
    first_track = None
    for index in range(count):
        track = {
            "provider_id": "local",
            "track_id": f"/fixture/track-{index}.flac",
            "local_path": f"/fixture/track-{index}.flac",
            "artist": f"Artist {index + 1:02d}",
            "album": f"Album {index + 1:02d}",
            "title": f"Track {index + 1:02d}",
            "disc_number": 1,
            "track_number": 1,
        }
        if first_track is None:
            first_track = track
        albums.append({
            "key": f"fixture-{index}",
            "artist": track["artist"],
            "title": track["album"],
            "year": 1998 + index % 25,
            "genres": ["Electronic" if index % 2 == 0 else "Ambient"],
            "track_count": 1,
            "tracks": [track],
            "representative_track": track,
            "analysed_tracks": 1,
            "sound_x": ((index % 6) / 3.0) - 1.0,
            "sound_y": ((index // 6) / 1.5) - 1.0,
            "fallback_x": ((index % 6) / 3.0) - 1.0,
            "fallback_y": ((index // 6) / 1.5) - 1.0,
            "familiarity": (index % 9) / 9.0,
            "rediscovery": 0.0,
            "plays": index * 3,
            "time_x": 0.0,
            "time_y": 0.0,
            "familiarity_x": 0.0,
            "familiarity_y": 0.0,
            "cover_path": "",
        })
    return {"albums": albums, "album_count": count, "analysed_albums": count}, first_track or {}


def capture(out: Path, width: int = 1440, height: int = 900) -> dict[str, object]:
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(_application_stylesheet())
    out.mkdir(parents=True, exist_ok=True)

    art_path = out / "_fixture_art.png"
    _album_art(art_path)

    manifest: dict[str, object] = {"size": [width, height], "captures": []}

    def record(name: str, description: str) -> None:
        manifest["captures"].append({"file": name, "description": description})

    now_playing = RichNowPlayingWidget(object())
    now_playing.resize(width, height)
    now_playing.set_track({
        **TRACK,
        "provider_id": "local",
        "local_path": "/fixture/glass-horizons.flac",
    })
    now_playing._set_art(str(art_path))
    now_playing._set_artist_photo(str(art_path))
    now_playing._set_artist_photo_credit({
        "path": str(art_path),
        "attribution": "Fixture Photographer",
        "source": "Fixture Archive",
        "license_name": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
    })
    _save_widget(now_playing, out / "14-now-playing.png", width, height)
    record("14-now-playing.png", "Now Playing with album art, artist photo, and attribution available on hover.")
    now_playing.deleteLater()

    album_model, current_track = _album_fixture()
    album_wall = AlbumWallWidget()
    album_wall.resize(width, height)
    album_wall.set_model(album_model, current_track)
    album_wall.set_artwork({key: str(art_path) for key in album_wall.tiles})
    _save_widget(album_wall, out / "12-album-wall.png", width, height)
    record("12-album-wall.png", "Album Wall with populated covers, quiet labels, controls, and current album.")
    album_wall.deleteLater()

    music_map = MusicMapWidget()
    map_nodes = []
    ref_map = {}
    cluster_centres = ((-0.52, 0.42), (0.48, 0.38), (0.02, -0.54))
    for index in range(18):
        ref = f"track-{index}"
        track = {
            "track_id": ref,
            "artist": f"Artist {index + 1:02d}",
            "album": f"Album {index + 1:02d}",
            "title": f"Track {index + 1:02d}",
        }
        cluster = index // 6
        point = index % 6
        angle = point * 1.047 + cluster * 0.31
        radius = 0.16 + 0.045 * (point % 3)
        centre_x, centre_y = cluster_centres[cluster]
        map_nodes.append({
            "ref": ref,
            **track,
            "x": centre_x + math.cos(angle) * radius,
            "y": centre_y + math.sin(angle) * radius,
            "energy": 0.35 + (index % 6) * 0.1,
            "taste": 0.25 + (index % 5) * 0.12,
            "rediscovery": 0.1 + (index % 4) * 0.18,
        })
        ref_map[ref] = track
    music_map.resize(width, height)
    music_map.set_map({"nodes": map_nodes, "edges": [], "analysed": len(map_nodes), "input_profiles": len(map_nodes)}, ref_map)
    music_map.set_artwork({
        ref: {"generation": music_map._art_generation, "image": QImage(str(art_path))}
        for ref in ref_map
    })
    first_item = music_map.node_items.get("track-0")
    if first_item is not None:
        first_item._hovered = True
        first_item._resize_on_hover(True)
    _save_widget(music_map, out / "13-music-map.png", width, height)
    record("13-music-map.png", "Music Map with album covers, one expanded hover detail card, and zoom controls.")

    # MM2: capture an actual open overlay at every qualification resolution.
    # The viewport must not shrink when the visual controls are revealed.
    original_view_rect = music_map.view.geometry()
    music_map.view_button.click()
    app.processEvents()
    if music_map.view.geometry() != original_view_rect:
        raise AssertionError("View settings unexpectedly resized the Music Map canvas")
    _save_widget(music_map, out / "13b-music-map-view.png", width, height)
    record("13b-music-map-view.png", "Music Map with floating colour/connection settings and unchanged viewport.")
    music_map.view_button.click()
    app.processEvents()
    music_map.deleteLater()

    # MM2-3a: use actual Flow projection positions to exercise overview LOD.
    dense_map = MusicMapWidget()
    dense_nodes = []
    dense_refs = {}
    for index in range(240):
        cluster = index // 80
        local = index % 80
        centres = ((-0.65, 0.37), (0.55, 0.42), (0.26, -0.53))
        centre_x, centre_y = centres[cluster]
        ref = f"dense-{index}"
        track = {
            "track_id": ref,
            "artist": f"Local Artist {index // 6 + 1}",
            "album": f"Album {index // 12 + 1}",
            "title": f"Mapped song {index + 1}",
        }
        dense_nodes.append({
            "ref": ref, **track,
            "x": centre_x + (local % 10 - 5) * 0.011,
            "y": centre_y + (local // 10 - 4) * 0.011,
        })
        dense_refs[ref] = track
    dense_map.resize(width, height)
    dense_map.set_map({
        "nodes": dense_nodes, "edges": [], "analysed": len(dense_nodes),
        "input_profiles": len(dense_nodes),
    }, dense_refs)
    app.processEvents()
    if not dense_map._cluster_items:
        raise AssertionError("Dense Music Map did not create overview clusters")
    dense_map.set_artwork({
        ref: {"generation": dense_map._art_generation, "image": QImage(str(art_path))}
        for ref in dense_refs
    })
    _save_widget(dense_map, out / "13c-music-map-clusters.png", width, height)
    record("13c-music-map-clusters.png", "MM2 overview groups nearby analysed tracks with album artwork and counts.")
    dense_map.deleteLater()

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
            "",
            "",
            "",
            False,
            "Embedded lyrics",
            -1,
            "First unsynced line\nThe words should still feel deliberate\nEven without timing metadata",
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

    reduced = _scene(width, height)
    reduced.set_mode("living")
    reduced.set_quality("auto")
    reduced._effective_quality = "eco"
    reduced._performance.effective = "eco"
    reduced._phase = 2.35
    reduced._refresh_visual_state()
    _save_widget(reduced, out / "10-auto-reduced-profile-pulse.png", width, height)
    record("10-auto-reduced-profile-pulse.png", "Profile Pulse with Auto reduced rendering budget.")
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
