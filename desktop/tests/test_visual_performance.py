from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QImage, QPainter
        from PySide6.QtWidgets import QApplication
        return QPointF, QColor, QImage, QPainter, QApplication
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")


def test_auto_quality_reduces_detail_and_frame_rate_after_sustained_slow_paints():
    _QPointF, _QColor, _QImage, _QPainter, QApplication = _qt()
    from melodex.visualization_scene import LivingScene

    app = QApplication.instance() or QApplication([])
    scene = LivingScene()
    scene.set_quality("auto")

    for _ in range(scene._performance.grace_frames):
        scene._adjust_auto_quality(40.0)
    scene._adjust_auto_quality(17.0)
    scene._adjust_auto_quality(17.5)
    assert scene._effective_quality == "normal"
    scene._adjust_auto_quality(18.0)

    assert scene._effective_quality == "eco"
    assert scene._timer.interval() == 84
    assert scene._quality_budget().max_particles <= 16
    assert scene.performance_stats["reductions"] == 1

    scene.deleteLater()
    app.processEvents()


def test_lyric_artwork_cache_is_resolution_bounded(tmp_path):
    _QPointF, QColor, QImage, _QPainter, QApplication = _qt()
    from melodex.lyrics_state import LyricFrame
    from melodex.visualization_profile import build_visual_profile
    from melodex.visualization_scene import LivingScene

    app = QApplication.instance() or QApplication([])
    art = QImage(128, 128, QImage.Format_ARGB32)
    art.fill(QColor("#315e9e"))
    path = tmp_path / "cover.png"
    assert art.save(str(path))

    scene = LivingScene()
    scene.resize(3840, 2160)
    scene.set_quality("auto")
    scene.set_profile(build_visual_profile(
        {"artist": "Example", "title": "Track", "duration": 180},
        {"energy": 0.7, "bpm": 120, "energy_curve": [0.2, 0.7, 0.9]},
    ))
    scene.set_mode("lyrics")
    scene.set_artwork(str(path))
    scene.set_lyrics(LyricFrame("", "Large screen lyric", "Next line", True, "local", 0))

    rendered = QImage(640, 360, QImage.Format_ARGB32)
    rendered.fill(QColor("#000000"))
    scene.resize(1920, 1080)
    scene.render(rendered)

    assert not scene._artwork_cache.isNull()
    assert max(scene._artwork_cache.width(), scene._artwork_cache.height()) <= 960

    scene.set_quality("eco")
    scene.render(rendered)
    assert max(scene._artwork_cache.width(), scene._artwork_cache.height()) <= 480

    scene.deleteLater()
    app.processEvents()


def test_glow_work_is_hard_capped_per_frame():
    QPointF, QColor, QImage, QPainter, QApplication = _qt()
    from melodex.visualization_scene import LivingScene

    app = QApplication.instance() or QApplication([])
    scene = LivingScene()
    scene.set_quality("auto")
    image = QImage(320, 240, QImage.Format_ARGB32)
    image.fill(QColor("#000000"))
    painter = QPainter(image)

    scene._frame_glows = 0
    for index in range(30):
        scene._draw_glow(
            painter,
            QPointF(20 + index * 4, 80),
            16,
            QColor("#6faeff"),
            40,
        )
    painter.end()

    assert scene._frame_glows == scene._quality_budget().max_glows
    assert scene._frame_glows <= 8

    scene.deleteLater()
    app.processEvents()
