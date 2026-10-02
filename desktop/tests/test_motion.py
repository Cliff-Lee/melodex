from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_motion():
    try:
        from PySide6.QtWidgets import QApplication, QLabel, QGraphicsOpacityEffect
        from melodex.motion import (
            FAST_MOTION_MS,
            MAX_ROUTINE_MOTION_MS,
            STANDARD_MOTION_MS,
            MotionController,
        )
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")
    return (
        QApplication,
        QLabel,
        QGraphicsOpacityEffect,
        FAST_MOTION_MS,
        MAX_ROUTINE_MOTION_MS,
        STANDARD_MOTION_MS,
        MotionController,
    )


def test_routine_motion_budget_is_short():
    (
        _QApplication,
        _QLabel,
        _QGraphicsOpacityEffect,
        fast,
        maximum,
        standard,
        _MotionController,
    ) = _qt_motion()

    assert fast <= 150
    assert standard <= maximum
    assert maximum <= 180


def test_settle_never_hides_content():
    (
        QApplication,
        QLabel,
        QGraphicsOpacityEffect,
        _fast,
        _maximum,
        standard,
        MotionController,
    ) = _qt_motion()

    app = QApplication.instance() or QApplication([])
    label = QLabel("Destination")
    label.show()
    controller = MotionController(reduced=False)

    animation = controller.settle(
        label,
        duration_ms=standard,
        start_opacity=0.84,
    )

    assert animation is not None
    assert animation.duration() == standard
    effect = label.graphicsEffect()
    assert isinstance(effect, QGraphicsOpacityEffect)
    assert 0.75 <= effect.opacity() <= 1.0

    animation.stop()
    label.deleteLater()
    app.processEvents()


def test_reduced_motion_disables_settle(monkeypatch):
    (
        QApplication,
        QLabel,
        _QGraphicsOpacityEffect,
        _fast,
        _maximum,
        _standard,
        MotionController,
    ) = _qt_motion()

    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("MELODEX_REDUCE_MOTION", "1")
    label = QLabel("Destination")
    controller = MotionController(reduced=False)

    animation = controller.settle(label)

    assert animation is None
    assert controller.snapshot()["reduced_motion"] is True

    label.deleteLater()
    app.processEvents()
