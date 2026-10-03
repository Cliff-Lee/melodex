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


def test_memory_atlas_hover_explains_a_group_and_click_pins_it():
    QEvent, QPointF, Qt, QColor, QImage, QMouseEvent, QApplication = _qt()
    from melodex.visualization_models import MemoryMark
    from melodex.visualization_profile import build_visual_profile
    from melodex.visualization_scene import LivingScene

    app = QApplication.instance() or QApplication([])
    scene = LivingScene()
    scene.resize(900, 520)
    scene.set_profile(build_visual_profile({"artist": "Current", "title": "Track"}))
    scene.set_mode("memory")
    scene.set_memory((
        MemoryMark(
            "Thu 08:10",
            "Artist A",
            4,
            210,
            0.25,
            0.36,
            0.08,
            "Thu Oct 01 · 08:10–08:35",
            "Song One · Artist A",
            "Morning",
        ),
        MemoryMark(
            "Thu 20:20",
            "Artist B",
            7,
            285,
            0.76,
            0.68,
            0.12,
            "Thu Oct 01 · 20:20–21:05",
            "Song Two · Artist B",
            "Evening",
        ),
    ), "sessions")
    scene.show()
    app.processEvents()

    image = QImage(scene.size(), QImage.Format_ARGB32)
    image.fill(QColor("#000000"))
    scene.render(image)

    assert len(scene._memory_hit_points) == 2
    point, index, _radius = scene._memory_hit_points[0]
    assert index == 0

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
    assert scene._hovered_memory_index == 0
    assert scene._active_memory_index() == 0
    assert "Thu 08:10" in scene.toolTip()

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
    assert scene._selected_memory_index == 0

    empty = QPointF(scene.width() - 3, scene.height() - 3)
    move_away = QMouseEvent(
        QEvent.MouseMove,
        empty,
        empty,
        empty,
        Qt.NoButton,
        Qt.NoButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(scene, move_away)
    assert scene._hovered_memory_index is None
    assert scene._active_memory_index() == 0

    scene.deleteLater()
    app.processEvents()


def test_memory_atlas_is_named_and_status_explains_visual_semantics():
    _QEvent, _QPointF, _Qt, _QColor, _QImage, _QMouseEvent, QApplication = _qt()
    from melodex.living_canvas import LivingCanvasView
    from melodex.visualization_models import MemoryMark

    app = QApplication.instance() or QApplication([])
    view = LivingCanvasView()
    memory_index = next(
        i for i in range(view.mode_combo.count())
        if view.mode_combo.itemData(i) == "memory"
    )
    assert view.mode_combo.itemText(memory_index) == "Memory Atlas"

    view.set_track({"artist": "Example", "title": "Track", "duration": 100})
    view.mode_combo.setCurrentIndex(memory_index)
    view.set_memory_marks((
        MemoryMark(
            "Fri 23:10",
            "Artist",
            3,
            220,
            0.5,
            0.79,
            0.05,
            "Fri Oct 02 · 23:10–23:30",
            "Song · Artist",
            "Late night",
        ),
    ), "sessions")
    view._update_status()

    status = view.status.text().casefold()
    assert "left-to-right is chronological time" in status
    assert "height is average time of day" in status
    assert "island size is play count" in status

    view.deleteLater()
    app.processEvents()


def test_memory_atlas_reuses_static_render_cache_until_inputs_change():
    _QEvent, _QPointF, _Qt, QColor, QImage, _QMouseEvent, QApplication = _qt()
    from melodex.visualization_models import MemoryMark
    from melodex.visualization_profile import build_visual_profile
    from melodex.visualization_scene import LivingScene

    app = QApplication.instance() or QApplication([])
    scene = LivingScene()
    scene.resize(960, 540)
    scene.set_profile(build_visual_profile({"artist": "Current", "title": "Track"}))
    scene.set_mode("memory")
    marks = tuple(
        MemoryMark(
            f"Session {index}",
            f"Artist {index % 5}",
            1 + index % 4,
            (205 + index * 17) % 360,
            index / 31.0,
            0.14 + 0.68 * ((index * 7) % 24) / 23.0,
            0.01,
            f"Oct 03 · {index % 24:02d}:00",
            f"Track {index}",
            "Evening",
        )
        for index in range(32)
    )
    scene.set_memory(marks, "sessions")

    image = QImage(scene.size(), QImage.Format_ARGB32)
    image.fill(QColor("#000000"))
    scene.render(image)
    first_key = scene._memory_cache.cacheKey()
    assert first_key

    scene.render(image)
    assert scene._memory_cache.cacheKey() == first_key

    scene.set_accent_color(QColor("#86b9ff"))
    assert scene._memory_cache.isNull()
    scene.render(image)
    second_key = scene._memory_cache.cacheKey()
    assert second_key and second_key != first_key

    scene.resize(1100, 620)
    larger = QImage(scene.size(), QImage.Format_ARGB32)
    larger.fill(QColor("#000000"))
    scene.render(larger)
    assert scene._memory_cache.size() == scene.size()

    scene.deleteLater()
    app.processEvents()
