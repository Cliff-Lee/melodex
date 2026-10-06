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


def test_profile_pulse_fills_plane_with_concentric_music_reactive_contours():
    QColor, QImage, QApplication = _qt()
    from melodex.living_canvas import LivingCanvasView
    from melodex.visualization_profile import build_visual_profile
    from melodex.visualization_scene import LivingScene

    app = QApplication.instance() or QApplication([])
    view = LivingCanvasView()
    living_index = next(
        i for i in range(view.mode_combo.count())
        if view.mode_combo.itemData(i) == "living"
    )
    assert view.mode_combo.itemText(living_index) == "Profile Pulse"

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

    contour_points = []
    smooth_path = scene._smooth_closed_path

    def capture_contour(points):
        contour_points.append(tuple((point.x(), point.y()) for point in points))
        return smooth_path(points)

    scene._smooth_closed_path = capture_contour

    first = QImage(scene.size(), QImage.Format_ARGB32)
    first.fill(QColor("#000000"))
    scene.render(first)
    assert len(contour_points) == 7
    all_points = [point for contour in contour_points for point in contour]
    area = scene._area()
    assert max(x for x, _y in all_points) - min(x for x, _y in all_points) >= area.width() * 0.75
    assert max(y for _x, y in all_points) - min(y for _x, y in all_points) >= area.height() * 0.75

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


def test_removed_visualizers_are_not_selectable():
    QColor, QImage, QApplication = _qt()
    from melodex.living_canvas import LivingCanvasView
    app = QApplication.instance() or QApplication([])
    view = LivingCanvasView()
    modes = [
        view.mode_combo.itemData(i)
        for i in range(view.mode_combo.count())
        if isinstance(view.mode_combo.itemData(i), str)
    ]
    assert "weather" not in modes
    assert "minimal" not in modes
    view.deleteLater()
    app.processEvents()


def test_profile_pulse_respects_battery_static_budget():
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

    scene.set_mode("living")
    assert not scene._timer.isActive()
    image = QImage(scene.size(), QImage.Format_ARGB32)
    image.fill(QColor("#000000"))
    scene.render(image)
    assert _signature(image)

    scene.deleteLater()
    app.processEvents()
