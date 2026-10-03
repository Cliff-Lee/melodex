from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QApplication
        return QColor, QImage, QApplication
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")


def _signature(image):
    points = []
    step_x = max(1, image.width() // 24)
    step_y = max(1, image.height() // 16)
    for y in range(0, image.height(), step_y):
        for x in range(0, image.width(), step_x):
            color = image.pixelColor(x, y)
            points.append((color.red(), color.green(), color.blue(), color.alpha()))
    return tuple(points)


def test_profile_pulse_is_the_primary_living_scene_and_is_music_reactive():
    QColor, QImage, QApplication = _qt()
    from melodex.living_canvas import LivingCanvasView
    from melodex.visualization_profile import build_visual_profile
    from melodex.visualization_scene import LivingScene

    app = QApplication.instance() or QApplication([])
    view = LivingCanvasView()
    assert view.mode_combo.itemText(0) == "Profile Pulse"
    assert view.mode_combo.itemData(0) == "living"

    scene = LivingScene()
    scene.resize(860, 500)
    scene.set_profile(build_visual_profile(
        {"artist": "Example", "title": "Pulse", "duration": 200},
        {
            "bpm": 126,
            "energy": 0.78,
            "spectral_centroid": 2300,
            "onset_density": 0.16,
            "energy_curve": [0.18, 0.82, 0.35, 0.94, 0.52],
        },
    ))
    scene.set_mode("living")
    scene.set_position_fraction(0.15)
    scene._phase = 0.0
    scene._refresh_visual_state()

    first = QImage(scene.size(), QImage.Format_ARGB32)
    first.fill(QColor("#000000"))
    scene.render(first)

    scene.set_position_fraction(0.78)
    scene._phase = 2.1
    scene._refresh_visual_state()
    second = QImage(scene.size(), QImage.Format_ARGB32)
    second.fill(QColor("#000000"))
    scene.render(second)

    assert _signature(first) != _signature(second)

    scene.deleteLater()
    view.deleteLater()
    app.processEvents()


def test_sonic_weather_is_an_animated_atmospheric_field():
    QColor, QImage, QApplication = _qt()
    from melodex.visualization_profile import build_visual_profile
    from melodex.visualization_scene import LivingScene

    app = QApplication.instance() or QApplication([])
    scene = LivingScene()
    scene.resize(860, 500)
    scene.set_profile(build_visual_profile(
        {"artist": "Example", "title": "Weather", "duration": 220},
        {
            "bpm": 132,
            "energy": 0.86,
            "spectral_centroid": 1200,
            "onset_density": 0.20,
            "energy_curve": [0.65, 0.88, 0.72, 0.93],
        },
    ))
    scene.set_mode("weather")
    assert scene.animated_mode

    scene._phase = 0.0
    scene._refresh_visual_state()
    first = QImage(scene.size(), QImage.Format_ARGB32)
    first.fill(QColor("#000000"))
    scene.render(first)

    scene._phase = 3.4
    scene._refresh_visual_state()
    second = QImage(scene.size(), QImage.Format_ARGB32)
    second.fill(QColor("#000000"))
    scene.render(second)

    assert _signature(first) != _signature(second)

    scene.deleteLater()
    app.processEvents()


def test_profile_pulse_and_weather_respect_battery_static_budget():
    QColor, QImage, QApplication = _qt()
    from melodex.visualization_profile import build_visual_profile
    from melodex.visualization_scene import LivingScene

    app = QApplication.instance() or QApplication([])
    scene = LivingScene()
    scene.resize(640, 360)
    scene.set_profile(build_visual_profile(
        {"artist": "Example", "title": "Static"},
        {"bpm": 110, "energy": 0.55, "onset_density": 0.08},
    ))
    scene.show()
    scene.set_playing(True)
    scene.set_quality("battery")

    for mode in ("living", "weather"):
        scene.set_mode(mode)
        assert not scene._timer.isActive()
        image = QImage(scene.size(), QImage.Format_ARGB32)
        image.fill(QColor("#000000"))
        scene.render(image)
        assert _signature(image)

    scene.deleteLater()
    app.processEvents()
