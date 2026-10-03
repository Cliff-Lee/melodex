"""Bounded QPainter scenes for built-in and declarative Melodex visualizers."""

from __future__ import annotations

import math
import random
import time
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QMouseEvent,
    QPolygonF, QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from .visualization_models import LyricFrame, MemoryMark, VisualNeighbour, describe_weather
from .visualization_profile import VisualProfile, energy_at
from .visualization_runtime import VisualState, resolve_visual_quality, sample_visual_state
from .visualizer_plugins import VisualizerRecipe


class LivingScene(QWidget):
    """One renderer for the built-in modes and bounded `.mdxviz` recipes."""

    neighbourSelected = Signal(int)
    neighbourActivated = Signal(int)
    qualityAdjusted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("Melodex Living Canvas scene")
        self.setAccessibleDescription(
            "A track-aware musical scene. In Constellation mode, use the arrow keys to select a nearby track and Enter to queue it."
        )
        self.profile: VisualProfile | None = None
        self.mode = "living"
        self.plugin: VisualizerRecipe | None = None
        self._accent = QColor("#7eb4ff")
        self._palette: tuple[QColor, ...] = ()
        self._playing = False
        self._window_minimized = False
        self._position_fraction = 0.0
        self._phase = 0.0
        self._visual_state = VisualState.idle()
        self._last_tick: float | None = None
        self._stars: tuple[tuple[float, float, float, float], ...] = ()
        self._neighbours: tuple[VisualNeighbour, ...] = ()
        self._memory: tuple[MemoryMark, ...] = ()
        self._memory_scale = "sessions"
        self._lyrics = LyricFrame("", "", "", False, "")
        self._requested_quality = "auto"
        self._effective_quality = "normal"
        self._slow_frames = 0
        self._fast_frames = 0
        self._hit_points: tuple[tuple[QPointF, int, str], ...] = ()
        self._hovered_token: int | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(67)
        self._timer.timeout.connect(self._advance)

    @property
    def animated_mode(self) -> bool:
        if self.mode in {"living", "album_world", "weather", "constellation"}:
            return True
        if self.mode == "plugin" and self.plugin:
            return any(layer.get("speed", 0) > 0 for layer in self.plugin.layers)
        return False

    def set_profile(self, profile: VisualProfile) -> None:
        self.profile = profile
        self._phase = 0.0
        self._refresh_visual_state()
        rng = random.Random(profile.seed)
        self._stars = tuple(
            (rng.random(), rng.random(), rng.uniform(0.6, 1.8), rng.uniform(0.0, math.tau))
            for _ in range(24)
        )
        if not self._palette:
            self._palette = self._fallback_palette()
        self.update()
        self._sync_timer()

    def set_mode(self, mode: str, plugin: VisualizerRecipe | None = None) -> None:
        self.mode = mode
        self.plugin = plugin
        self._hovered_token = None
        self._hit_points = ()
        self.update()
        self._sync_timer()

    def set_accent_color(self, color: QColor) -> None:
        self._accent = QColor(color)
        self._palette = self._fallback_palette()
        self.update()

    def set_palette(self, colors: tuple[str, ...] | list[str]) -> None:
        parsed: list[QColor] = []
        for value in colors[:6]:
            color = QColor(str(value))
            if color.isValid():
                parsed.append(color)
        self._palette = tuple(parsed) or self._fallback_palette()
        self.update()

    def set_position_fraction(self, fraction: float) -> None:
        self._position_fraction = max(0.0, min(1.0, float(fraction)))
        self._refresh_visual_state()
        position_sensitive = self.mode in {"journey", "minimal"} or (
            self.mode == "plugin" and self.plugin and any(
                layer.get("feature") == "progress" for layer in self.plugin.layers
            )
        )
        if position_sensitive and not self.animated_mode:
            self.update()

    def set_neighbours(self, neighbours: tuple[VisualNeighbour, ...] | list[VisualNeighbour]) -> None:
        self._neighbours = tuple(neighbours[:24])
        self.update()

    def set_memory(self, marks: tuple[MemoryMark, ...] | list[MemoryMark], scale: str = "sessions") -> None:
        self._memory = tuple(marks[:128])
        self._memory_scale = str(scale or "sessions")
        self.update()

    def set_lyrics(self, frame: LyricFrame) -> None:
        value = frame if isinstance(frame, LyricFrame) else LyricFrame("", "", "", False, "")
        if value != self._lyrics:
            self._lyrics = value
            self.update()

    def set_quality(self, quality: str) -> None:
        value = quality if quality in {"auto", "eco", "high", "battery"} else "auto"
        self._requested_quality = value
        self._effective_quality = "eco" if value == "eco" else "normal"
        self._slow_frames = self._fast_frames = 0
        budget = resolve_visual_quality(value, self._effective_quality)
        self._timer.setInterval(budget.timer_interval_ms)
        self.update()
        self._sync_timer()

    def set_playing(self, playing: bool) -> None:
        self._playing = bool(playing)
        self._sync_timer()

    def set_window_minimized(self, minimized: bool) -> None:
        self._window_minimized = bool(minimized)
        self._sync_timer()

    def _fallback_palette(self) -> tuple[QColor, ...]:
        hue = self._accent.hue()
        if hue < 0:
            hue = self.profile.hue if self.profile else 210
        return tuple(
            QColor.fromHsv((hue + offset) % 360, saturation, value)
            for offset, saturation, value in (
                (0, 175, 238), (38, 165, 232), (205, 150, 222),
                (300, 135, 208), (116, 145, 214), (260, 110, 238),
            )
        )

    def _color(self, index: int) -> QColor:
        palette = self._palette or self._fallback_palette()
        return QColor(palette[index % len(palette)])

    def _sync_timer(self) -> None:
        should_run = (
            self._playing and self.isVisible() and not self._window_minimized
            and self._requested_quality != "battery" and self.animated_mode
        )
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
        self._refresh_visual_state()
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        self._last_tick = None
        super().hideEvent(event)

    @property
    def visual_state(self) -> VisualState:
        """Current renderer-facing musical state; safe for all built-in scenes."""
        return self._visual_state

    def _refresh_visual_state(self) -> None:
        self._visual_state = sample_visual_state(
            self.profile,
            self._position_fraction,
            self._phase,
        )

    def _detail_count(self, default: int) -> int:
        budget = resolve_visual_quality(self._requested_quality, self._effective_quality)
        scaled = int(round(default * budget.detail_scale))
        return max(3, min(budget.max_detail, scaled))

    def paintEvent(self, event) -> None:
        started = time.perf_counter()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        profile = self.profile
        self._paint_backdrop(painter, profile)
        if profile is None:
            painter.setPen(QColor("#aab0ba"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Play a track to give it a place in the canvas.")
            painter.end()
            return

        if self.mode == "living":
            self._paint_living(painter, profile)
        elif self.mode == "fingerprint":
            self._paint_fingerprint(painter, profile)
        elif self.mode == "journey":
            self._paint_journey(painter, profile)
        elif self.mode == "constellation":
            self._paint_constellation(painter, profile)
        elif self.mode == "lyrics":
            self._paint_lyrics(painter)
        elif self.mode == "album_world":
            self._paint_album_world(painter, profile)
        elif self.mode == "weather":
            self._paint_weather(painter, profile)
        elif self.mode == "memory":
            self._paint_memory(painter)
        elif self.mode == "minimal":
            self._paint_minimal(painter, profile)
        elif self.mode == "plugin" and self.plugin:
            self._paint_plugin(painter, profile)
        painter.end()
        self._adjust_auto_quality((time.perf_counter() - started) * 1000.0)

    def _adjust_auto_quality(self, paint_ms: float) -> None:
        if self._requested_quality != "auto":
            return
        if paint_ms > 18.0:
            self._slow_frames += 1
            self._fast_frames = 0
        elif paint_ms < 8.0:
            self._fast_frames += 1
            self._slow_frames = 0
        else:
            self._slow_frames = self._fast_frames = 0
        if self._slow_frames >= 3 and self._effective_quality != "eco":
            self._effective_quality = "eco"
            self._slow_frames = 0
            self.qualityAdjusted.emit("eco")
            self.update()
        elif self._fast_frames >= 90 and self._effective_quality != "normal":
            self._effective_quality = "normal"
            self._fast_frames = 0
            self.qualityAdjusted.emit("normal")
            self.update()

    def _paint_backdrop(self, painter: QPainter, profile: VisualProfile | None) -> None:
        bounds = QRectF(self.rect())
        base = QLinearGradient(bounds.topLeft(), bounds.bottomRight())
        base.setColorAt(0.0, QColor("#121a25"))
        base.setColorAt(0.48, QColor("#0d131c"))
        base.setColorAt(1.0, QColor("#111925"))
        painter.fillRect(bounds, base)

        if profile is not None:
            color = self._color(0)
            color.setAlpha(27)
            fade = QColor(color)
            fade.setAlpha(0)
            glow = QRadialGradient(
                QPointF(bounds.width() * 0.49, bounds.height() * 0.46),
                max(bounds.width(), bounds.height()) * 0.66,
            )
            glow.setColorAt(0.0, color)
            glow.setColorAt(0.52, QColor(color.red(), color.green(), color.blue(), 9))
            glow.setColorAt(1.0, fade)
            painter.fillRect(bounds, glow)

            # A few quiet, deterministic dust points give the canvas depth without
            # adding any moving particles or per-frame scene state.
            painter.setPen(Qt.NoPen)
            for index, (x, y, size, _phase) in enumerate(self._stars[:18]):
                mote = self._color(index + 1)
                mote.setAlpha(18 + (index % 3) * 3)
                painter.setBrush(mote)
                px = bounds.left() + x * bounds.width()
                py = bounds.top() + y * bounds.height()
                painter.drawEllipse(QPointF(px, py), min(1.3, size * 0.62), min(1.3, size * 0.62))

        edge = QColor("#334052")
        edge.setAlpha(130)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(edge, 1.0))
        painter.drawRoundedRect(bounds.adjusted(0.5, 0.5, -0.5, -0.5), 16, 16)

    def _area(self) -> QRectF:
        return QRectF(self.rect()).adjusted(30, 24, -30, -24)

    @staticmethod
    def _draw_caption(
        painter: QPainter,
        rect: QRectF,
        text: str,
        color: QColor | str = "#a8b5c5",
        alignment=Qt.AlignCenter,
    ) -> None:
        painter.save()
        font = QFont("sans-serif", 9, QFont.DemiBold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
        font.setItalic(False)
        font.setStyle(QFont.StyleNormal)
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(rect, alignment, text)
        painter.restore()

    @staticmethod
    def _draw_glow(painter: QPainter, center: QPointF, radius: float, color: QColor, strength: int = 34) -> None:
        glow_color = QColor(color)
        glow_color.setAlpha(strength)
        transparent = QColor(color)
        transparent.setAlpha(0)
        brush = QRadialGradient(center, max(1.0, radius))
        brush.setColorAt(0.0, glow_color)
        middle = QColor(color)
        middle.setAlpha(max(1, strength // 3))
        brush.setColorAt(0.62, middle)
        brush.setColorAt(1.0, transparent)
        painter.setPen(Qt.NoPen)
        painter.setBrush(brush)
        painter.drawEllipse(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2))

    def _paint_living(self, painter: QPainter, profile: VisualProfile) -> None:
        rect = self._area()
        center = rect.center()
        base = min(rect.width(), rect.height()) * 0.35
        energy = energy_at(profile, self._position_fraction)
        seed_phase = profile.hue / 360.0 * math.tau
        glow = self._color(0)
        self._draw_glow(painter, center, base * (1.6 + energy * 0.12), glow, 32 + int(22 * energy))
        orbit = self._color(0)
        orbit.setAlpha(24)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(orbit, 1.0, Qt.DashLine))
        painter.drawEllipse(center, base * 1.16, base * 0.93)
        painter.setPen(QPen(QColor(orbit.red(), orbit.green(), orbit.blue(), 82), 1.0))
        for index in range(48):
            angle = math.tau * index / 48
            inner = base * 1.105
            outer = base * (1.15 if index % 6 == 0 else 1.125)
            painter.drawLine(
                QPointF(center.x() + math.cos(angle) * inner, center.y() + math.sin(angle) * inner * 0.80),
                QPointF(center.x() + math.cos(angle) * outer, center.y() + math.sin(angle) * outer * 0.80),
            )
        points = self._detail_count(48)
        layers = 2 if self._requested_quality == "eco" or self._effective_quality == "eco" else 3
        for layer in range(layers):
            path = QPainterPath()
            scale = 0.66 + layer * 0.17
            for index in range(points + 1):
                angle = math.tau * index / points
                contour = energy_at(profile, index / points) - 0.5
                lobe = (
                    0.12 * profile.rhythm * math.sin(angle * (5 + layer) + seed_phase)
                    + 0.09 * profile.brightness * math.sin(angle * 3.0 - seed_phase * 0.7)
                    + 0.10 * contour
                    + 0.035 * math.sin(self._phase + angle * 2.0 + layer)
                )
                radius = base * scale * (0.91 + lobe)
                point = QPointF(center.x() + math.cos(angle) * radius, center.y() + math.sin(angle) * radius * 0.78)
                if index == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
            path.closeSubpath()
            color = self._color(0 if layer != 1 else 1)
            color.setAlpha(90 + layer * 26)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(color, 1.0 + layer * 0.55, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)
        painter.setPen(Qt.NoPen)
        halo = QColor(self._color(0))
        halo.setAlpha(34 + int(28 * energy))
        painter.setBrush(halo)
        painter.drawEllipse(center, base * (0.16 + energy * 0.04), base * (0.16 + energy * 0.04))
        for index, (sx, sy, size, phase) in enumerate(self._stars[: self._detail_count(14)]):
            angle = sx * math.tau + self._phase * 0.018
            orbit = base * (0.88 + 0.36 * sy)
            x = center.x() + math.cos(angle) * orbit
            y = center.y() + math.sin(angle) * orbit * 0.72
            twinkle = 0.5 + 0.5 * math.sin(self._phase * (0.5 + profile.rhythm) + phase)
            dot = self._color(index % 3)
            dot.setAlpha(80 + int(145 * twinkle))
            painter.setBrush(dot)
            painter.drawEllipse(QPointF(x, y), size + twinkle * 0.7, size + twinkle * 0.7)
        core = self._color(0)
        core.setAlpha(70 + int(100 * energy))
        painter.setBrush(core)
        painter.drawEllipse(center, base * (0.09 + energy * 0.045), base * (0.09 + energy * 0.045))
        center_dot = QColor("#eaf4ff")
        center_dot.setAlpha(145)
        painter.setBrush(center_dot)
        painter.drawEllipse(center, 2.1, 2.1)

    def _paint_fingerprint(self, painter: QPainter, profile: VisualProfile) -> None:
        rect = self._area()
        center = rect.center()
        radius = min(rect.width(), rect.height()) * 0.34
        seed_phase = (profile.seed % 10007) / 10007.0 * math.tau
        points = self._detail_count(64)
        self._draw_glow(painter, center, radius * 1.35, self._color(0), 23)
        for layer in range(4):
            path = QPainterPath()
            for i in range(points + 1):
                angle = math.tau * i / points
                contour = energy_at(profile, i / points) - 0.5
                harmonic = math.sin(angle * (3 + layer * 2) + seed_phase * (layer + 1))
                second = math.cos(angle * (7 + int(profile.rhythm * 5)) - seed_phase)
                r = radius * (0.64 + layer * 0.105 + 0.12 * harmonic * profile.rhythm + 0.06 * second * profile.brightness + 0.06 * contour)
                point = QPointF(center.x() + math.cos(angle) * r, center.y() + math.sin(angle) * r)
                if i == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
            path.closeSubpath()
            color = self._color(layer)
            color.setAlpha(72 + layer * 35)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(color, 1.1 + layer * 0.35, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)
        painter.setPen(QPen(QColor(self._color(4).red(), self._color(4).green(), self._color(4).blue(), 74), 1.0))
        painter.drawEllipse(center, radius * 0.10, radius * 0.10)
        for index in range(72):
            angle = math.tau * index / 72
            inner = radius * 1.17
            outer = radius * (1.23 if index % 6 == 0 else 1.195)
            painter.drawLine(
                QPointF(center.x() + math.cos(angle) * inner, center.y() + math.sin(angle) * inner),
                QPointF(center.x() + math.cos(angle) * outer, center.y() + math.sin(angle) * outer),
            )
        label = profile.fingerprint[:12].upper()
        self._draw_caption(
            painter,
            QRectF(rect.left(), rect.bottom() - 26, rect.width(), 18),
            f"TRACK SIGIL   ·   {label}",
        )

    def _paint_journey(self, painter: QPainter, profile: VisualProfile) -> None:
        rect = self._area()
        baseline = rect.bottom() - rect.height() * 0.16
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            x_tick = rect.left() + rect.width() * fraction
            guide = QColor("#99a8ba")
            guide.setAlpha(34 if fraction not in (0.0, 1.0) else 24)
            painter.setPen(QPen(guide, 1.0, Qt.DotLine))
            painter.drawLine(QPointF(x_tick, rect.top() + 6), QPointF(x_tick, baseline))
        painter.setPen(QPen(QColor("#718096"), 1.0))
        painter.drawLine(QPointF(rect.left(), baseline), QPointF(rect.right(), baseline))
        if len(profile.energy_curve) < 2:
            painter.setPen(QColor("#aab0ba"))
            painter.drawText(rect, Qt.AlignCenter, "No cached Flow contour yet\nThe position slider remains available below.")
            return
        points = min(64, len(profile.energy_curve))
        sampled: list[QPointF] = []
        for i in range(points):
            fraction = i / max(1, points - 1)
            value = energy_at(profile, fraction)
            x = rect.left() + rect.width() * fraction
            y = baseline - (rect.height() * 0.68) * value
            sampled.append(QPointF(x, y))
        path = QPainterPath(sampled[0])
        fill = QPainterPath(QPointF(sampled[0].x(), baseline))
        fill.lineTo(sampled[0])
        for index in range(1, len(sampled) - 1):
            midpoint = QPointF(
                (sampled[index].x() + sampled[index + 1].x()) * 0.5,
                (sampled[index].y() + sampled[index + 1].y()) * 0.5,
            )
            path.quadTo(sampled[index], midpoint)
            fill.quadTo(sampled[index], midpoint)
        path.lineTo(sampled[-1])
        fill.lineTo(sampled[-1])
        fill.lineTo(rect.right(), baseline)
        fill.closeSubpath()
        fill_color = self._color(0)
        fill_color.setAlpha(24)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill_color)
        painter.drawPath(fill)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(self._color(0), 2.3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        x = rect.left() + rect.width() * self._position_fraction
        value = energy_at(profile, self._position_fraction)
        y = baseline - (rect.height() * 0.68) * value
        guide = QColor(self._color(1))
        guide.setAlpha(74)
        painter.setPen(QPen(guide, 1.0))
        painter.drawLine(QPointF(x, rect.top() + 8), QPointF(x, baseline))
        self._draw_glow(painter, QPointF(x, y), 18.0, self._color(1), 38)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color(1))
        painter.drawEllipse(QPointF(x, y), 5.5, 5.5)
        painter.setPen(QPen(QColor("#eef5ff"), 1.2))
        painter.setBrush(self._color(1))
        painter.drawEllipse(QPointF(x, y), 3.6, 3.6)
        self._draw_caption(
            painter,
            QRectF(rect.left(), rect.bottom() - 22, rect.width(), 18),
            "PAST     ·     NOW     ·     WHAT'S AHEAD",
        )

    def _paint_constellation(self, painter: QPainter, profile: VisualProfile) -> None:
        rect = self._area()
        center = rect.center()
        self._hit_points = ()
        for scale in (0.34, 0.62):
            guide = QColor(self._color(0))
            guide.setAlpha(18)
            painter.setPen(QPen(guide, 1.0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(
                QRectF(
                    center.x() - rect.width() * scale * 0.5,
                    center.y() - rect.height() * scale * 0.5,
                    rect.width() * scale,
                    rect.height() * scale,
                )
            )
        if not self._neighbours:
            painter.setPen(QColor("#aab0ba"))
            painter.drawText(rect, Qt.AlignCenter, "This track is the centre.\nQueue or hear more music to grow its constellation.")
            return
        hit: list[tuple[QPointF, int, str]] = []
        positions: dict[int, QPointF] = {}
        for node in self._neighbours:
            point = QPointF(rect.left() + rect.width() * node.x, rect.top() + rect.height() * node.y)
            positions[node.token] = point
            color = self._relation_color(node.relation)
            pen = QColor(color)
            pen.setAlpha(52)
            painter.setPen(QPen(pen, 1.0))
            painter.drawLine(center, point)
        current = self._color(0)
        current.setAlpha(220)
        painter.setPen(Qt.NoPen)
        halo = QColor(current)
        halo.setAlpha(35)
        painter.setBrush(halo)
        painter.drawEllipse(center, 19, 19)
        rim = QColor(current)
        rim.setAlpha(115)
        painter.setPen(QPen(rim, 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, 13, 13)
        painter.setPen(Qt.NoPen)
        painter.setBrush(current)
        painter.drawEllipse(center, 9, 9)
        for index, node in enumerate(self._neighbours):
            point = positions[node.token]
            color = self._relation_color(node.relation)
            pulse = 0.5 + 0.5 * math.sin(self._phase + index * 1.7)
            size = (6.0 + 2.0 * pulse) if node.token != self._hovered_token else 10.0
            halo = QColor(color)
            halo.setAlpha(28)
            painter.setPen(Qt.NoPen)
            painter.setBrush(halo)
            painter.drawEllipse(point, size * 2.2, size * 2.2)
            color.setAlpha(200)
            outline = QColor("#eaf3ff")
            outline.setAlpha(185 if node.token == self._hovered_token else 68)
            painter.setPen(QPen(outline, 1.2 if node.token == self._hovered_token else 0.7))
            painter.setBrush(color)
            painter.drawEllipse(point, size, size)
            hit.append((point, node.token, f"{node.artist} — {node.title} · {node.relation}"))
            if node.token == self._hovered_token:
                chip = QRectF(rect.center().x() - 190, rect.bottom() - 41, 380, 30)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(8, 12, 18, 205))
                painter.drawRoundedRect(chip, 12, 12)
                self._draw_caption(
                    painter,
                    chip.adjusted(10, 0, -10, 0),
                    f"{node.artist}  ·  {node.title}  ·  {node.relation}  ·  DOUBLE-CLICK TO QUEUE",
                    "#edf4ff",
                )
        self._hit_points = tuple(hit)

    def _relation_color(self, relation: str) -> QColor:
        if relation == "Up next":
            return self._color(1)
        if relation == "Played earlier":
            return self._color(2)
        if relation == "Same album":
            return self._color(3)
        if relation == "Same artist":
            return self._color(4)
        return self._color(5)

    def _paint_lyrics(self, painter: QPainter) -> None:
        rect = self._area()
        if not self._lyrics.current and not self._lyrics.following:
            painter.setPen(QColor("#aab0ba"))
            painter.drawText(rect, Qt.AlignCenter, "No local lyrics are available.\nAdd embedded lyrics or a .lrc / .txt sidecar to the track.")
            return
        edge = QColor(self._color(0))
        edge.setAlpha(48)
        painter.setPen(QPen(edge, 1.0))
        painter.drawLine(QPointF(rect.left() + rect.width() * 0.31, rect.top() + rect.height() * 0.27), QPointF(rect.right() - rect.width() * 0.31, rect.top() + rect.height() * 0.27))
        painter.drawLine(QPointF(rect.left() + rect.width() * 0.31, rect.bottom() - rect.height() * 0.25), QPointF(rect.right() - rect.width() * 0.31, rect.bottom() - rect.height() * 0.25))
        painter.save()
        painter.setFont(QFont("sans-serif", 13, QFont.Normal))
        painter.setPen(QColor(190, 199, 212, 120))
        painter.drawText(QRectF(rect.left() + 20, rect.top() + rect.height() * 0.12, rect.width() - 40, 56), Qt.AlignCenter | Qt.TextWordWrap, self._lyrics.previous)
        current = self._lyrics.current or "…"
        painter.setFont(QFont("sans-serif", 22, QFont.DemiBold))
        active = QColor(self._color(0))
        active.setAlpha(244)
        painter.setPen(active)
        painter.drawText(QRectF(rect.left() + 32, rect.center().y() - 66, rect.width() - 64, 132), Qt.AlignCenter | Qt.TextWordWrap, current)
        painter.setFont(QFont("sans-serif", 13, QFont.Normal))
        painter.setPen(QColor(190, 199, 212, 120))
        painter.drawText(QRectF(rect.left() + 20, rect.bottom() - rect.height() * 0.25, rect.width() - 40, 56), Qt.AlignCenter | Qt.TextWordWrap, self._lyrics.following)
        painter.restore()
        label = "SYNCED LOCAL LYRICS" if self._lyrics.synced else "UNTIMED LYRICS · PACED ACROSS THE TRACK"
        self._draw_caption(painter, QRectF(rect.left(), rect.bottom() - 20, rect.width(), 16), label)

    def _paint_album_world(self, painter: QPainter, profile: VisualProfile) -> None:
        rect = self._area()
        center = rect.center()
        energy = energy_at(profile, self._position_fraction)
        base = min(rect.width(), rect.height()) * 0.34
        painter.setPen(Qt.NoPen)
        glow = self._color(0)
        glow.setAlpha(17 + int(22 * energy))
        painter.setBrush(glow)
        painter.drawEllipse(center, base * 1.7, base * 1.3)
        points = self._detail_count(48)
        for band in range(7):
            path = QPainterPath()
            offset = (band - 3) * rect.height() * 0.085
            for i in range(points + 1):
                x_fraction = i / points
                x = rect.left() + rect.width() * x_fraction
                amp = rect.height() * (0.025 + 0.035 * profile.energy + band * 0.002)
                wave = (
                    math.sin(x_fraction * (4.0 + profile.rhythm * 8.0) + band + self._phase * 0.11) * amp
                    + math.sin(x_fraction * 9.0 - band * 0.7 + profile.hue) * amp * 0.35
                )
                y = center.y() + offset + wave - rect.height() * (profile.brightness - 0.5) * 0.08
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            color = self._color(band)
            color.setAlpha(110 if band % 2 else 80)
            painter.setPen(QPen(color, 1.0 + (band % 3) * 0.45, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
        progress_x = rect.left() + rect.width() * self._position_fraction
        progress = QColor(self._color(0))
        progress.setAlpha(80)
        painter.setPen(QPen(progress, 1.0, Qt.DashLine))
        painter.drawLine(QPointF(progress_x, rect.top() + 14), QPointF(progress_x, rect.bottom() - 31))
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color(0))
        painter.drawEllipse(QPointF(progress_x, center.y()), 3.3, 3.3)
        self._draw_caption(
            painter,
            QRectF(rect.left(), rect.bottom() - 22, rect.width(), 18),
            "ALBUM WORLD    ·    COVER-COLOUR PALETTE",
        )

    def _paint_weather(self, painter: QPainter, profile: VisualProfile) -> None:
        weather = describe_weather(profile)
        rect = self._area()
        center = QPointF(rect.center().x(), rect.center().y() - rect.height() * 0.16)
        radius = min(rect.width(), rect.height()) * 0.23
        self._draw_glow(painter, QPointF(center.x(), center.y() + radius * 0.42), radius * 2.15, self._color(0), 25)
        shadow = QColor("#070b11")
        shadow.setAlpha(74)
        painter.setPen(Qt.NoPen)
        painter.setBrush(shadow)
        painter.drawEllipse(QPointF(center.x(), center.y() + radius * 0.44), radius * 1.22, radius * 0.23)

        cloud_path = QPainterPath()
        cloud_path.moveTo(center.x() - radius * 1.34, center.y() + radius * 0.27)
        cloud_path.cubicTo(
            center.x() - radius * 1.52, center.y() - radius * 0.10,
            center.x() - radius * 1.17, center.y() - radius * 0.48,
            center.x() - radius * 0.72, center.y() - radius * 0.39,
        )
        cloud_path.cubicTo(
            center.x() - radius * 0.50, center.y() - radius * 0.96,
            center.x() + radius * 0.34, center.y() - radius * 1.00,
            center.x() + radius * 0.57, center.y() - radius * 0.32,
        )
        cloud_path.cubicTo(
            center.x() + radius * 1.06, center.y() - radius * 0.58,
            center.x() + radius * 1.55, center.y() - radius * 0.22,
            center.x() + radius * 1.37, center.y() + radius * 0.28,
        )
        cloud_path.cubicTo(
            center.x() + radius * 1.23, center.y() + radius * 0.50,
            center.x() - radius * 1.14, center.y() + radius * 0.50,
            center.x() - radius * 1.34, center.y() + radius * 0.27,
        )
        cloud = self._color(0)
        cloud.setAlpha(173)
        cloud_highlight = QColor(cloud)
        cloud_highlight.setAlpha(210)
        cloud_shade = QColor(cloud)
        cloud_shade.setAlpha(116)
        cloud_gradient = QLinearGradient(center.x(), center.y() - radius, center.x(), center.y() + radius * 0.55)
        cloud_gradient.setColorAt(0.0, cloud_highlight)
        cloud_gradient.setColorAt(1.0, cloud_shade)
        outline = QColor("#e5f1ff")
        outline.setAlpha(58)
        painter.setPen(QPen(outline, 1.0))
        painter.setBrush(cloud_gradient)
        painter.drawPath(cloud_path)
        energy = profile.energy
        marks = self._detail_count(10)
        color = self._color(1 if profile.brightness > 0.58 else 3)
        color.setAlpha(155)
        painter.setPen(QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap))
        if profile.rhythm > 0.56:
            for i in range(marks):
                x = center.x() - radius + (i + 0.5) * radius * 2 / marks
                drift = math.sin(self._phase * 0.7 + i * 1.9) * 5
                y = center.y() + radius * 0.76 + (i % 3) * 12 + drift
                painter.drawLine(QPointF(x, y), QPointF(x - 5, y + 10 + energy * 7))
        else:
            for i in range(marks):
                angle = math.tau * i / marks + self._phase * 0.018
                x = center.x() + math.cos(angle) * radius * 1.28
                y = center.y() + math.sin(angle) * radius * 0.82
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(QPointF(x, y), 2.0 + energy, 2.0 + energy)
        painter.save()
        painter.setFont(QFont("sans-serif", 17, QFont.DemiBold))
        painter.setPen(QColor("#edf3fb"))
        painter.drawText(QRectF(rect.left(), center.y() + radius * 1.47, rect.width(), 32), Qt.AlignCenter, f"{weather.tone}  ·  {weather.density}")
        painter.restore()
        self._draw_caption(painter, QRectF(rect.left(), center.y() + radius * 1.47 + 30, rect.width(), 24), weather.motion.upper())
        if not weather.based_on_flow:
            self._draw_caption(
                painter,
                QRectF(rect.left(), rect.bottom() - 20, rect.width(), 16),
                "IDENTITY-BASED ESTIMATE    ·    NO CACHED FLOW ANALYSIS",
                "#8491a1",
            )

    def _paint_memory(self, painter: QPainter) -> None:
        rect = self._area()
        if not self._memory:
            painter.setPen(QColor("#aab0ba"))
            painter.drawText(rect, Qt.AlignCenter, "Your listening atlas starts here.\nMelodex uses the listening history already stored on this device.")
            return
        line_y = rect.bottom() - rect.height() * 0.20
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            tick_x = rect.left() + rect.width() * fraction
            guide = QColor("#9badc4")
            guide.setAlpha(25)
            painter.setPen(QPen(guide, 1.0, Qt.DotLine))
            painter.drawLine(QPointF(tick_x, rect.top() + 12), QPointF(tick_x, line_y))
        painter.setPen(QPen(QColor("#596778"), 1.0))
        painter.drawLine(QPointF(rect.left(), line_y), QPointF(rect.right(), line_y))
        ordered = sorted(self._memory, key=lambda mark: mark.x)
        if len(ordered) > 1:
            path = QPainterPath()
            first = QPointF(
                rect.left() + rect.width() * max(0.0, min(1.0, ordered[0].x)),
                rect.top() + rect.height() * max(0.0, min(0.78, ordered[0].y)),
            )
            path.moveTo(first)
            for index in range(1, len(ordered)):
                previous = ordered[index - 1]
                current = ordered[index]
                start = QPointF(
                    rect.left() + rect.width() * max(0.0, min(1.0, previous.x)),
                    rect.top() + rect.height() * max(0.0, min(0.78, previous.y)),
                )
                end = QPointF(
                    rect.left() + rect.width() * max(0.0, min(1.0, current.x)),
                    rect.top() + rect.height() * max(0.0, min(0.78, current.y)),
                )
                midpoint = QPointF((start.x() + end.x()) * 0.5, (start.y() + end.y()) * 0.5)
                path.quadTo(start, midpoint)
            last = ordered[-1]
            path.lineTo(
                rect.left() + rect.width() * max(0.0, min(1.0, last.x)),
                rect.top() + rect.height() * max(0.0, min(0.78, last.y)),
            )
            guide = QColor(self._color(0))
            guide.setAlpha(28)
            painter.setPen(QPen(guide, 1.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)
        for index, mark in enumerate(self._memory):
            x = rect.left() + rect.width() * max(0.0, min(1.0, mark.x))
            y = rect.top() + rect.height() * max(0.0, min(0.78, mark.y))
            color = QColor.fromHsv(mark.hue, 155, 238)
            size = min(22.0, 5.0 + math.sqrt(max(1, mark.count)) * 2.4)
            color.setAlpha(115 + min(100, mark.count * 3))
            painter.setPen(QPen(color, 1.0))
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 32))
            painter.drawEllipse(QPointF(x, y), size, size)
            if index % max(1, len(self._memory) // 12) == 0:
                label_y = y + size + 5 if index % 2 == 0 else y - size - 22
                label_color = QColor("#e0e8f3")
                label_color.setAlpha(224)
                painter.setPen(label_color)
                font = QFont("sans-serif", 9, QFont.Medium)
                font.setItalic(False)
                painter.setFont(font)
                painter.drawText(QRectF(x - 62, label_y, 124, 18), Qt.AlignHCenter | Qt.AlignVCenter, mark.label[:21])
        self._draw_caption(
            painter,
            QRectF(rect.left(), rect.bottom() - 18, rect.width(), 16),
            f"LOCAL LISTENING ATLAS    ·    {self._memory_scale.upper()}    ·    {len(self._memory)} MARKS",
        )

    def _paint_minimal(self, painter: QPainter, profile: VisualProfile) -> None:
        rect = self._area()
        center = rect.center()
        size = min(rect.width(), rect.height()) * 0.25
        base = self._color(0)
        self._draw_glow(painter, center, size * 1.75, base, 28)
        painter.setPen(Qt.NoPen)
        for index in range(60):
            angle = math.tau * index / 60
            inner = size * 1.27
            outer = size * (1.36 if index % 5 == 0 else 1.31)
            tick = QColor(self._color(0))
            tick.setAlpha(54 if index % 5 == 0 else 22)
            painter.setPen(QPen(tick, 1.0))
            painter.drawLine(
                QPointF(center.x() + math.cos(angle) * inner, center.y() + math.sin(angle) * inner),
                QPointF(center.x() + math.cos(angle) * outer, center.y() + math.sin(angle) * outer),
            )
        accent = self._color(0)
        accent.setAlpha(210)
        painter.setPen(QPen(accent, 2.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, size, size)
        accent.setAlpha(55)
        painter.setPen(QPen(accent, 1.0))
        painter.drawEllipse(center, size * 1.11, size * 1.11)
        accent.setAlpha(220)
        painter.setPen(QPen(accent, 2.5, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(QRectF(center.x() - size * 1.11, center.y() - size * 1.11, size * 2.22, size * 2.22), 90 * 16, -int(360 * self._position_fraction * 16))
        angle = math.pi / 2 - math.tau * self._position_fraction
        dot = QPointF(center.x() + math.cos(angle) * size * 1.11, center.y() - math.sin(angle) * size * 1.11)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#eef5ff"))
        painter.drawEllipse(dot, 3.1, 3.1)
        self._draw_caption(
            painter,
            QRectF(rect.left(), rect.bottom() - 24, rect.width(), 18),
            f"{profile.fingerprint[:12].upper()}    ·    {profile.bpm:.0f} BPM",
        )

    def _paint_plugin(self, painter: QPainter, profile: VisualProfile) -> None:
        assert self.plugin is not None
        rect = self._area()
        center = rect.center()
        base = min(rect.width(), rect.height()) * 0.36
        for layer in self.plugin.layers:
            kind = layer["type"]
            count = layer["count"]
            gain = layer["gain"]
            feature = layer["feature"]
            speed = layer["speed"]
            color = self._color(layer["palette"])
            reactivity = self._feature(profile, feature)
            phase = self._phase * speed
            alpha = 68 + int(130 * reactivity)
            color.setAlpha(alpha)
            painter.setBrush(Qt.NoBrush)
            if kind == "rings":
                for index in range(count):
                    r = base * (0.18 + 0.72 * (index + 1) / count) * (1.0 + gain * reactivity)
                    painter.setPen(QPen(color, 1.0 + gain * 3.0))
                    painter.drawEllipse(center, r, r * (0.66 + 0.12 * profile.brightness))
            elif kind == "contour":
                points = self._detail_count(48)
                for layer_index in range(count):
                    path = QPainterPath()
                    for i in range(points + 1):
                        angle = math.tau * i / points
                        wave = math.sin(angle * (4 + layer_index * 2) + phase) * gain * reactivity
                        r = base * (0.38 + 0.11 * layer_index + wave)
                        point = QPointF(center.x() + math.cos(angle + phase * 0.1) * r, center.y() + math.sin(angle + phase * 0.1) * r * 0.8)
                        if i == 0:
                            path.moveTo(point)
                        else:
                            path.lineTo(point)
                    path.closeSubpath()
                    painter.setPen(QPen(color, 1.0 + layer_index * 0.35, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    painter.drawPath(path)
            elif kind == "orbit":
                painter.setPen(Qt.NoPen)
                for index in range(count):
                    angle = math.tau * index / count + phase
                    r = base * (0.40 + 0.46 * ((index % 4) / 3.0))
                    point = QPointF(center.x() + math.cos(angle) * r, center.y() + math.sin(angle) * r * 0.72)
                    painter.setBrush(color)
                    radius = 1.8 + gain * 7.0 * reactivity + (index % 3) * 0.5
                    painter.drawEllipse(point, radius, radius)
            elif kind == "terrain":
                points = self._detail_count(48)
                for band in range(count):
                    path = QPainterPath()
                    offset = band * rect.height() * 0.09
                    for i in range(points + 1):
                        frac = i / points
                        x = rect.left() + rect.width() * frac
                        y = center.y() + offset + math.sin(frac * 8 + phase + band) * rect.height() * (0.02 + gain * reactivity)
                        if i == 0:
                            path.moveTo(x, y)
                        else:
                            path.lineTo(x, y)
                    painter.setPen(QPen(color, 1.0 + band * 0.25, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    painter.drawPath(path)
            elif kind == "glyphs":
                painter.setPen(QPen(color, 1.2))
                for index in range(count):
                    angle = math.tau * index / count + phase
                    orbit = base * (0.30 + gain * reactivity + 0.45 * ((index % 3) / 2.0))
                    point = QPointF(center.x() + math.cos(angle) * orbit, center.y() + math.sin(angle) * orbit * 0.8)
                    r = 3.0 + gain * 8.0 * reactivity
                    for spoke in range(4):
                        theta = angle + spoke * math.pi / 4
                        painter.drawLine(QPointF(point.x() - math.cos(theta) * r, point.y() - math.sin(theta) * r), QPointF(point.x() + math.cos(theta) * r, point.y() + math.sin(theta) * r))
        self._draw_caption(painter, QRectF(rect.left(), rect.bottom() - 20, rect.width(), 16), self.plugin.name.upper())

    def _feature(self, profile: VisualProfile, name: str) -> float:
        if name == "brightness":
            return profile.brightness
        if name == "rhythm":
            return profile.rhythm
        if name == "progress":
            return self._position_fraction
        if name == "tempo":
            return max(0.0, min(1.0, (profile.bpm - 40.0) / 180.0))
        return profile.energy

    def _hit_test(self, point: QPointF) -> tuple[int, str] | None:
        for center, token, label in self._hit_points:
            if math.hypot(point.x() - center.x(), point.y() - center.y()) <= 20:
                return token, label
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self.mode == "constellation":
            found = self._hit_test(event.position())
            if found:
                token, label = found
                self._hovered_token = token
                self.setToolTip(label + " — double-click to queue")
                self.neighbourSelected.emit(token)
                self.update()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self.mode == "constellation":
            found = self._hit_test(event.position())
            if found:
                self.neighbourActivated.emit(found[0])
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        if self.mode == "constellation" and self._neighbours:
            if event.key() in {Qt.Key_Right, Qt.Key_Down, Qt.Key_Tab}:
                current = next((i for i, node in enumerate(self._neighbours) if node.token == self._hovered_token), -1)
                node = self._neighbours[(current + 1) % len(self._neighbours)]
                self._hovered_token = node.token
                self.neighbourSelected.emit(node.token)
                self.update()
                event.accept()
                return
            if event.key() in {Qt.Key_Left, Qt.Key_Up, Qt.Key_Backtab}:
                current = next((i for i, node in enumerate(self._neighbours) if node.token == self._hovered_token), 0)
                node = self._neighbours[(current - 1) % len(self._neighbours)]
                self._hovered_token = node.token
                self.neighbourSelected.emit(node.token)
                self.update()
                event.accept()
                return
            if event.key() in {Qt.Key_Return, Qt.Key_Enter} and self._hovered_token is not None:
                self.neighbourActivated.emit(self._hovered_token)
                event.accept()
                return
        super().keyPressEvent(event)
