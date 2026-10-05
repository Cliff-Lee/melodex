from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QSlider, QStyle


from .seek_interaction import SeekInteraction

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
