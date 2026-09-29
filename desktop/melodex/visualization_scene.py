"""Bounded QPainter scenes for built-in and declarative Melodex visualizers."""

from __future__ import annotations

import math
import random
import time
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QMouseEvent, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from .visualization_models import LyricFrame, MemoryMark, VisualNeighbour, describe_weather
from .visualization_profile import VisualProfile, energy_at
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
        interval = {"auto": 67, "eco": 100, "high": 34, "battery": 1000}[value]
        self._timer.setInterval(interval)
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
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        self._last_tick = None
        super().hideEvent(event)

    def _detail_count(self, default: int) -> int:
        if self._requested_quality == "eco" or self._effective_quality == "eco":
            return max(3, default // 2)
        if self._requested_quality == "high":
            return min(48, default * 2)
        return default

    def paintEvent(self, event) -> None:
        started = time.perf_counter()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#10151c"))
        profile = self.profile
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

    def _area(self) -> QRectF:
        return QRectF(self.rect()).adjusted(20, 18, -20, -18)

    def _paint_living(self, painter: QPainter, profile: VisualProfile) -> None:
        rect = self._area()
        center = rect.center()
        base = min(rect.width(), rect.height()) * 0.32
        energy = energy_at(profile, self._position_fraction)
        seed_phase = profile.hue / 360.0 * math.tau
        glow = self._color(0)
        glow.setAlpha(14 + int(36 * energy))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, base * 1.44, base * 1.12)
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
        painter.drawEllipse(center, base * (0.10 + energy * 0.05), base * (0.10 + energy * 0.05))

    def _paint_fingerprint(self, painter: QPainter, profile: VisualProfile) -> None:
        rect = self._area()
        center = rect.center()
        radius = min(rect.width(), rect.height()) * 0.35
        seed_phase = (profile.seed % 10007) / 10007.0 * math.tau
        points = self._detail_count(64)
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
        painter.setPen(QPen(self._color(4), 1.0))
        painter.drawEllipse(center, radius * 0.10, radius * 0.10)
        label = profile.fingerprint[:12].upper()
        painter.setPen(QColor("#aab0ba"))
        painter.drawText(QRectF(rect.left(), rect.bottom() - 28, rect.width(), 22), Qt.AlignCenter, f"TRACK SIGIL  ·  {label}")

    def _paint_journey(self, painter: QPainter, profile: VisualProfile) -> None:
        rect = self._area()
        baseline = rect.bottom() - rect.height() * 0.16
        painter.setPen(QPen(QColor("#35404d"), 1.0))
        painter.drawLine(QPointF(rect.left(), baseline), QPointF(rect.right(), baseline))
        if len(profile.energy_curve) < 2:
            painter.setPen(QColor("#aab0ba"))
            painter.drawText(rect, Qt.AlignCenter, "No cached Flow contour yet\nThe position slider remains available below.")
            return
        points = min(64, len(profile.energy_curve))
        path = QPainterPath()
        fill = QPainterPath()
        for i in range(points):
            fraction = i / max(1, points - 1)
            value = energy_at(profile, fraction)
            x = rect.left() + rect.width() * fraction
            y = baseline - (rect.height() * 0.68) * value
            if i == 0:
                path.moveTo(x, y)
                fill.moveTo(x, baseline)
                fill.lineTo(x, y)
            else:
                path.lineTo(x, y)
                fill.lineTo(x, y)
        fill.lineTo(rect.right(), baseline)
        fill.closeSubpath()
        fill_color = self._color(0)
        fill_color.setAlpha(24)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill_color)
        painter.drawPath(fill)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(self._color(0), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        x = rect.left() + rect.width() * self._position_fraction
        value = energy_at(profile, self._position_fraction)
        y = baseline - (rect.height() * 0.68) * value
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color(1))
        painter.drawEllipse(QPointF(x, y), 6, 6)
        painter.setPen(QColor("#9aa5b3"))
        painter.drawText(QRectF(rect.left(), rect.bottom() - 22, rect.width(), 18), Qt.AlignCenter, "PAST  →  PRESENT POSITION  →  WHAT'S AHEAD")

    def _paint_constellation(self, painter: QPainter, profile: VisualProfile) -> None:
        rect = self._area()
        center = rect.center()
        self._hit_points = ()
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
        painter.setBrush(current)
        painter.drawEllipse(center, 9, 9)
        for index, node in enumerate(self._neighbours):
            point = positions[node.token]
            color = self._relation_color(node.relation)
            pulse = 0.5 + 0.5 * math.sin(self._phase + index * 1.7)
            size = (6.0 + 2.0 * pulse) if node.token != self._hovered_token else 10.0
            color.setAlpha(200)
            painter.setPen(QPen(QColor("#dfe8f5"), 1.0 if node.token == self._hovered_token else 0.0))
            painter.setBrush(color)
            painter.drawEllipse(point, size, size)
            hit.append((point, node.token, f"{node.artist} — {node.title} · {node.relation}"))
            if node.token == self._hovered_token:
                painter.setPen(QColor("#e8edf5"))
                painter.drawText(QRectF(rect.left(), rect.bottom() - 30, rect.width(), 24), Qt.AlignCenter, f"{node.artist} — {node.title}  ·  {node.relation}  ·  double-click to queue")
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
        painter.setPen(QColor(180, 190, 204, 100))
        painter.drawText(QRectF(rect.left() + 20, rect.top() + rect.height() * 0.18, rect.width() - 40, 46), Qt.AlignCenter, self._lyrics.previous)
        current = self._lyrics.current or "…"
        painter.setPen(self._color(0))
        painter.drawText(QRectF(rect.left() + 20, rect.center().y() - 52, rect.width() - 40, 104), Qt.AlignCenter | Qt.TextWordWrap, current)
        painter.setPen(QColor(180, 190, 204, 100))
        painter.drawText(QRectF(rect.left() + 20, rect.bottom() - rect.height() * 0.25, rect.width() - 40, 46), Qt.AlignCenter, self._lyrics.following)
        painter.setPen(QColor("#8793a1"))
        label = "SYNCED LOCAL LYRICS" if self._lyrics.synced else "UNTIMED LYRICS · PACED ACROSS THE TRACK"
        painter.drawText(QRectF(rect.left(), rect.bottom() - 20, rect.width(), 16), Qt.AlignCenter, label)

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
        painter.setPen(QColor("#aab0ba"))
        painter.drawText(QRectF(rect.left(), rect.bottom() - 22, rect.width(), 18), Qt.AlignCenter, "DETERMINISTIC ALBUM WORLD  ·  COVER-COLOUR PALETTE")

    def _paint_weather(self, painter: QPainter, profile: VisualProfile) -> None:
        weather = describe_weather(profile)
        rect = self._area()
        center = QPointF(rect.center().x(), rect.center().y() - rect.height() * 0.11)
        radius = min(rect.width(), rect.height()) * 0.21
        cloud = self._color(0)
        cloud.setAlpha(110)
        painter.setPen(Qt.NoPen)
        painter.setBrush(cloud)
        painter.drawEllipse(QPointF(center.x() - radius * 0.65, center.y()), radius * 0.54, radius * 0.45)
        painter.drawEllipse(QPointF(center.x(), center.y() - radius * 0.22), radius * 0.67, radius * 0.58)
        painter.drawEllipse(QPointF(center.x() + radius * 0.68, center.y()), radius * 0.50, radius * 0.43)
        energy = profile.energy
        marks = self._detail_count(10)
        color = self._color(1 if profile.brightness > 0.58 else 3)
        color.setAlpha(145)
        painter.setPen(QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap))
        if profile.rhythm > 0.56:
            for i in range(marks):
                x = center.x() - radius + (i + 0.5) * radius * 2 / marks
                drift = math.sin(self._phase * 0.7 + i * 1.9) * 8
                y = center.y() + radius * 0.9 + (i % 3) * 11 + drift
                painter.drawLine(QPointF(x, y), QPointF(x - 5, y + 12 + energy * 6))
        else:
            for i in range(marks):
                angle = math.tau * i / marks + self._phase * 0.018
                x = center.x() + math.cos(angle) * radius * 1.28
                y = center.y() + math.sin(angle) * radius * 0.82
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(QPointF(x, y), 2.0 + energy, 2.0 + energy)
        painter.setPen(QColor("#e6ebf2"))
        painter.drawText(QRectF(rect.left(), center.y() + radius * 1.45, rect.width(), 32), Qt.AlignCenter, f"{weather.tone}  ·  {weather.density}")
        painter.setPen(QColor("#9ba6b4"))
        painter.drawText(QRectF(rect.left(), center.y() + radius * 1.45 + 30, rect.width(), 24), Qt.AlignCenter, weather.motion)
        if not weather.based_on_flow:
            painter.setPen(QColor("#808b99"))
            painter.drawText(QRectF(rect.left(), rect.bottom() - 20, rect.width(), 16), Qt.AlignCenter, "IDENTITY-BASED ESTIMATE · NO CACHED FLOW ANALYSIS")

    def _paint_memory(self, painter: QPainter) -> None:
        rect = self._area()
        if not self._memory:
            painter.setPen(QColor("#aab0ba"))
            painter.drawText(rect, Qt.AlignCenter, "Your listening atlas starts here.\nMelodex uses the listening history already stored on this device.")
            return
        line_y = rect.bottom() - rect.height() * 0.20
        painter.setPen(QPen(QColor("#46515e"), 1.0))
        painter.drawLine(QPointF(rect.left(), line_y), QPointF(rect.right(), line_y))
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
                painter.setPen(QColor("#d6dce5"))
                painter.drawText(QRectF(x - 65, y + size + 5, 130, 20), Qt.AlignHCenter | Qt.AlignTop, mark.label[:24])
        painter.setPen(QColor("#8f9aaa"))
        painter.drawText(QRectF(rect.left(), rect.bottom() - 18, rect.width(), 16), Qt.AlignCenter, f"LOCAL LISTENING ATLAS  ·  {self._memory_scale.upper()}  ·  {len(self._memory)} MARKS")

    def _paint_minimal(self, painter: QPainter, profile: VisualProfile) -> None:
        rect = self._area()
        center = rect.center()
        size = min(rect.width(), rect.height()) * 0.24
        base = self._color(0)
        base.setAlpha(40)
        painter.setPen(Qt.NoPen)
        painter.setBrush(base)
        painter.drawEllipse(center, size * 1.45, size * 1.45)
        accent = self._color(0)
        accent.setAlpha(210)
        painter.setPen(QPen(accent, 2.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, size, size)
        painter.drawArc(QRectF(center.x() - size * 1.15, center.y() - size * 1.15, size * 2.3, size * 2.3), 90 * 16, -int(360 * self._position_fraction * 16))
        painter.setPen(QColor("#8793a1"))
        painter.drawText(QRectF(rect.left(), rect.bottom() - 24, rect.width(), 18), Qt.AlignCenter, f"{profile.fingerprint[:12].upper()}  ·  {profile.bpm:.0f} BPM")

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
        painter.setPen(QColor("#8f9aaa"))
        painter.drawText(QRectF(rect.left(), rect.bottom() - 20, rect.width(), 16), Qt.AlignCenter, self.plugin.name.upper())

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
