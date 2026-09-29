from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def test_canvas_animation_stops_when_paused_hidden_or_minimized():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtGui import QImage
        from PySide6.QtWidgets import QApplication

        from melodex.visualization_models import LyricFrame, MemoryMark, VisualNeighbour
        from melodex.visualization_profile import build_visual_profile
        from melodex.visualization_scene import LivingScene
        from melodex.visualizer_plugins import parse_visualizer
    except ImportError as exc:
        import pytest

        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    scene = LivingScene()
    scene.resize(640, 320)
    scene.set_profile(build_visual_profile({"artist": "Example", "title": "Test", "duration": 180}, {
        "bpm": 120, "energy": 0.6, "spectral_centroid": 1700,
        "onset_density": 0.1, "energy_curve": [0.1, 0.6, 0.4, 0.9],
    }))
    scene.show()
    app.processEvents()
    assert not scene._timer.isActive()

    scene.set_playing(True)
    assert scene._timer.isActive()

    scene.set_mode("fingerprint")
    assert not scene._timer.isActive()
    scene.set_mode("living")
    assert scene._timer.isActive()

    scene.set_window_minimized(True)
    assert not scene._timer.isActive()
    scene.set_window_minimized(False)
    assert scene._timer.isActive()

    scene.set_playing(False)
    assert not scene._timer.isActive()
    scene.set_playing(True)

    scene.set_quality("battery")
    assert not scene._timer.isActive()
    scene.set_quality("high")
    assert scene._timer.isActive()
    assert scene._timer.interval() == 34

    scene.set_neighbours((VisualNeighbour(1, "Other", "Song", "Album", "Up next", 0.8, 0.5),))
    scene.set_lyrics(LyricFrame("before", "current", "after", True, "local"))
    scene.set_memory((MemoryMark("Today", "Artist", 3, 180, 0.5, 0.4),), "sessions")
    plugin = parse_visualizer(
        '{"format":"mdxviz","api_version":1,"manifest":{"id":"org.example.test","name":"Test","author":"","description":""},'
        '"scene":{"layers":[{"type":"rings","count":3,"gain":0.2,"feature":"energy","palette":0,"speed":0.05}]}}'
    )
    for mode, recipe in (
        ("living", None), ("fingerprint", None), ("journey", None),
        ("constellation", None), ("lyrics", None), ("album_world", None),
        ("weather", None), ("memory", None), ("minimal", None), ("plugin", plugin),
    ):
        scene.set_mode(mode, recipe)
        image = QImage(640, 320, QImage.Format_ARGB32)
        image.fill(0)
        scene.render(image)
    scene.hide()
    app.processEvents()
    assert not scene._timer.isActive()
    scene.deleteLater()
    app.processEvents()


def test_canvas_modes_plugins_and_analysis_refresh_keep_lyrics(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication

        from melodex.living_canvas import LivingCanvasView
        from melodex.visualization_profile import build_visual_profile
        from melodex.visualizer_plugins import install_visualizer_file
    except ImportError as exc:
        import pytest

        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    sample = ROOT.parent / "docs" / "visualizers" / "examples" / "orbit-garden.mdxviz"
    recipe, _ = install_visualizer_file(sample, tmp_path / "visualizers")
    view = LivingCanvasView(visualizer_dir=tmp_path / "visualizers")
    view.set_track({"artist": "Example", "title": "Test", "duration": 100}, None)
    modes = [view.mode_combo.itemData(i) for i in range(9)]
    assert modes == [
        "living", "fingerprint", "journey", "constellation", "lyrics",
        "album_world", "weather", "memory", "minimal",
    ]
    plugin_index = next(i for i in range(view.mode_combo.count()) if view.mode_combo.itemData(i) == ("plugin", recipe.id))
    view.mode_combo.setCurrentIndex(plugin_index)
    assert view.active_mode == "plugin"
    assert view.scene.plugin.name == "Orbit Garden"
    assert view.remove_button.isEnabled()

    view.set_lyrics({"text": "First line\nSecond line", "source": "local"})
    before = view.scene._lyrics
    view.set_analysis({"bpm": 124, "energy": 0.7, "energy_curve": [0.2, 0.9]})
    assert view.scene._lyrics == before
    assert view.scene.profile == build_visual_profile(view._track, {"bpm": 124, "energy": 0.7, "energy_curve": [0.2, 0.9]})

    view.deleteLater()
    app.processEvents()


def test_cover_palette_is_sampled_into_a_small_cached_set(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor, QImage, QPainter
        from PySide6.QtWidgets import QApplication

        from melodex.rich_now_playing import RichNowPlayingWidget
    except ImportError as exc:
        import pytest

        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    image = QImage(48, 48, QImage.Format_ARGB32)
    image.fill(QColor("#182030"))
    painter = QPainter(image)
    painter.fillRect(QRect(0, 0, 24, 48), QColor("#d53b66"))
    painter.fillRect(QRect(24, 0, 24, 48), QColor("#236dc0"))
    painter.end()
    cover = tmp_path / "cover.png"
    assert image.save(str(cover))

    widget = RichNowPlayingWidget(object())
    palettes = []
    widget.paletteChanged.connect(palettes.append)
    widget._set_art(str(cover))

    assert palettes
    assert 2 <= len(palettes[-1]) <= 6
    assert all(QColor(value).isValid() for value in palettes[-1])
    widget.deleteLater()
    app.processEvents()
