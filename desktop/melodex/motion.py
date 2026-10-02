from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


FAST_MOTION_MS = 120
STANDARD_MOTION_MS = 150
MAX_ROUTINE_MOTION_MS = 180


def env_reduced_motion() -> bool:
    value = str(os.environ.get("MELODEX_REDUCE_MOTION", "") or "").strip().casefold()
    return value in {"1", "true", "yes", "on"}


class MotionController(QObject):
    """Tiny non-blocking motion language for causal UI feedback.

    Motion never controls when content becomes available. Widgets are already
    visible and interactive before these short settle animations run.
    """

    def __init__(self, parent: QObject | None = None, *, reduced: bool = False) -> None:
        super().__init__(parent)
        self.reduced = bool(reduced or env_reduced_motion())
        self._animations: dict[int, QPropertyAnimation] = {}

    def set_reduced(self, reduced: bool) -> None:
        self.reduced = bool(reduced)
        if self.reduced:
            for animation in list(self._animations.values()):
                animation.stop()
            self._animations.clear()

    def settle(
        self,
        widget: QWidget | None,
        *,
        duration_ms: int = FAST_MOTION_MS,
        start_opacity: float = 0.88,
    ) -> QPropertyAnimation | None:
        if widget is None:
            return None

        duration = max(0, min(int(duration_ms), MAX_ROUTINE_MOTION_MS))
        if self.reduced or duration <= 0:
            effect = widget.graphicsEffect()
            if isinstance(effect, QGraphicsOpacityEffect):
                effect.setOpacity(1.0)
            return None

        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        # The UI is never hidden. This is a short visual settle after the
        # immediate state change, not a gate before the user can see content.
        start = max(0.75, min(1.0, float(start_opacity)))
        effect.setOpacity(start)

        key = id(widget)
        previous = self._animations.pop(key, None)
        if previous is not None:
            previous.stop()

        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(duration)
        animation.setStartValue(start)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)

        def finished() -> None:
            effect.setOpacity(1.0)
            self._animations.pop(key, None)

        animation.finished.connect(finished)
        self._animations[key] = animation
        animation.start()
        return animation

    def active_animation(self, widget: QWidget) -> QPropertyAnimation | None:
        return self._animations.get(id(widget))

    def snapshot(self) -> dict[str, Any]:
        return {
            "reduced_motion": self.reduced,
            "fast_motion_ms": FAST_MOTION_MS,
            "standard_motion_ms": STANDARD_MOTION_MS,
            "max_routine_motion_ms": MAX_ROUTINE_MOTION_MS,
            "active_animations": len(self._animations),
        }
