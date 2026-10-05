from __future__ import annotations

import time
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QSlider, QStyle


class SeekInteraction:
    """Own transport-slider arbitration while the user seeks.

    Player position updates remain authoritative for playback state, but they
    must not overwrite the slider while the user is dragging/clicking it or
    while the media backend is still acknowledging a committed seek.
    """

    def __init__(
        self,
        *,
        tolerance_ms: int = 900,
        commit_timeout_ms: int = 2000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.tolerance_ms = max(0, int(tolerance_ms))
        self.commit_timeout_ms = max(100, int(commit_timeout_ms))
        self._clock = clock
        self.state = "idle"
        self.target_ms: int | None = None
        self._commit_started_at = 0.0
        self._metrics = {
            "scrubs_started": 0,
            "commits": 0,
            "acknowledged": 0,
            "timed_out": 0,
            "player_updates_suppressed": 0,
            "cancelled": 0,
        }

    def begin(self) -> None:
        self.state = "scrubbing"
        self.target_ms = None
        self._commit_started_at = 0.0
        self._metrics["scrubs_started"] += 1

    def commit(self, slider_value: int, duration_ms: int) -> int | None:
        duration = max(0, int(duration_ms))
        if duration <= 0:
            self.cancel()
            return None
        value = max(0, min(1000, int(slider_value)))
        target = int(round(duration * value / 1000.0))
        self.state = "committing"
        self.target_ms = target
        self._commit_started_at = self._clock()
        self._metrics["commits"] += 1
        return target

    def follow_player_position(self, position_ms: int, duration_ms: int) -> bool:
        """Return whether the slider may follow this player position update."""
        if self.state == "scrubbing":
            self._metrics["player_updates_suppressed"] += 1
            return False
        if self.state != "committing":
            return True

        target = self.target_ms
        if target is None:
            self.state = "idle"
            return True

        position = max(0, int(position_ms))
        duration = max(0, int(duration_ms))
        tolerance = max(
            self.tolerance_ms,
            min(2500, int(round(duration * 0.002))) if duration else 0,
        )
        if abs(position - target) <= tolerance:
            self.state = "idle"
            self.target_ms = None
            self._commit_started_at = 0.0
            self._metrics["acknowledged"] += 1
            return True

        elapsed_ms = (self._clock() - self._commit_started_at) * 1000.0
        if elapsed_ms >= self.commit_timeout_ms:
            self.state = "idle"
            self.target_ms = None
            self._commit_started_at = 0.0
            self._metrics["timed_out"] += 1
            return True

        self._metrics["player_updates_suppressed"] += 1
        return False

    def cancel(self) -> None:
        if self.state != "idle":
            self._metrics["cancelled"] += 1
        self.state = "idle"
        self.target_ms = None
        self._commit_started_at = 0.0

    def snapshot(self) -> dict[str, int | str | None]:
        return {
            **dict(self._metrics),
            "state": self.state,
            "target_ms": self.target_ms,
            "tolerance_ms": self.tolerance_ms,
            "commit_timeout_ms": self.commit_timeout_ms,
        }


class SeekSlider(QSlider):
    """A transport slider where any left-click is a real seek gesture.

    QSlider's platform-default groove click may only page-step and does not
    reliably emit sliderReleased. This control makes click, drag, wheel and
    keyboard seeking explicit and consistent across platforms.
    """

    seekStarted = Signal()
    seekFinished = Signal(int)

    _SEEK_KEYS = {
        Qt.Key_Left,
        Qt.Key_Right,
        Qt.Key_Up,
        Qt.Key_Down,
        Qt.Key_PageUp,
        Qt.Key_PageDown,
        Qt.Key_Home,
        Qt.Key_End,
    }

    def __init__(self, orientation: Qt.Orientation, parent=None) -> None:
        super().__init__(orientation, parent)
        self._pointer_seeking = False

    def _value_for_pointer(self, event: QMouseEvent) -> int:
        minimum = int(self.minimum())
        maximum = int(self.maximum())
        if self.orientation() == Qt.Horizontal:
            span = max(1, self.width() - 1)
            position = max(0, min(span, int(round(event.position().x()))))
            upside_down = bool(self.invertedAppearance())
            if self.layoutDirection() == Qt.RightToLeft:
                upside_down = not upside_down
        else:
            span = max(1, self.height() - 1)
            position = max(0, min(span, int(round(event.position().y()))))
            upside_down = not bool(self.invertedAppearance())
        return int(
            QStyle.sliderValueFromPosition(
                minimum,
                maximum,
                position,
                span,
                upside_down,
            )
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._pointer_seeking = True
            self.setSliderDown(True)
            self.seekStarted.emit()
            self.setValue(self._value_for_pointer(event))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pointer_seeking:
            self.setValue(self._value_for_pointer(event))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._pointer_seeking and event.button() == Qt.LeftButton:
            self.setValue(self._value_for_pointer(event))
            self._pointer_seeking = False
            self.setSliderDown(False)
            value = int(self.value())
            event.accept()
            self.seekFinished.emit(value)
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        before = int(self.value())
        self.seekStarted.emit()
        super().wheelEvent(event)
        after = int(self.value())
        if after == before:
            self.seekFinished.emit(before)
        else:
            self.seekFinished.emit(after)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        is_seek = event.key() in self._SEEK_KEYS
        if is_seek:
            self.seekStarted.emit()
        super().keyPressEvent(event)
        if is_seek:
            self.seekFinished.emit(int(self.value()))


__all__ = ["SeekInteraction", "SeekSlider"]
