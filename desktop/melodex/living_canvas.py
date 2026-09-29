"""Low-cost, track-aware Now Playing canvas and seekable Flow contour."""

from __future__ import annotations

import math
import random
import time
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QSlider, QSizePolicy, QVBoxLayout, QWidget,
)

from .visualization_profile import VisualProfile, build_visual_profile, energy_at


def _time_label(milliseconds: int) -> str:
    seconds = max(0, int(milliseconds) // 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"


class EnergyJourneySlider(QSlider):
    """Keyboard-accessible seek slider with a compact cached energy contour."""

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setRange(0, 1000)
        self.setFixedHeight(58)
        self.setTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName("Musical journey and playback position")
        self.setAccessibleDescription(
            "The contour shows cached Flow energy across the track. Use the arrow keys, "
            "or click and drag the contour, to seek."
        )
        self.setToolTip("Click or drag the contour to seek. Use the arrow keys for keyboard control.")
        self._curve: tuple[float, ...] = ()
        self._accent = QColor("#7eb4ff")
        self._chart_drag = False

    def set_curve(self, curve: tuple[float, ...]) -> None:
        self._curve = tuple(max(0.0, min(1.0, float(x))) for x in curve)
        self.update()

    def set_accent_color(self, color: QColor) -> None:
        self._accent = QColor(color)
        self.update()

    def set_fraction(self, fraction: float) -> None:
        value = int(round(max(0.0, min(1.0, float(fraction))) * self.maximum()))
        self.setValue(value)

    def _chart_rect(self) -> QRectF:
        return QRectF(8.0, 4.0, max(1.0, self.width() - 16.0), max(12.0, self.height() - 41.0))

    def _fraction_for_x(self, x: float) -> float:
        chart = self._chart_rect()
        return max(0.0, min(1.0, (x - chart.left()) / max(1.0, chart.width())))

    def _set_from_x(self, x: float) -> None:
        self.setValue(int(round(self._fraction_for_x(x) * self.maximum())))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._chart_rect().contains(event.position()):
            self._chart_drag = True
            self.setFocus(Qt.MouseFocusReason)
            self.setSliderDown(True)
            self._set_from_x(event.position().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._chart_drag:
            self._set_from_x(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._chart_drag and event.button() == Qt.LeftButton:
            self._set_from_x(event.position().x())
            self._chart_drag = False
            self.setSliderDown(False)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        chart = self._chart_rect()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        muted = QColor(self._accent)
        muted.setAlpha(48)
        painter.setPen(QPen(muted, 1.0, Qt.DashLine))
        painter.drawLine(QPointF(chart.left(), chart.bottom()), QPointF(chart.right(), chart.bottom()))

        if len(self._curve) >= 2:
            line = QPainterPath()
            fill = QPainterPath()
            for i, value in enumerate(self._curve):
                x = chart.left() + chart.width() * i / (len(self._curve) - 1)
                y = chart.bottom() - chart.height() * value
                if i == 0:
                    line.moveTo(x, y)
                    fill.moveTo(x, chart.bottom())
                    fill.lineTo(x, y)
                else:
                    line.lineTo(x, y)
                    fill.lineTo(x, y)
            fill.lineTo(chart.right(), chart.bottom())
            fill.closeSubpath()
            area = QColor(self._accent)
            area.setAlpha(22)
            painter.setPen(Qt.NoPen)
            painter.setBrush(area)
            painter.drawPath(fill)
            stroke = QColor(self._accent)
            stroke.setAlpha(190)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(stroke, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(line)

        cursor_x = chart.left() + chart.width() * self.value() / max(1, self.maximum())
        cursor = QColor(self._accent)
        cursor.setAlpha(235)
        painter.setPen(QPen(cursor, 1.3))
        painter.drawLine(QPointF(cursor_x, chart.top()), QPointF(cursor_x, chart.bottom()))
        painter.end()


class _LivingScene(QWidget):
    """A deterministic, inexpensive contour that moves at a gentle beat rate."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAccessibleName("Living Canvas musical fingerprint")
        self.profile: VisualProfile | None = None
        self._accent = QColor("#7eb4ff")
        self._playing = False
        self._window_minimized = False
        self._position_fraction = 0.0
        self._phase = 0.0
        self._last_tick: float | None = None
        self._stars: tuple[tuple[float, float, float, float], ...] = ()
        self._timer = QTimer(self)
        self._timer.setInterval(67)  # approximately 15 frames per second
        self._timer.timeout.connect(self._advance)

    def set_profile(self, profile: VisualProfile) -> None:
        self.profile = profile
        self._phase = 0.0
        rng = random.Random(profile.seed)
        self._stars = tuple(
            (rng.random(), rng.random(), rng.uniform(0.6, 1.8), rng.uniform(0.0, math.tau))
            for _ in range(14)
        )
        self.update()

    def set_accent_color(self, color: QColor) -> None:
        self._accent = QColor(color)
        self.update()

    def set_position_fraction(self, fraction: float) -> None:
        self._position_fraction = max(0.0, min(1.0, float(fraction)))
        self.update()

    def set_playing(self, playing: bool) -> None:
        self._playing = bool(playing)
        self._sync_timer()

    def set_window_minimized(self, minimized: bool) -> None:
        self._window_minimized = bool(minimized)
        self._sync_timer()

    def _sync_timer(self) -> None:
        should_run = self._playing and self.isVisible() and not self._window_minimized
        if should_run and not self._timer.isActive():
            self._last_tick = time.monotonic()
            self._timer.start()
        elif not should_run and self._timer.isActive():
            self._timer.stop()
            self._last_tick = None

    def _advance(self) -> None:
        now = time.monotonic()
        if self._last_tick is None:
            self._last_tick = now
        elapsed = max(0.0, min(0.2, now - self._last_tick))
        self._last_tick = now
        bpm = self.profile.bpm if self.profile else 96.0
        self._phase = (self._phase + elapsed * math.tau * bpm / 60.0) % math.tau
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        self._last_tick = None
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#10151c"))
        profile = self.profile
        if profile is None:
            painter.setPen(QColor("#8f9aaa"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Play a track to give it a place in the canvas.")
            painter.end()
            return

        rect = self.rect().adjusted(12, 10, -12, -10)
        center = QPointF(rect.center())
        base_radius = min(rect.width(), rect.height()) * 0.31
        energy = energy_at(profile, self._position_fraction)
        accent = QColor(self._accent)
        if accent.hue() < 0:
            accent = QColor.fromHsv(profile.hue, 180, 235)
        hue = accent.hue()
        secondary = QColor.fromHsv((hue + 42 + int(profile.brightness * 55)) % 360, 165, 238)
        seed_phase = (profile.seed % 10000) / 10000.0 * math.tau

        glow = QColor(accent)
        glow.setAlpha(16 + int(32 * energy))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, base_radius * 1.42, base_radius * 1.12)

        side_count = 48
        for layer in range(3):
            path = QPainterPath()
            layer_scale = 0.62 + layer * 0.18
            for index in range(side_count + 1):
                angle = math.tau * index / side_count
                contour = energy_at(profile, index / side_count) - 0.5
                lobes = (
                    0.12 * profile.rhythm * math.sin(angle * (5 + layer) + seed_phase)
                    + 0.09 * profile.brightness * math.sin(angle * 3.0 - seed_phase * 0.7)
                    + 0.10 * contour
                    + 0.035 * math.sin(self._phase + angle * 2.0 + layer)
                )
                radius = base_radius * layer_scale * (0.91 + lobes)
                x = center.x() + math.cos(angle + seed_phase * 0.08) * radius
                y = center.y() + math.sin(angle + seed_phase * 0.08) * radius * 0.78
                if index == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            path.closeSubpath()
            color = QColor(accent if layer != 1 else secondary)
            color.setAlpha(82 + layer * 34)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(color, 1.0 + layer * 0.55, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)

        painter.setPen(Qt.NoPen)
        for index, (x_seed, y_seed, size, phase) in enumerate(self._stars):
            orbit = base_radius * (0.85 + 0.37 * y_seed)
            angle = x_seed * math.tau + self._phase * 0.018
            x = center.x() + math.cos(angle) * orbit
            y = center.y() + math.sin(angle) * orbit * 0.70
            twinkle = 0.5 + 0.5 * math.sin(self._phase * (0.5 + profile.rhythm) + phase)
            dot = QColor(secondary if index % 3 == 0 else accent)
            dot.setAlpha(90 + int(135 * twinkle))
            painter.setBrush(dot)
            painter.drawEllipse(QPointF(x, y), size + twinkle * 0.8, size + twinkle * 0.8)

        core = QColor(accent)
        core.setAlpha(70 + int(95 * energy))
        painter.setBrush(core)
        painter.drawEllipse(center, base_radius * (0.11 + energy * 0.04), base_radius * (0.11 + energy * 0.04))
        painter.end()


class LivingCanvasView(QWidget):
    """Now Playing panel combining a stable visual identity with a seekable contour."""

    seekRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._track: dict[str, Any] = {}
        self._profile: VisualProfile | None = None
        self._duration_ms = 0
        self._syncing_slider = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        heading = QHBoxLayout()
        title = QLabel("Every song has a place")
        title.setStyleSheet("font-size:20px;font-weight:700")
        heading.addWidget(title)
        heading.addStretch(1)
        layout.addLayout(heading)

        self.track_label = QLabel("Waiting for music")
        self.track_label.setStyleSheet("font-size:13px;color:#c8ccd2")
        self.track_label.setWordWrap(True)
        layout.addWidget(self.track_label)

        self.scene = _LivingScene(self)
        layout.addWidget(self.scene, 1)

        self.status = QLabel("The same track returns to the same visual fingerprint.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#8f9aaa;font-size:11px")
        layout.addWidget(self.status)

        self.journey = EnergyJourneySlider(self)
        self.journey.valueChanged.connect(self._slider_value_changed)
        self.journey.sliderReleased.connect(self._emit_seek)
        layout.addWidget(self.journey)

        times = QHBoxLayout()
        self.position_label = QLabel("0:00")
        self.duration_label = QLabel("0:00")
        self.duration_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.position_label.setStyleSheet("color:#aab0ba;font-size:11px")
        self.duration_label.setStyleSheet("color:#aab0ba;font-size:11px")
        times.addWidget(self.position_label)
        times.addStretch(1)
        times.addWidget(self.duration_label)
        layout.addLayout(times)

    def set_track(self, track: dict[str, Any], analysis: Any = None) -> None:
        self._track = dict(track or {})
        self._profile = build_visual_profile(self._track, analysis)
        self.scene.set_profile(self._profile)
        self.journey.set_curve(self._profile.energy_curve)
        title = self._profile.title or "Unknown track"
        artist = self._profile.artist or "Unknown artist"
        self.track_label.setText(f"{artist}  ·  {title}")
        if self._profile.energy_curve:
            note = "Cached Flow contour · repeatable track fingerprint"
        elif self._profile.flow_available:
            note = "Cached Flow fingerprint · section contour is unavailable"
        else:
            note = "Identity fingerprint only · analyse this track in Play for me for its Flow contour"
        self.status.setText(note)
        duration = self._track.get("duration")
        try:
            if duration is None and self._track.get("duration_ms") is not None:
                self._duration_ms = max(0, int(float(self._track.get("duration_ms") or 0)))
            else:
                self._duration_ms = max(0, int(float(duration or 0) * 1000))
        except (TypeError, ValueError, OverflowError):
            self._duration_ms = 0
        self.set_position(0, self._duration_ms)

    def set_accent_color(self, color: QColor) -> None:
        self.scene.set_accent_color(color)
        self.journey.set_accent_color(color)

    def set_playing(self, playing: bool) -> None:
        self.scene.set_playing(playing)

    def set_window_minimized(self, minimized: bool) -> None:
        self.scene.set_window_minimized(minimized)

    def set_position(self, position_ms: int, duration_ms: int | None = None) -> None:
        if duration_ms is not None and duration_ms > 0:
            self._duration_ms = int(duration_ms)
        duration = self._duration_ms
        position = max(0, int(position_ms))
        if duration > 0:
            position = min(position, duration)
            fraction = position / duration
            self.position_label.setText(_time_label(position))
            self.duration_label.setText(_time_label(duration))
            self.scene.set_position_fraction(fraction)
            if not self.journey.isSliderDown():
                self._syncing_slider = True
                self.journey.set_fraction(fraction)
                self._syncing_slider = False
        else:
            self.position_label.setText(_time_label(position))
            self.duration_label.setText("0:00")
            self.scene.set_position_fraction(0.0)

    def _slider_value_changed(self, _value: int) -> None:
        if self._syncing_slider or self.journey.isSliderDown():
            return
        self._emit_seek()

    def _emit_seek(self) -> None:
        if self._duration_ms <= 0:
            return
        position = int(self._duration_ms * self.journey.value() / max(1, self.journey.maximum()))
        self.seekRequested.emit(position)
