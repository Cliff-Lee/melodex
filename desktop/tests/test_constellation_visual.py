from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QColor, QImage, QMouseEvent
        from PySide6.QtWidgets import QApplication
        return QEvent, QPointF, Qt, QColor, QImage, QMouseEvent, QApplication
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")


def test_constellation_hover_reveals_preview_and_click_holds_selection(tmp_path):
    QEvent, QPointF, Qt, QColor, QImage, QMouseEvent, QApplication = _qt()
    from melodex.visualization_models import VisualNeighbour
    from melodex.visualization_profile import build_visual_profile
    from melodex.visualization_scene import LivingScene

    app = QApplication.instance() or QApplication([])
    scene = LivingScene()
    scene.resize(900, 520)
    scene.set_profile(build_visual_profile(
        {"artist": "Centre", "title": "Current", "duration": 200},
        {"bpm": 118, "energy": 0.62, "onset_density": 0.1},
    ))
    scene.set_mode("constellation")
    scene.set_neighbours((
        VisualNeighbour(7, "Nearby Artist", "Nearby Song", "Nearby Album", "Same artist", 0.68, 0.44, 0.88),
        VisualNeighbour(8, "Other Artist", "Other Song", "Other Album", "Recently heard", 0.28, 0.67, 0.52),
    ))
    scene.show()
    app.processEvents()

    image = QImage(scene.size(), QImage.Format_ARGB32)
    image.fill(QColor("#000000"))
    scene.render(image)
    assert scene._hit_points

    selected = []
    scene.neighbourSelected.connect(selected.append)
    point = scene._hit_points[0][0]

    move = QMouseEvent(
        QEvent.MouseMove,
        point,
        point,
        point,
        Qt.NoButton,
        Qt.NoButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(scene, move)
    assert scene._hovered_token == 7
    assert selected[-1] == 7
    assert scene._active_constellation_token() == 7

    cover = QImage(48, 48, QImage.Format_ARGB32)
    cover.fill(QColor("#2b6fbd"))
    cover_path = tmp_path / "cover.png"
    assert cover.save(str(cover_path))
    scene.set_neighbour_artwork(7, str(cover_path))
    assert 7 in scene._neighbour_artwork
    assert scene._neighbour_artwork[7].width() <= 112 or scene._neighbour_artwork[7].height() <= 112

    press = QMouseEvent(
        QEvent.MouseButtonPress,
        point,
        point,
        point,
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(scene, press)
    assert scene._selected_token == 7

    empty = QPointF(scene.width() - 4, scene.height() - 4)
    leave_move = QMouseEvent(
        QEvent.MouseMove,
        empty,
        empty,
        empty,
        Qt.NoButton,
        Qt.NoButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(scene, leave_move)
    assert scene._hovered_token is None
    assert scene._active_constellation_token() == 7

    rendered = QImage(scene.size(), QImage.Format_ARGB32)
    rendered.fill(QColor("#000000"))
    scene.render(rendered)
    assert rendered.pixelColor(rendered.width() // 2, rendered.height() // 2) != QColor("#000000")

    scene.deleteLater()
    app.processEvents()


def test_living_canvas_requests_artwork_only_for_interacted_neighbour():
    QEvent, QPointF, Qt, QColor, QImage, QMouseEvent, QApplication = _qt()
    from melodex.living_canvas import LivingCanvasView
    from melodex.visualization_models import VisualNeighbour

    app = QApplication.instance() or QApplication([])
    view = LivingCanvasView()
    view.set_track({"artist": "Centre", "title": "Current", "duration": 100})
    node = VisualNeighbour(3, "Artist", "Song", "Album", "Up next", 0.7, 0.5, 0.76)
    view.set_neighbours((node,))

    requested = []
    view.neighbourPreviewRequested.connect(requested.append)
    view._neighbour_selected(3)

    assert requested == [3]
    assert "hover reveals artwork" in view.status.text()

    view.deleteLater()
    app.processEvents()
