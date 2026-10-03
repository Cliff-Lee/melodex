"""Bounded QPainter scenes for built-in and declarative Melodex visualizers."""

from __future__ import annotations

import math
import random
import time
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QMouseEvent,
    QPolygonF, QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from .track_sigil import paint_track_sigil
from .visualization_models import LyricFrame, MemoryMark, VisualNeighbour, describe_weather
from .visualization_profile import VisualProfile, energy_at
from .visualization_runtime import (
    VisualPerformanceGovernor,
    VisualState,
    resolve_visual_quality,
    sample_visual_state,
)
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
        self._memory_hit_points: tuple[tuple[QPointF, int, float], ...] = ()
        self._hovered_memory_index: int | None = None
        self._selected_memory_index: int | None = None
        self._memory_cache = QImage()
        self._lyrics = LyricFrame("", "", "", False, "")
        self._previous_lyrics = self._lyrics
        self._lyric_transition = 1.0
        self._artwork_source = QImage()
        self._artwork_cache = QImage()
        self._immersive = False
        self._requested_quality = "auto"
        self._effective_quality = "normal"
        self._performance = VisualPerformanceGovernor()
        self._frame_glows = 0
        self._hit_points: tuple[tuple[QPointF, int, str], ...] = ()
        self._hovered_token: int | None = None
        self._selected_token: int | None = None
        self._neighbour_artwork: dict[int, QImage] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(67)
        self._timer.timeout.connect(self._advance)

    @property
    def animated_mode(self) -> bool:
        if self.mode in {"living", "album_world", "weather", "constellation", "lyrics"}:
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
        self._selected_token = None
        self._hit_points = ()
        self._hovered_memory_index = None
        self._selected_memory_index = None
        self._memory_hit_points = ()
        self._memory_cache = QImage()
        self.update()
        self._sync_timer()

    def set_immersive(self, immersive: bool) -> None:
        self._immersive = bool(immersive)
        self.update()

    def set_artwork(self, path: str) -> None:
        image = QImage(str(path or ""))
        if image.isNull():
            self._artwork_source = QImage()
        else:
            # Deliberately downsample once.  Scaling this soft source back to the
            # scene gives the atmospheric artwork wash without a live blur pass.
            self._artwork_source = image.scaled(
                72,
                72,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
        self._artwork_cache = QImage()
        self.update()

    def set_accent_color(self, color: QColor) -> None:
        self._accent = QColor(color)
        self._palette = self._fallback_palette()
        self._memory_cache = QImage()
        self.update()

    def set_palette(self, colors: tuple[str, ...] | list[str]) -> None:
        parsed: list[QColor] = []
        for value in colors[:6]:
            color = QColor(str(value))
            if color.isValid():
                parsed.append(color)
        self._palette = tuple(parsed) or self._fallback_palette()
        self._memory_cache = QImage()
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
        valid = {node.token for node in self._neighbours}
        if self._hovered_token not in valid:
            self._hovered_token = None
        if self._selected_token not in valid:
            self._selected_token = None
        self._neighbour_artwork = {
            token: image
            for token, image in self._neighbour_artwork.items()
            if token in valid
        }
        self.update()

    def set_neighbour_artwork(self, token: int, path: str) -> None:
        token = int(token)
        if token not in {node.token for node in self._neighbours}:
            return
        image = QImage(str(path or ""))
        if image.isNull():
            self._neighbour_artwork.pop(token, None)
        else:
            self._neighbour_artwork[token] = image.scaled(
                112,
                112,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
        self.update()

    def set_memory(self, marks: tuple[MemoryMark, ...] | list[MemoryMark], scale: str = "sessions") -> None:
        self._memory = tuple(marks[:128])
        self._memory_scale = str(scale or "sessions")
        self._hovered_memory_index = None
        self._selected_memory_index = None
        self._memory_hit_points = ()
        self.update()

    def set_lyrics(self, frame: LyricFrame) -> None:
        value = frame if isinstance(frame, LyricFrame) else LyricFrame("", "", "", False, "")
        if value != self._lyrics:
            if value.index != self._lyrics.index or value.current != self._lyrics.current:
                self._previous_lyrics = self._lyrics
                self._lyric_transition = 0.0
            self._lyrics = value
            self.update()
            self._sync_timer()

    def set_quality(self, quality: str) -> None:
        value = quality if quality in {"auto", "eco", "high", "battery"} else "auto"
        self._requested_quality = value
        self._effective_quality = "eco" if value == "eco" else "normal"
        self._performance.reset(self._effective_quality)
        self._artwork_cache = QImage()
        budget = self._quality_budget()
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
        if self._lyric_transition < 1.0:
            self._lyric_transition = min(1.0, self._lyric_transition + elapsed / 0.38)
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

    def _quality_budget(self):
        return resolve_visual_quality(self._requested_quality, self._effective_quality)

    @property
    def performance_stats(self) -> dict[str, float | int | str]:
        return self._performance.snapshot()

    def _detail_count(self, default: int) -> int:
        budget = self._quality_budget()
        scaled = int(round(default * budget.detail_scale))
        return max(3, min(budget.max_detail, scaled))

    def _particle_count(self, default: int) -> int:
        budget = self._quality_budget()
        scaled = int(round(default * budget.detail_scale))
        return max(1, min(budget.max_particles, scaled))

    def paintEvent(self, event) -> None:
        started = time.perf_counter()
        self._frame_glows = 0
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
        transition = self._performance.observe(paint_ms, self._requested_quality)
        if transition is None:
            return
        self._effective_quality = transition
        self._artwork_cache = QImage()
        self._timer.setInterval(self._quality_budget().timer_interval_ms)
        self.qualityAdjusted.emit(transition)
        self.update()

    def _paint_backdrop(self, painter: QPainter, profile: VisualProfile | None) -> None:
        bounds = QRectF(self.rect())
        base = QLinearGradient(bounds.topLeft(), bounds.bottomRight())
        base.setColorAt(0.0, QColor("#121a25"))
        base.setColorAt(0.48, QColor("#0d131c"))
        base.setColorAt(1.0, QColor("#111925"))
        painter.fillRect(bounds, base)

        if self.mode == "lyrics" and not self._artwork_source.isNull():
            size = self.size()
            budget = self._quality_budget()
            width = max(1, size.width())
            height = max(1, size.height())
            largest = max(width, height)
            scale = min(1.0, budget.artwork_cache_px / max(1, largest))
            cache_width = max(1, int(round(width * scale)))
            cache_height = max(1, int(round(height * scale)))
            if (
                self._artwork_cache.isNull()
                or self._artwork_cache.width() != cache_width
                or self._artwork_cache.height() != cache_height
            ):
                self._artwork_cache = self._artwork_source.scaled(
                    cache_width,
                    cache_height,
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation,
                )
            painter.save()
            painter.setOpacity(0.20 + 0.06 * self._visual_state.glow)
            painter.drawImage(bounds, self._artwork_cache)
            painter.setOpacity(1.0)
            painter.fillRect(bounds, QColor(4, 9, 17, 178))
            painter.restore()

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
            for index, (x, y, size, _phase) in enumerate(
                self._stars[: self._particle_count(18)]
            ):
                mote = self._color(index + 1)
                mote.setAlpha(18 + (index % 3) * 3)
                painter.setBrush(mote)
                px = bounds.left() + x * bounds.width()
                py = bounds.top() + y * bounds.height()
                painter.drawEllipse(QPointF(px, py), min(1.3, size * 0.62), min(1.3, size * 0.62))

        if not self._immersive:
            edge = QColor("#334052")
            edge.setAlpha(130)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(edge, 1.0))
            painter.drawRoundedRect(bounds.adjusted(0.5, 0.5, -0.5, -0.5), 16, 16)

    def _area(self) -> QRectF:
        margin_x = 64 if self._immersive else 30
        margin_y = 46 if self._immersive else 24
        return QRectF(self.rect()).adjusted(margin_x, margin_y, -margin_x, -margin_y)

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

    def _draw_glow(
        self,
        painter: QPainter,
        center: QPointF,
        radius: float,
        color: QColor,
        strength: int = 34,
    ) -> None:
        budget = self._quality_budget()
        if self._frame_glows >= budget.max_glows:
            return
        self._frame_glows += 1

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
        painter.drawEllipse(
            QRectF(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2,
            )
        )

    def _paint_living(self, painter: QPainter, profile: VisualProfile) -> None:
        """Profile Pulse: a low-cost radial portrait that breathes with the track."""

        rect = self._area()
        center = rect.center()
        state = self._visual_state
        base = min(rect.width(), rect.height()) * 0.34
        points = self._detail_count(56)
        seed_phase = (profile.seed % 10007) / 10007.0 * math.tau

        # A broad luminous field replaces the old radar/tick-ring appearance.
        field = QColor(self._color(0))
        self._draw_glow(
            painter,
            center,
            base * (1.35 + 0.12 * state.energy),
            field,
            24 + int(34 * state.glow),
        )
        secondary = QColor(self._color(1))
        secondary_center = QPointF(
            center.x() + math.cos(seed_phase) * base * 0.18,
            center.y() + math.sin(seed_phase) * base * 0.12,
        )
        self._draw_glow(
            painter,
            secondary_center,
            base * 0.92,
            secondary,
            9 + int(16 * state.brightness),
        )

        layer_count = 2 if self._requested_quality == "eco" or self._effective_quality == "eco" else 4
        for layer in range(layer_count):
            path = QPainterPath()
            layer_fraction = layer / max(1, layer_count - 1)
            layer_radius = base * (0.48 + 0.13 * layer)
            phase_offset = seed_phase * (0.55 + 0.22 * layer) + self._phase * (0.025 + 0.012 * layer)
            for index in range(points + 1):
                angle = math.tau * index / points
                contour = energy_at(profile, index / points) - 0.5
                harmonic = math.sin(
                    angle * (3 + layer * 2)
                    + phase_offset
                )
                fine = math.cos(
                    angle * (7 + int(profile.rhythm * 5))
                    - seed_phase * 0.7
                )
                movement = math.sin(
                    angle * 2.0
                    - self._phase * (0.18 + 0.14 * state.rhythm)
                    + layer
                )
                lobe = (
                    0.105 * profile.rhythm * harmonic
                    + 0.070 * profile.brightness * fine
                    + 0.085 * contour
                    + 0.025 * state.drift * movement
                )
                breathing = 1.0 + 0.010 * state.glow + 0.006 * state.pulse
                radius = layer_radius * breathing * (1.0 + lobe)
                y_scale = 0.91 + 0.035 * math.sin(seed_phase + layer)
                point = QPointF(
                    center.x() + math.cos(angle) * radius,
                    center.y() + math.sin(angle) * radius * y_scale,
                )
                if index == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
            path.closeSubpath()

            color = QColor(self._color(layer))
            halo = QColor(color)
            halo.setAlpha(17 + int(16 * state.glow) + int(8 * layer_fraction))
            core = QColor(color)
            core.setAlpha(105 + int(60 * layer_fraction) + int(35 * state.energy))

            painter.setBrush(Qt.NoBrush)
            painter.setPen(
                QPen(
                    halo,
                    5.0 + 1.2 * layer_fraction,
                    Qt.SolidLine,
                    Qt.RoundCap,
                    Qt.RoundJoin,
                )
            )
            painter.drawPath(path)
            painter.setPen(
                QPen(
                    core,
                    1.15 + 0.55 * layer_fraction,
                    Qt.SolidLine,
                    Qt.RoundCap,
                    Qt.RoundJoin,
                )
            )
            painter.drawPath(path)

        # Sparse luminous motes orbit slowly around the profile rather than
        # looking like a fixed instrument scale.
        mote_count = self._particle_count(12)
        for index, (sx, sy, size, phase) in enumerate(self._stars[:mote_count]):
            angle = sx * math.tau + self._phase * (0.010 + profile.rhythm * 0.018)
            orbit = base * (0.78 + 0.44 * sy)
            x = center.x() + math.cos(angle) * orbit
            y = center.y() + math.sin(angle) * orbit * 0.88
            twinkle = 0.5 + 0.5 * math.sin(self._phase * 0.55 + phase + index)
            mote = QColor(self._color(index + 1))
            mote.setAlpha(34 + int(72 * twinkle))
            painter.setPen(Qt.NoPen)
            painter.setBrush(mote)
            painter.drawEllipse(QPointF(x, y), 0.9 + size * 0.45, 0.9 + size * 0.45)

        # The centre is the playback pulse: bright, small and deliberately calm.
        core_color = QColor(self._color(0))
        self._draw_glow(
            painter,
            center,
            base * (0.24 + 0.04 * state.energy),
            core_color,
            34 + int(40 * state.glow),
        )
        painter.setPen(Qt.NoPen)
        center_fill = QColor(core_color)
        center_fill.setAlpha(135 + int(85 * state.energy))
        painter.setBrush(center_fill)
        core_radius = base * (0.055 + 0.010 * state.pulse)
        painter.drawEllipse(center, core_radius, core_radius)
        painter.setBrush(QColor(248, 252, 255, 225))
        painter.drawEllipse(center, 2.2 + state.pulse * 0.8, 2.2 + state.pulse * 0.8)

        label = "PROFILE PULSE"
        if profile.flow_available:
            label += "   ·   FLOW-DRIVEN"
        else:
            label += "   ·   IDENTITY-DRIVEN"
        self._draw_caption(
            painter,
            QRectF(rect.left(), rect.bottom() - 18, rect.width(), 16),
            label,
            QColor(172, 190, 211, 150),
        )

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

    def _active_constellation_token(self) -> int | None:
        return self._hovered_token if self._hovered_token is not None else self._selected_token

    def _paint_constellation_card(
        self,
        painter: QPainter,
        rect: QRectF,
        point: QPointF,
        node: VisualNeighbour,
    ) -> None:
        width = min(360.0, max(286.0, rect.width() * 0.38))
        height = 116.0
        x = point.x() + 28.0
        if x + width > rect.right() - 8:
            x = point.x() - width - 28.0
        x = max(rect.left() + 8.0, min(x, rect.right() - width - 8.0))
        y = max(rect.top() + 8.0, min(point.y() - height * 0.52, rect.bottom() - height - 8.0))
        card = QRectF(x, y, width, height)

        leader_end = QPointF(card.left(), card.center().y()) if card.center().x() > point.x() else QPointF(card.right(), card.center().y())
        leader = QColor(self._relation_color(node.relation))
        leader.setAlpha(118)
        painter.setPen(QPen(leader, 1.1, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(point, leader_end)

        painter.setPen(QPen(QColor(114, 144, 178, 105), 1.0))
        painter.setBrush(QColor(7, 12, 20, 232))
        painter.drawRoundedRect(card, 15, 15)

        art_rect = QRectF(card.left() + 12, card.top() + 12, 92, 92)
        artwork = self._neighbour_artwork.get(node.token)
        if artwork is not None and not artwork.isNull():
            painter.save()
            clip = QPainterPath()
            clip.addRoundedRect(art_rect, 10, 10)
            painter.setClipPath(clip)
            painter.drawImage(art_rect, artwork)
            painter.restore()
        else:
            placeholder = QLinearGradient(art_rect.topLeft(), art_rect.bottomRight())
            color = QColor(self._relation_color(node.relation))
            muted = QColor(color)
            muted.setAlpha(72)
            deep = QColor(10, 18, 29, 255)
            placeholder.setColorAt(0.0, muted)
            placeholder.setColorAt(1.0, deep)
            painter.setPen(Qt.NoPen)
            painter.setBrush(placeholder)
            painter.drawRoundedRect(art_rect, 10, 10)
            painter.setFont(QFont("sans-serif", 26, QFont.Normal))
            painter.setPen(QColor(231, 240, 250, 185))
            painter.drawText(art_rect, Qt.AlignCenter, "♪")

        text_left = art_rect.right() + 14
        text_width = card.right() - text_left - 12

        painter.setFont(QFont("sans-serif", 13, QFont.DemiBold))
        painter.setPen(QColor("#f2f7fd"))
        painter.drawText(
            QRectF(text_left, card.top() + 13, text_width, 38),
            Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
            node.title or "Unknown track",
        )

        painter.setFont(QFont("sans-serif", 10, QFont.Medium))
        painter.setPen(QColor("#c2cfdd"))
        artist_album = node.artist or "Unknown artist"
        if node.album:
            artist_album += f"  ·  {node.album}"
        painter.drawText(
            QRectF(text_left, card.top() + 52, text_width, 26),
            Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
            artist_album,
        )

        relation = QColor(self._relation_color(node.relation))
        relation.setAlpha(235)
        painter.setFont(QFont("sans-serif", 9, QFont.DemiBold))
        painter.setPen(relation)
        painter.drawText(
            QRectF(text_left, card.bottom() - 29, text_width, 17),
            Qt.AlignLeft | Qt.AlignVCenter,
            node.relation.upper(),
        )
        painter.setFont(QFont("sans-serif", 8, QFont.Normal))
        painter.setPen(QColor(156, 171, 188, 165))
        painter.drawText(
            QRectF(text_left, card.bottom() - 16, text_width, 13),
            Qt.AlignLeft | Qt.AlignVCenter,
            "DOUBLE-CLICK TO QUEUE",
        )

    def _paint_constellation(self, painter: QPainter, profile: VisualProfile) -> None:
        rect = self._area()
        center = rect.center()
        self._hit_points = ()
        if not self._neighbours:
            self._draw_glow(painter, center, min(rect.width(), rect.height()) * 0.18, self._color(0), 32)
            painter.setPen(QColor("#b7c4d3"))
            painter.setFont(QFont("sans-serif", 14, QFont.Normal))
            painter.drawText(
                rect,
                Qt.AlignCenter,
                "This track is the centre.\nQueue or hear more music to grow its neighbourhood.",
            )
            return

        active_token = self._active_constellation_token()
        positions: dict[int, QPointF] = {}
        hit: list[tuple[QPointF, int, str]] = []
        for index, node in enumerate(self._neighbours):
            drift = 0.0 if self._requested_quality == "battery" else 1.7
            dx = math.sin(self._phase * 0.045 + index * 1.31) * drift
            dy = math.cos(self._phase * 0.038 + index * 1.79) * drift * 0.72
            positions[node.token] = QPointF(
                rect.left() + rect.width() * node.x + dx,
                rect.top() + rect.height() * node.y + dy,
            )

        # Recent listening becomes a faint journey trail instead of another
        # legend or axis. It is intentionally subordinate to relationship paths.
        past = [node for node in self._neighbours if node.relation == "Played earlier"]
        if len(past) >= 2:
            trail = QPainterPath(positions[past[0].token])
            for node in past[1:]:
                trail.lineTo(positions[node.token])
            trail_color = QColor(self._color(2))
            trail_color.setAlpha(26 if active_token is None else 14)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(trail_color, 1.0, Qt.DotLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(trail)

        # Curved paths communicate relationship strength. Hovering one star
        # illuminates its route and quiets unrelated routes.
        for index, node in enumerate(self._neighbours):
            point = positions[node.token]
            color = QColor(self._relation_color(node.relation))
            selected = node.token == active_token
            alpha = (170 + int(55 * node.strength)) if selected else int(24 + 54 * node.strength)
            if active_token is not None and not selected:
                alpha = max(12, alpha // 3)
            color.setAlpha(min(235, alpha))

            dx = point.x() - center.x()
            dy = point.y() - center.y()
            curve_sign = -1.0 if (node.token + index) % 2 else 1.0
            bend = (18.0 + 30.0 * (1.0 - node.strength)) * curve_sign
            length = max(1.0, math.hypot(dx, dy))
            nx, ny = -dy / length, dx / length
            c1 = QPointF(center.x() + dx * 0.36 + nx * bend, center.y() + dy * 0.36 + ny * bend)
            c2 = QPointF(center.x() + dx * 0.72 + nx * bend * 0.52, center.y() + dy * 0.72 + ny * bend * 0.52)
            path = QPainterPath(center)
            path.cubicTo(c1, c2, point)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(
                QPen(
                    color,
                    2.0 + node.strength * 0.9 if selected else 0.65 + node.strength * 0.75,
                    Qt.SolidLine,
                    Qt.RoundCap,
                    Qt.RoundJoin,
                )
            )
            painter.drawPath(path)

        state = self._visual_state
        current = QColor(self._color(0))
        self._draw_glow(
            painter,
            center,
            54 + 18 * state.glow,
            current,
            40 + int(28 * state.glow),
        )
        painter.setPen(Qt.NoPen)
        core_halo = QColor(current)
        core_halo.setAlpha(52 + int(38 * state.glow))
        painter.setBrush(core_halo)
        painter.drawEllipse(center, 20 + state.pulse * 2.4, 20 + state.pulse * 2.4)

        # The centre reuses the same deterministic Track Sigil geometry shown in
        # the header. Geometry is identity; glow/pulse is playback state.
        sigil_rect = QRectF(center.x() - 15, center.y() - 15, 30, 30)
        paint_track_sigil(
            painter,
            sigil_rect,
            profile.seed,
            current,
            glow=0.25 + 0.45 * state.glow,
            compact=True,
        )

        for index, node in enumerate(self._neighbours):
            point = positions[node.token]
            selected = node.token == active_token
            color = QColor(self._relation_color(node.relation))
            pulse = 0.5 + 0.5 * math.sin(self._phase * 0.62 + index * 1.47)
            size = 3.8 + node.strength * 4.3 + pulse * 0.65
            if selected:
                size += 2.4

            if selected:
                self._draw_glow(painter, point, size * 4.0, color, 42 + int(34 * state.glow))
            else:
                halo = QColor(color)
                halo.setAlpha(20 + int(20 * node.strength))
                painter.setPen(Qt.NoPen)
                painter.setBrush(halo)
                painter.drawEllipse(point, size * 2.0, size * 2.0)

            fill = QColor(color)
            fill.setAlpha(235 if selected else 176 + int(55 * node.strength))
            outline = QColor("#f0f6ff")
            outline.setAlpha(210 if selected else 88)
            painter.setPen(QPen(outline, 1.25 if selected else 0.7))
            painter.setBrush(fill)
            painter.drawEllipse(point, size, size)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(247, 251, 255, 215 if selected else 105))
            painter.drawEllipse(point, max(1.1, size * 0.22), max(1.1, size * 0.22))

            hit.append((point, node.token, f"{node.artist} — {node.title} · {node.relation}"))

        self._hit_points = tuple(hit)

        if active_token is not None:
            node = next((item for item in self._neighbours if item.token == active_token), None)
            if node is not None:
                self._paint_constellation_card(painter, rect, positions[node.token], node)

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

    @staticmethod
    def _ease_out_cubic(value: float) -> float:
        value = max(0.0, min(1.0, float(value)))
        return 1.0 - (1.0 - value) ** 3

    def _draw_glowing_text(
        self,
        painter: QPainter,
        box: QRectF,
        text: str,
        font: QFont,
        core: QColor,
        glow: QColor,
        strength: float,
    ) -> None:
        if not text:
            return
        painter.save()
        painter.setFont(font)
        all_offsets = (
            (-2, 0), (2, 0), (0, -2), (0, 2),
            (-2, -2), (2, -2), (-2, 2), (2, 2),
        )
        layer_count = self._quality_budget().glow_layers
        offset_count = min(len(all_offsets), max(2, layer_count * 2))
        offsets = all_offsets[:offset_count]
        halo = QColor(glow)
        halo.setAlpha(max(8, min(92, int(42 * strength))))
        for dx, dy in offsets:
            painter.setPen(halo)
            painter.drawText(
                box.translated(dx, dy),
                Qt.AlignCenter | Qt.TextWordWrap,
                text,
            )
        painter.setPen(core)
        painter.drawText(box, Qt.AlignCenter | Qt.TextWordWrap, text)
        painter.restore()

    def _paint_lyric_energy_line(self, painter: QPainter, rect: QRectF) -> None:
        profile = self.profile
        y_mid = rect.bottom() - (34 if self._immersive else 28)
        left = rect.left() + rect.width() * 0.15
        width = rect.width() * 0.70
        color = QColor(self._color(0))
        muted = QColor(color)
        muted.setAlpha(38)
        painter.setBrush(Qt.NoBrush)

        path = QPainterPath()
        if profile is not None and len(profile.energy_curve) >= 2:
            for index, value in enumerate(profile.energy_curve):
                x = left + width * index / max(1, len(profile.energy_curve) - 1)
                amplitude = (11 if self._immersive else 7) * (0.25 + 0.75 * value)
                phase = index * 0.72
                y = y_mid + math.sin(phase) * amplitude
                if index == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
        else:
            path.moveTo(left, y_mid)
            path.lineTo(left + width, y_mid)

        painter.setPen(QPen(muted, 1.1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        progress = max(0.0, min(1.0, self._position_fraction))
        cursor_x = left + width * progress
        active = QColor(color)
        active.setAlpha(150 + int(70 * self._visual_state.glow))
        painter.setPen(Qt.NoPen)
        painter.setBrush(active)
        painter.drawEllipse(QPointF(cursor_x, y_mid), 2.4, 2.4)

    def _paint_lyrics(self, painter: QPainter) -> None:
        rect = self._area()
        if not self._lyrics.current and not self._lyrics.following:
            painter.setPen(QColor("#b8c4d2"))
            painter.setFont(QFont("sans-serif", 17 if self._immersive else 14, QFont.Normal))
            painter.drawText(
                rect,
                Qt.AlignCenter,
                "No lyrics are available for this track yet.",
            )
            return

        state = self._visual_state
        transition = self._ease_out_cubic(self._lyric_transition)
        slide = (1.0 - transition) * (34.0 if self._immersive else 22.0)
        current_y = rect.center().y() + slide
        spacing = rect.height() * (0.23 if self._immersive else 0.22)

        # One restrained ambient halo makes the current lyric feel luminous
        # without paying for a blur effect every frame.
        glow_color = QColor(self._color(0))
        halo_radius = min(rect.width(), rect.height()) * (0.42 if self._immersive else 0.36)
        self._draw_glow(
            painter,
            QPointF(rect.center().x(), current_y),
            halo_radius,
            glow_color,
            22 + int(34 * state.glow),
        )

        active_size = min(
            72 if self._immersive else 48,
            max(34 if self._immersive else 28, int(rect.height() * (0.085 if self._immersive else 0.075))),
        )
        if self._playing:
            active_size = int(round(active_size * (1.0 + 0.012 * state.glow + 0.006 * state.pulse)))
        adjacent_size = max(18 if self._immersive else 15, int(active_size * 0.52))

        previous = self._lyrics.previous
        following = self._lyrics.following
        current = self._lyrics.current or "…"

        adjacent_font = QFont("sans-serif", adjacent_size, QFont.Medium)
        adjacent = QColor("#c2cddd")
        adjacent.setAlpha(112)
        painter.save()
        painter.setFont(adjacent_font)
        painter.setPen(adjacent)
        if previous:
            painter.drawText(
                QRectF(rect.left() + 30, current_y - spacing - 55, rect.width() - 60, 110),
                Qt.AlignCenter | Qt.TextWordWrap,
                previous,
            )
        if following:
            next_color = QColor("#b4c0d0")
            next_color.setAlpha(96)
            painter.setPen(next_color)
            painter.drawText(
                QRectF(rect.left() + 30, current_y + spacing - 55, rect.width() - 60, 110),
                Qt.AlignCenter | Qt.TextWordWrap,
                following,
            )
        painter.restore()

        core = QColor("#f7fbff")
        accent = QColor(self._color(0))
        active_font = QFont("sans-serif", active_size, QFont.DemiBold)
        active_font.setLetterSpacing(QFont.PercentageSpacing, 101.0)
        active_box = QRectF(
            rect.left() + rect.width() * 0.08,
            current_y - rect.height() * 0.13,
            rect.width() * 0.84,
            rect.height() * 0.26,
        )
        self._draw_glowing_text(
            painter,
            active_box,
            current,
            active_font,
            core,
            accent,
            0.72 + 0.55 * state.glow,
        )

        self._paint_lyric_energy_line(painter, rect)
        if self._lyrics.synced:
            label = "LYRIC FLOW   ·   SYNCED"
        else:
            label = "LYRIC FLOW   ·   UNTIMED · PACED ACROSS TRACK"
        if self._lyrics.source:
            label += f"   ·   {self._lyrics.source}"
        self._draw_caption(
            painter,
            QRectF(rect.left(), rect.bottom() - 12, rect.width(), 16),
            label,
            QColor(178, 193, 210, 150),
        )

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
        """Sonic Weather: an abstract atmospheric field, never a literal icon."""

        weather = describe_weather(profile)
        rect = self._area()
        state = self._visual_state
        center = QPointF(
            rect.center().x() + math.sin(self._phase * 0.018) * rect.width() * 0.035,
            rect.center().y() - rect.height() * 0.05,
        )

        # Internal illumination: brightness chooses how open the field feels,
        # warmth shifts the secondary glow within the cover-derived palette.
        primary = QColor(self._color(0))
        secondary = QColor(self._color(3 if state.warmth > 0.55 else 1))
        self._draw_glow(
            painter,
            center,
            min(rect.width(), rect.height()) * (0.52 + 0.08 * state.density),
            primary,
            18 + int(26 * state.glow),
        )
        warm_center = QPointF(
            center.x() - rect.width() * 0.14,
            center.y() + rect.height() * 0.08,
        )
        self._draw_glow(
            painter,
            warm_center,
            min(rect.width(), rect.height()) * 0.36,
            secondary,
            7 + int(18 * state.warmth),
        )

        # Layered vapor bands create depth cheaply: broad translucent Bezier
        # ribbons with slow phase drift, no blur shader or texture asset.
        band_count = 3 if self._requested_quality == "eco" or self._effective_quality == "eco" else 5
        for band in range(band_count):
            fraction = band / max(1, band_count - 1)
            y_mid = rect.top() + rect.height() * (0.22 + 0.13 * band)
            thickness = rect.height() * (0.11 + 0.055 * state.density + 0.015 * band)
            drift = math.sin(self._phase * (0.022 + band * 0.006) + band * 1.4)
            offset = drift * rect.width() * (0.025 + 0.008 * band)
            amplitude = rect.height() * (0.025 + 0.020 * state.rhythm + 0.008 * band)

            top = QPainterPath()
            top.moveTo(rect.left() - 40, y_mid - thickness * 0.5)
            top.cubicTo(
                rect.left() + rect.width() * 0.25 + offset,
                y_mid - thickness * 0.5 - amplitude,
                rect.left() + rect.width() * 0.62 - offset,
                y_mid - thickness * 0.5 + amplitude,
                rect.right() + 40,
                y_mid - thickness * 0.5,
            )
            top.lineTo(rect.right() + 40, y_mid + thickness * 0.5)
            top.cubicTo(
                rect.left() + rect.width() * 0.72 - offset,
                y_mid + thickness * 0.5 + amplitude * 0.72,
                rect.left() + rect.width() * 0.30 + offset,
                y_mid + thickness * 0.5 - amplitude * 0.65,
                rect.left() - 40,
                y_mid + thickness * 0.5,
            )
            top.closeSubpath()

            vapor = QColor(self._color(band))
            alpha = 16 + int(22 * state.density) + int(9 * (1.0 - fraction))
            vapor.setAlpha(alpha)
            painter.setPen(Qt.NoPen)
            painter.setBrush(vapor)
            painter.drawPath(top)

            rim = QColor(self._color(band))
            rim.setAlpha(12 + int(18 * state.glow))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(rim, 0.7 + 0.25 * fraction, Qt.SolidLine, Qt.RoundCap))
            painter.drawPath(top)

        # Particles change character with musical activity. Dense/rhythmic
        # tracks become rain-like light threads; calmer tracks become suspended
        # dust. Positions remain deterministic for the recording.
        particle_count = self._particle_count(24 if state.density > 0.56 else 16)
        active_threads = state.rhythm > 0.48 or state.density > 0.64
        for index, (sx, sy, size, phase) in enumerate(self._stars[:particle_count]):
            travel = (self._phase * (0.010 + 0.025 * state.drift) + phase) % math.tau
            x = rect.left() + ((sx + math.sin(travel + index) * 0.035) % 1.0) * rect.width()
            y = rect.top() + ((sy + self._phase * (0.0018 + 0.0028 * state.drift)) % 1.0) * rect.height()
            particle = QColor(self._color(index + 1))
            particle.setAlpha(28 + int(74 * state.density))
            if active_threads:
                length = 8 + 20 * state.energy + (index % 4) * 3
                painter.setPen(QPen(particle, 0.8 + size * 0.18, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(
                    QPointF(x, y),
                    QPointF(x - 3.0 - 4.0 * state.drift, y + length),
                )
            else:
                painter.setPen(Qt.NoPen)
                painter.setBrush(particle)
                painter.drawEllipse(QPointF(x, y), 0.8 + size * 0.35, 0.8 + size * 0.35)

        # A few pressure-front lines give lateral motion without becoming a
        # waveform visualizer.
        front_count = 2 if self._requested_quality == "eco" or self._effective_quality == "eco" else 3
        for front in range(front_count):
            y = rect.top() + rect.height() * (0.20 + front * 0.23)
            path = QPainterPath(QPointF(rect.left() - 20, y))
            control = math.sin(self._phase * 0.028 + front * 1.8) * rect.height() * 0.07
            path.cubicTo(
                QPointF(rect.left() + rect.width() * 0.32, y + control),
                QPointF(rect.left() + rect.width() * 0.68, y - control * 0.7),
                QPointF(rect.right() + 20, y + control * 0.25),
            )
            front_color = QColor(self._color(front))
            front_color.setAlpha(15 + int(24 * state.glow))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(front_color, 1.0, Qt.SolidLine, Qt.RoundCap))
            painter.drawPath(path)

        painter.save()
        painter.setFont(QFont("sans-serif", 15, QFont.DemiBold))
        painter.setPen(QColor(239, 245, 252, 225))
        painter.drawText(
            QRectF(rect.left(), rect.bottom() - 66, rect.width(), 26),
            Qt.AlignCenter,
            f"{weather.tone}  ·  {weather.density}",
        )
        painter.restore()
        self._draw_caption(
            painter,
            QRectF(rect.left(), rect.bottom() - 40, rect.width(), 18),
            weather.motion.upper(),
            QColor(166, 182, 201, 145),
        )
        self._draw_caption(
            painter,
            QRectF(rect.left(), rect.top() + 2, rect.width(), 18),
            "SONIC WEATHER",
            QColor(166, 182, 201, 125),
        )
        if not weather.based_on_flow:
            self._draw_caption(
                painter,
                QRectF(rect.left(), rect.bottom() - 18, rect.width(), 16),
                "IDENTITY-BASED ESTIMATE   ·   NO CACHED FLOW ANALYSIS",
                QColor(132, 145, 161, 135),
            )

    def _active_memory_index(self) -> int | None:
        return (
            self._hovered_memory_index
            if self._hovered_memory_index is not None
            else self._selected_memory_index
        )

    def _paint_memory_card(
        self,
        painter: QPainter,
        rect: QRectF,
        point: QPointF,
        mark: MemoryMark,
    ) -> None:
        width = min(380.0, max(300.0, rect.width() * 0.42))
        height = 126.0
        x = point.x() + 26.0
        if x + width > rect.right() - 8:
            x = point.x() - width - 26.0
        x = max(rect.left() + 8.0, min(x, rect.right() - width - 8.0))
        y = max(rect.top() + 8.0, min(point.y() - height * 0.52, rect.bottom() - height - 8.0))
        card = QRectF(x, y, width, height)

        leader_end = (
            QPointF(card.left(), card.center().y())
            if card.center().x() > point.x()
            else QPointF(card.right(), card.center().y())
        )
        color = QColor.fromHsv(mark.hue, 145, 242)
        leader = QColor(color)
        leader.setAlpha(115)
        painter.setPen(QPen(leader, 1.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(point, leader_end)

        painter.setPen(QPen(QColor(111, 140, 171, 95), 1.0))
        painter.setBrush(QColor(7, 12, 20, 234))
        painter.drawRoundedRect(card, 15, 15)

        accent = QRectF(card.left() + 12, card.top() + 14, 5, card.height() - 28)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 210))
        painter.drawRoundedRect(accent, 2.5, 2.5)

        left = accent.right() + 14
        width_text = card.right() - left - 14

        painter.setFont(QFont("sans-serif", 13, QFont.DemiBold))
        painter.setPen(QColor("#f3f7fc"))
        painter.drawText(
            QRectF(left, card.top() + 13, width_text, 25),
            Qt.AlignLeft | Qt.AlignVCenter,
            mark.label[:48],
        )

        painter.setFont(QFont("sans-serif", 10, QFont.Medium))
        painter.setPen(QColor("#c6d1dd"))
        painter.drawText(
            QRectF(left, card.top() + 39, width_text, 21),
            Qt.AlignLeft | Qt.AlignVCenter,
            mark.detail[:64],
        )

        meta = f"{mark.count} play{'s' if mark.count != 1 else ''}"
        if mark.daypart:
            meta += f"  ·  {mark.daypart}"
        painter.setFont(QFont("sans-serif", 9, QFont.DemiBold))
        painter.setPen(QColor(color.red(), color.green(), color.blue(), 225))
        painter.drawText(
            QRectF(left, card.top() + 63, width_text, 18),
            Qt.AlignLeft | Qt.AlignVCenter,
            meta.upper(),
        )

        painter.setFont(QFont("sans-serif", 9, QFont.Normal))
        painter.setPen(QColor(166, 179, 194, 190))
        detail = mark.time_label
        if mark.representative:
            detail += ("  ·  " if detail else "") + mark.representative
        painter.drawText(
            QRectF(left, card.top() + 84, width_text, 31),
            Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
            detail[:110],
        )

    def _memory_geometry(self, rect: QRectF):
        ordered_indices = sorted(
            range(len(self._memory)),
            key=lambda index: self._memory[index].x,
        )
        positions: dict[int, QPointF] = {}
        for index in ordered_indices:
            mark = self._memory[index]
            positions[index] = QPointF(
                rect.left() + rect.width() * max(0.0, min(1.0, mark.x)),
                rect.top() + rect.height() * max(0.14, min(0.82, mark.y)),
            )

        max_count = max((mark.count for mark in self._memory), default=1)
        geometry: dict[int, tuple[QPointF, float, float, float, QColor]] = {}
        hit: list[tuple[QPointF, int, float]] = []
        for index, mark in enumerate(self._memory):
            point = positions[index]
            count_scale = math.sqrt(max(1, mark.count) / max(1, max_count))
            radius_y = 7.0 + 11.0 * count_scale
            span_width = rect.width() * mark.span
            radius_x = max(
                radius_y * 1.20,
                min(rect.width() * 0.13, span_width * 0.5 + radius_y * 0.80),
            )
            color = QColor.fromHsv(mark.hue, 145, 242)
            geometry[index] = (point, radius_x, radius_y, count_scale, color)
            hit.append((point, index, max(18.0, radius_x)))
        return ordered_indices, positions, geometry, tuple(hit)

    def _build_memory_cache(
        self,
        rect: QRectF,
        ordered_indices: list[int],
        positions: dict[int, QPointF],
        geometry: dict[int, tuple[QPointF, float, float, float, QColor]],
    ) -> None:
        image = QImage(
            max(1, self.width()),
            max(1, self.height()),
            QImage.Format_ARGB32_Premultiplied,
        )
        image.fill(Qt.transparent)
        cache = QPainter(image)
        cache.setRenderHint(QPainter.Antialiasing, True)

        dayparts = (
            ("LATE NIGHT", 2.5),
            ("MORNING", 8.5),
            ("AFTERNOON", 14.0),
            ("EVENING", 19.0),
            ("LATE NIGHT", 23.0),
        )
        for label, hour in dayparts:
            y_fraction = 0.14 + (hour / 24.0) * 0.68
            y = rect.top() + rect.height() * y_fraction
            line = QColor("#8fa3ba")
            line.setAlpha(20)
            cache.setPen(QPen(line, 1.0, Qt.DotLine))
            cache.drawLine(
                QPointF(rect.left() + 72, y),
                QPointF(rect.right(), y),
            )
            self._draw_caption(
                cache,
                QRectF(rect.left(), y - 8, 66, 16),
                label,
                QColor(143, 159, 178, 105),
                Qt.AlignLeft | Qt.AlignVCenter,
            )

        if len(ordered_indices) > 1:
            path = QPainterPath(positions[ordered_indices[0]])
            for position_index, index in enumerate(ordered_indices[1:], start=1):
                previous = positions[ordered_indices[position_index - 1]]
                current = positions[index]
                mid_x = (previous.x() + current.x()) * 0.5
                path.cubicTo(
                    QPointF(mid_x, previous.y()),
                    QPointF(mid_x, current.y()),
                    current,
                )
            trail = QColor(self._color(0))
            trail.setAlpha(30)
            cache.setBrush(Qt.NoBrush)
            cache.setPen(QPen(trail, 1.15, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            cache.drawPath(path)

        for index, mark in enumerate(self._memory):
            point, radius_x, radius_y, count_scale, color = geometry[index]

            outer = QColor(color)
            outer.setAlpha(16 + int(18 * count_scale))
            cache.setPen(Qt.NoPen)
            cache.setBrush(outer)
            cache.drawEllipse(
                QRectF(
                    point.x() - radius_x,
                    point.y() - radius_y,
                    radius_x * 2,
                    radius_y * 2,
                )
            )

            inner = QColor(color)
            inner.setAlpha(44 + int(48 * count_scale))
            cache.setBrush(inner)
            cache.drawEllipse(
                QRectF(
                    point.x() - radius_x * 0.58,
                    point.y() - radius_y * 0.58,
                    radius_x * 1.16,
                    radius_y * 1.16,
                )
            )

            outline = QColor("#eef6ff")
            outline.setAlpha(46 + int(38 * count_scale))
            cache.setPen(QPen(outline, 0.65))
            cache.setBrush(Qt.NoBrush)
            cache.drawEllipse(
                QRectF(
                    point.x() - radius_x * 0.62,
                    point.y() - radius_y * 0.62,
                    radius_x * 1.24,
                    radius_y * 1.24,
                )
            )
            cache.setPen(Qt.NoPen)
            cache.setBrush(QColor(247, 251, 255, 95))
            cache.drawEllipse(
                point,
                1.8 + 1.2 * count_scale,
                1.8 + 1.2 * count_scale,
            )

        step = max(1, len(self._memory) // 8)
        for ordinal, index in enumerate(ordered_indices):
            if ordinal % step != 0:
                continue
            mark = self._memory[index]
            point = positions[index]
            label_color = QColor("#dce6f1")
            label_color.setAlpha(175)
            cache.setPen(label_color)
            cache.setFont(QFont("sans-serif", 8, QFont.Medium))
            cache.drawText(
                QRectF(point.x() - 60, point.y() + 16, 120, 18),
                Qt.AlignHCenter | Qt.AlignVCenter,
                mark.label[:20],
            )

        self._draw_caption(
            cache,
            QRectF(rect.left(), rect.top() + 2, rect.width(), 16),
            "MEMORY ATLAS   ·   LEFT → RIGHT IS TIME   ·   HEIGHT IS TIME OF DAY   ·   SIZE IS PLAYS",
            QColor(165, 182, 202, 145),
        )
        self._draw_caption(
            cache,
            QRectF(rect.left(), rect.bottom() - 18, rect.width(), 16),
            f"{self._memory_scale.upper()}   ·   {len(self._memory)} GROUPS   ·   HOVER TO EXPLORE",
            QColor(165, 182, 202, 135),
        )
        cache.end()
        self._memory_cache = image

    def _paint_memory_active(
        self,
        painter: QPainter,
        rect: QRectF,
        index: int,
        geometry: dict[int, tuple[QPointF, float, float, float, QColor]],
    ) -> None:
        point, radius_x, radius_y, _count_scale, color = geometry[index]
        self._draw_glow(
            painter,
            point,
            max(radius_x, radius_y) * 2.4,
            color,
            46,
        )

        island = QRadialGradient(point, max(radius_x, radius_y))
        core = QColor(color)
        core.setAlpha(190)
        edge = QColor(color)
        edge.setAlpha(48)
        fade = QColor(color)
        fade.setAlpha(0)
        island.setColorAt(0.0, core)
        island.setColorAt(0.62, edge)
        island.setColorAt(1.0, fade)
        painter.setPen(Qt.NoPen)
        painter.setBrush(island)
        painter.drawEllipse(
            QRectF(
                point.x() - radius_x,
                point.y() - radius_y,
                radius_x * 2,
                radius_y * 2,
            )
        )

        outline = QColor("#eef6ff")
        outline.setAlpha(175)
        painter.setPen(QPen(outline, 1.15))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(
            QRectF(
                point.x() - radius_x * 0.62,
                point.y() - radius_y * 0.62,
                radius_x * 1.24,
                radius_y * 1.24,
            )
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(247, 251, 255, 185))
        painter.drawEllipse(point, 3.0, 3.0)

        self._paint_memory_card(painter, rect, point, self._memory[index])

    def _paint_memory(self, painter: QPainter) -> None:
        rect = self._area()
        self._memory_hit_points = ()
        if not self._memory:
            painter.setPen(QColor("#b2bfce"))
            painter.setFont(QFont("sans-serif", 14, QFont.Normal))
            painter.drawText(
                rect,
                Qt.AlignCenter,
                "Your Memory Atlas starts here.\nListening history will form a chronological landscape.",
            )
            return

        ordered_indices, positions, geometry, hit = self._memory_geometry(rect)
        self._memory_hit_points = hit

        if (
            self._memory_cache.isNull()
            or self._memory_cache.width() != self.width()
            or self._memory_cache.height() != self.height()
        ):
            self._build_memory_cache(
                rect,
                ordered_indices,
                positions,
                geometry,
            )

        painter.drawImage(QPointF(0, 0), self._memory_cache)

        active_index = self._active_memory_index()
        if active_index is not None and active_index in geometry:
            self._paint_memory_active(
                painter,
                rect,
                active_index,
                geometry,
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

    def _memory_hit_test(self, point: QPointF) -> int | None:
        best: tuple[float, int] | None = None
        for center, index, radius in self._memory_hit_points:
            distance = math.hypot(point.x() - center.x(), point.y() - center.y())
            if distance <= max(18.0, radius):
                if best is None or distance < best[0]:
                    best = (distance, index)
        return best[1] if best is not None else None

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.mode == "memory":
            index = self._memory_hit_test(event.position())
            if index != self._hovered_memory_index:
                self._hovered_memory_index = index
                if index is not None and 0 <= index < len(self._memory):
                    mark = self._memory[index]
                    self.setToolTip(
                        f"{mark.label} — {mark.detail} — {mark.count} play"
                        f"{'s' if mark.count != 1 else ''}"
                    )
                else:
                    self.setToolTip("")
                self.update()
            event.accept()
            return
        if self.mode == "constellation":
            found = self._hit_test(event.position())
            token = found[0] if found else None
            if token != self._hovered_token:
                self._hovered_token = token
                if found:
                    self.setToolTip(found[1] + " — double-click to queue")
                    self.neighbourSelected.emit(token)
                else:
                    self.setToolTip("")
                self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        if self.mode == "memory" and self._hovered_memory_index is not None:
            self._hovered_memory_index = None
            self.setToolTip("")
            self.update()
        if self.mode == "constellation" and self._hovered_token is not None:
            self._hovered_token = None
            self.setToolTip("")
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self.mode == "memory":
            index = self._memory_hit_test(event.position())
            self._selected_memory_index = index
            self._hovered_memory_index = index
            self.update()
            event.accept()
            return
        if event.button() == Qt.LeftButton and self.mode == "constellation":
            found = self._hit_test(event.position())
            if found:
                token, label = found
                self._selected_token = token
                self._hovered_token = token
                self.setToolTip(label + " — double-click to queue")
                self.neighbourSelected.emit(token)
                self.update()
                event.accept()
                return
            self._selected_token = None
            self._hovered_token = None
            self.update()
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
            active = self._selected_token if self._selected_token is not None else self._hovered_token
            if event.key() in {Qt.Key_Right, Qt.Key_Down, Qt.Key_Tab}:
                current = next((i for i, node in enumerate(self._neighbours) if node.token == active), -1)
                node = self._neighbours[(current + 1) % len(self._neighbours)]
                self._hovered_token = None
                self._selected_token = node.token
                self.neighbourSelected.emit(node.token)
                self.update()
                event.accept()
                return
            if event.key() in {Qt.Key_Left, Qt.Key_Up, Qt.Key_Backtab}:
                current = next((i for i, node in enumerate(self._neighbours) if node.token == active), 0)
                node = self._neighbours[(current - 1) % len(self._neighbours)]
                self._hovered_token = None
                self._selected_token = node.token
                self.neighbourSelected.emit(node.token)
                self.update()
                event.accept()
                return
            if event.key() in {Qt.Key_Return, Qt.Key_Enter} and active is not None:
                self.neighbourActivated.emit(active)
                event.accept()
                return
        super().keyPressEvent(event)
