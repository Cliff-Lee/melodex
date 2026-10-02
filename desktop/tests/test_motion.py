from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QGraphicsOpacityEffect

from melodex.motion import (
    FAST_MOTION_MS,
    MAX_ROUTINE_MOTION_MS,
    STANDARD_MOTION_MS,
    MotionController,
)


def test_routine_motion_budget_is_short():
    assert FAST_MOTION_MS <= 150
    assert STANDARD_MOTION_MS <= MAX_ROUTINE_MOTION_MS
    assert MAX_ROUTINE_MOTION_MS <= 180


def test_settle_never_hides_content():
    app = QApplication.instance() or QApplication([])
    label = QLabel("Destination")
    label.show()
    controller = MotionController(reduced=False)

    animation = controller.settle(
        label,
        duration_ms=STANDARD_MOTION_MS,
        start_opacity=0.84,
    )

    assert animation is not None
    assert animation.duration() == STANDARD_MOTION_MS
    effect = label.graphicsEffect()
    assert isinstance(effect, QGraphicsOpacityEffect)
    assert 0.75 <= effect.opacity() <= 1.0

    animation.stop()
    label.deleteLater()
    app.processEvents()


def test_reduced_motion_disables_settle(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("MELODEX_REDUCE_MOTION", "1")
    label = QLabel("Destination")
    controller = MotionController(reduced=False)

    animation = controller.settle(label)

    assert animation is None
    assert controller.snapshot()["reduced_motion"] is True

    label.deleteLater()
    app.processEvents()
