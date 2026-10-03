"""Low-cost, track-aware Now Playing canvas and seekable Flow contour."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QMouseEvent
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)

from .lyrics_state import LyricsDocument, build_lyrics_document
from .track_sigil import TrackSigilBadge
from .visualization_models import MemoryMark, VisualNeighbour, describe_weather
from .visualization_profile import VisualProfile, build_visual_profile
from .visualization_scene import LivingScene
from .visualizer_plugins import installed_visualizers, install_visualizer_file


def _time_label(milliseconds: int) -> str:
    seconds = max(0, int(milliseconds) // 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"


class EnergyJourneySlider(QSlider):
    """Keyboard-accessible seek slider with a compact cached energy contour."""

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setRange(0, 1000)
        self.setFixedHeight(64)
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
        return QRectF(12.0, 5.0, max(1.0, self.width() - 24.0), max(24.0, self.height() - 29.0))

    def _fraction_for_x(self, x: float) -> float:
        chart = self._chart_rect()
        return max(0.0, min(1.0, (x - chart.left()) / max(1.0, chart.width())))

    def _set_from_x(self, x: float) -> None:
        self.setValue(int(round(self._fraction_for_x(x) * self.maximum())))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
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
        chart = self._chart_rect()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        fraction = self.value() / max(1, self.maximum())
        points: list[QPointF] = []
        if len(self._curve) >= 2:
            for index, value in enumerate(self._curve):
                x = chart.left() + chart.width() * index / (len(self._curve) - 1)
                y = chart.bottom() - chart.height() * (0.08 + 0.84 * value)
                points.append(QPointF(x, y))

        if points:
            line = QPainterPath(points[0])
            fill = QPainterPath(QPointF(points[0].x(), chart.bottom()))
            fill.lineTo(points[0])
            for point in points[1:]:
                line.lineTo(point)
                fill.lineTo(point)
            fill.lineTo(points[-1].x(), chart.bottom())
            fill.closeSubpath()
            area = QColor(self._accent)
            area.setAlpha(17)
            painter.setPen(Qt.NoPen)
            painter.setBrush(area)
            painter.drawPath(fill)
            muted = QColor(self._accent)
            muted.setAlpha(95)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(muted, 1.15, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(line)

            curve_position = fraction * (len(points) - 1)
            left_index = min(len(points) - 1, int(curve_position))
            right_index = min(len(points) - 1, left_index + 1)
            blend = curve_position - left_index
            cursor_y = points[left_index].y() * (1.0 - blend) + points[right_index].y() * blend
            active_points = points[: left_index + 1]
            active_cursor = QPointF(chart.left() + chart.width() * fraction, cursor_y)
            if not active_points or abs(active_points[-1].x() - active_cursor.x()) > 0.1:
                active_points.append(active_cursor)
            active_path = QPainterPath(active_points[0])
            for point in active_points[1:]:
                active_path.lineTo(point)
            active = QColor(self._accent)
            active.setAlpha(226)
            painter.setPen(QPen(active, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(active_path)
        else:
            cursor_y = chart.center().y()

        baseline = chart.bottom() + 15.0
        muted = QColor(self._accent)
        muted.setAlpha(48)
        painter.setPen(QPen(muted, 2.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(chart.left(), baseline), QPointF(chart.right(), baseline))
        active = QColor(self._accent)
        active.setAlpha(190)
        cursor_x = chart.left() + chart.width() * fraction
        painter.setPen(QPen(active, 2.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(chart.left(), baseline), QPointF(cursor_x, baseline))
        for tick in range(5):
            x = chart.left() + chart.width() * tick / 4
            tick_color = QColor(self._accent)
            tick_color.setAlpha(68)
            painter.setPen(QPen(tick_color, 1.0))
            painter.drawLine(QPointF(x, baseline - 3.0), QPointF(x, baseline + 3.0))

        painter.setPen(Qt.NoPen)
        halo = QColor(self._accent)
        halo.setAlpha(52)
        painter.setBrush(halo)
        painter.drawEllipse(QPointF(cursor_x, cursor_y), 9.0, 9.0)
        ring = QColor(self._accent)
        ring.setAlpha(228)
        painter.setPen(QPen(ring, 1.5))
        painter.setBrush(QColor("#0e141d"))
        painter.drawEllipse(QPointF(cursor_x, baseline), 5.0, 5.0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#eff6ff"))
        painter.drawEllipse(QPointF(cursor_x, baseline), 2.0, 2.0)
        if self.hasFocus():
            focus = QColor(self._accent)
            focus.setAlpha(90)
            painter.setPen(QPen(focus, 1.0, Qt.DotLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 8, 8)
        painter.end()


class LivingCanvasView(QWidget):
    """Now Playing visualizer modes, seek journey and local `.mdxviz` recipes."""

    seekRequested = Signal(int)
    modeDataRequested = Signal(str)
    neighbourActivated = Signal(int)
    neighbourPreviewRequested = Signal(int)

    _MODE_GROUPS = (
        (
            "WATCH",
            (
                ("Profile Pulse", "living"),
                ("Lyric Flow", "lyrics"),
                ("Sonic Weather", "weather"),
                ("Album World", "album_world"),
                ("Minimal", "minimal"),
            ),
        ),
        (
            "EXPLORE",
            (
                ("Constellation", "constellation"),
                ("Memory Atlas", "memory"),
                ("Musical Journey", "journey"),
            ),
        ),
    )
    _BUILTIN_MODES = (
        ("Profile Pulse", "living"),
        ("Lyric Flow", "lyrics"),
        ("Sonic Weather", "weather"),
        ("Album World", "album_world"),
        ("Minimal", "minimal"),
        ("Constellation", "constellation"),
        ("Memory Atlas", "memory"),
        ("Musical Journey", "journey"),
    )

    def __init__(self, parent=None, visualizer_dir: Path | None = None):
        super().__init__(parent)
        self._track: dict[str, Any] = {}
        self._profile: VisualProfile | None = None
        self._duration_ms = 0
        self._position_ms = 0
        self._syncing_slider = False
        self._lyrics = LyricsDocument.empty()
        self._accent_color = QColor("#7eb4ff")
        self._palette_colors: tuple[str, ...] = ()
        self._artwork_path = ""
        self._playing = False
        self._window_minimized = False
        self._lyric_flow_dialog: QDialog | None = None
        self._lyric_flow_scene: LivingScene | None = None
        self._visualizer_dir = Path(visualizer_dir or Path.home() / ".melodex" / "visualizers")
        self._plugins: dict[str, Any] = {}
        self._neighbours: tuple[VisualNeighbour, ...] = ()
        self._active_mode = "living"
        self._active_plugin_id = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(9)

        heading = QHBoxLayout()
        heading.setSpacing(8)
        title = QLabel("Visuals")
        title.setStyleSheet("font-size:21px;font-weight:700;color:#f3f6fb;letter-spacing:.2px")
        heading.addWidget(title)
        heading.addStretch(1)
        self.mode_combo = QComboBox(self)
        self.mode_combo.setAccessibleName("Melodex visual experience")
        self.mode_combo.setToolTip(
            "Watch music-reactive scenes or Explore your listening and nearby tracks."
        )
        self.mode_combo.setMinimumHeight(36)
        self.mode_combo.setMinimumWidth(172)
        heading.addWidget(self.mode_combo)

        self.memory_scale = QComboBox(self)
        self.memory_scale.setAccessibleName("Memory Atlas grouping")
        for label, value in (("Sessions", "sessions"), ("Albums", "albums"), ("Weeks", "weeks"), ("Years", "years")):
            self.memory_scale.addItem(label, value)
        self.memory_scale.setMinimumHeight(36)
        self.memory_scale.setToolTip(
            "Group the same chronological listening history into sessions, albums, weeks or years."
        )
        self.memory_scale.hide()
        heading.addWidget(self.memory_scale)

        self.quality_combo = QComboBox(self)
        self.quality_combo.setAccessibleName("Visualizer performance quality")
        for label, value in (("Auto · 15 fps", "auto"), ("Eco · 10 fps", "eco"), ("High · 30 fps", "high"), ("Battery · static", "battery")):
            self.quality_combo.addItem(label, value)
        self.quality_combo.setToolTip("Limit animation and drawing detail to suit this device.")
        self.quality_combo.setMinimumHeight(36)
        heading.addWidget(self.quality_combo)

        self.install_button = QPushButton("Add visualizer…", self)
        self.install_button.setToolTip("Install a validated, non-executable .mdxviz JSON recipe.")
        self.install_button.setMinimumHeight(36)
        self.install_button.clicked.connect(self._install_visualizer)
        heading.addWidget(self.install_button)
        self.remove_button = QPushButton("Remove", self)
        self.remove_button.setToolTip("Remove the selected personal visualizer.")
        self.remove_button.setEnabled(False)
        self.remove_button.setVisible(False)
        self.remove_button.setMinimumHeight(36)
        self.remove_button.clicked.connect(self._remove_visualizer)
        heading.addWidget(self.remove_button)
        layout.addLayout(heading)

        track_row = QHBoxLayout()
        track_row.setContentsMargins(0, 0, 0, 0)
        track_row.setSpacing(9)
        self.track_sigil = TrackSigilBadge(self)
        track_row.addWidget(self.track_sigil, 0, Qt.AlignVCenter)

        track_text = QVBoxLayout()
        track_text.setContentsMargins(0, 0, 0, 0)
        track_text.setSpacing(1)
        self.track_label = QLabel("Waiting for music")
        self.track_label.setTextFormat(Qt.RichText)
        self.track_label.setStyleSheet("font-size:13px;color:#c8ccd2;padding-left:2px")
        self.track_label.setWordWrap(True)
        track_text.addWidget(self.track_label)
        self.sigil_caption = QLabel("TRACK SIGIL · stable recording identity")
        self.sigil_caption.setStyleSheet(
            "font-size:9px;font-weight:600;letter-spacing:.8px;color:#75869a;padding-left:2px"
        )
        track_text.addWidget(self.sigil_caption)
        track_row.addLayout(track_text, 1)
        layout.addLayout(track_row)

        self.scene = LivingScene(self)
        self.scene.neighbourSelected.connect(self._neighbour_selected)
        self.scene.neighbourActivated.connect(self.neighbourActivated.emit)
        self.scene.qualityAdjusted.connect(self._quality_adjusted)
        layout.addWidget(self.scene, 1)

        self.status = QLabel("Choose a Watch scene or Explore map.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#a6b2c1;font-size:12px;padding-left:2px")
        layout.addWidget(self.status)

        self.journey = EnergyJourneySlider(self)
        self.journey.valueChanged.connect(self._slider_value_changed)
        self.journey.sliderReleased.connect(self._emit_seek)
        layout.addWidget(self.journey)

        times = QHBoxLayout()
        self.position_label = QLabel("0:00")
        self.duration_label = QLabel("0:00")
        self.duration_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.position_label.setStyleSheet("color:#b5c1d0;font-size:11px;font-weight:600")
        self.duration_label.setStyleSheet("color:#b5c1d0;font-size:11px;font-weight:600")
        times.addWidget(self.position_label)
        times.addStretch(1)
        times.addWidget(self.duration_label)
        layout.addLayout(times)

        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.memory_scale.currentIndexChanged.connect(self._memory_scale_changed)
        self.quality_combo.currentIndexChanged.connect(self._quality_changed)
        self._reload_plugins()

    def set_track(self, track: dict[str, Any], analysis: Any = None) -> None:
        self._track = dict(track or {})
        self._lyrics = LyricsDocument.empty()
        self.scene.set_lyrics(self._lyrics.frame(0, 0))
        self._profile = build_visual_profile(self._track, analysis)
        self.scene.set_profile(self._profile)
        self.track_sigil.set_profile(self._profile)
        self.sigil_caption.setText(
            f"TRACK SIGIL · {self._profile.fingerprint[:12].upper()} · stable recording identity"
        )
        if self._lyric_flow_scene is not None:
            self._lyric_flow_scene.set_profile(self._profile)
            self._lyric_flow_scene.set_lyrics(self._lyrics.frame(0, 0))
        self.journey.set_curve(self._profile.energy_curve)
        title = self._profile.title or "Unknown track"
        artist = self._profile.artist or "Unknown artist"
        album = str(self._track.get("album") or "").strip()
        title_html = escape(title)
        artist_html = escape(artist)
        album_html = escape(album)
        detail = f'<span style="font-size:16px;font-weight:bold;font-style:normal;color:#f0f4fa">{title_html}</span>'
        detail += f'<span style="font-size:13px;color:#9caabc"> &nbsp;·&nbsp; {artist_html}'
        if album_html:
            detail += f' &nbsp;·&nbsp; {album_html}'
        self.track_label.setText(detail + "</span>")
        duration = self._track.get("duration")
        try:
            if duration is None and self._track.get("duration_ms") is not None:
                self._duration_ms = max(0, int(float(self._track.get("duration_ms") or 0)))
            else:
                self._duration_ms = max(0, int(float(duration or 0) * 1000))
        except (TypeError, ValueError, OverflowError):
            self._duration_ms = 0
        self.set_position(0, self._duration_ms)
        self._update_status()

    def set_analysis(self, analysis: Any) -> None:
        """Refresh cached Flow features without clearing lyrics or playback position."""
        if not self._track:
            return
        self._profile = build_visual_profile(self._track, analysis)
        self.scene.set_profile(self._profile)
        if self._lyric_flow_scene is not None:
            self._lyric_flow_scene.set_profile(self._profile)
        self.journey.set_curve(self._profile.energy_curve)
        self.set_position(self._position_ms, self._duration_ms)
        self._update_status()

    def set_accent_color(self, color: QColor) -> None:
        self._accent_color = QColor(color)
        self.scene.set_accent_color(color)
        self.journey.set_accent_color(color)
        self.track_sigil.set_accent_color(color)
        if self._lyric_flow_scene is not None:
            self._lyric_flow_scene.set_accent_color(color)

    def set_palette(self, colors: object) -> None:
        if isinstance(colors, (tuple, list)):
            self._palette_colors = tuple(str(value) for value in colors)
            self.scene.set_palette(self._palette_colors)
            if self._lyric_flow_scene is not None:
                self._lyric_flow_scene.set_palette(self._palette_colors)

    def set_artwork(self, path: str) -> None:
        self._artwork_path = str(path or "")
        self.scene.set_artwork(self._artwork_path)
        if self._lyric_flow_scene is not None:
            self._lyric_flow_scene.set_artwork(self._artwork_path)

    def set_playing(self, playing: bool) -> None:
        self._playing = bool(playing)
        self.scene.set_playing(self._playing)
        if self._lyric_flow_scene is not None:
            self._lyric_flow_scene.set_playing(self._playing)

    def set_window_minimized(self, minimized: bool) -> None:
        self._window_minimized = bool(minimized)
        self.scene.set_window_minimized(self._window_minimized)
        if self._lyric_flow_scene is not None:
            self._lyric_flow_scene.set_window_minimized(self._window_minimized)

    def set_lyrics(self, lyrics: object) -> None:
        self._lyrics = build_lyrics_document(lyrics)
        self._update_lyric_frame()
        self._update_status()

    def set_neighbours(self, neighbours: tuple[VisualNeighbour, ...] | list[VisualNeighbour]) -> None:
        self._neighbours = tuple(neighbours[:24])
        self.scene.set_neighbours(self._neighbours)
        if self._active_mode == "constellation":
            self._update_status()

    def set_neighbour_artwork(self, token: int, path: str) -> None:
        self.scene.set_neighbour_artwork(int(token), str(path or ""))

    def set_memory_marks(self, marks: tuple[MemoryMark, ...] | list[MemoryMark], scale: str) -> None:
        self.scene.set_memory(marks, scale)
        if self._active_mode == "memory":
            self._update_status()

    @property
    def active_mode(self) -> str:
        return self._active_mode

    def refresh_context(self) -> None:
        if self._active_mode == "constellation":
            self.modeDataRequested.emit("constellation")
        elif self._active_mode == "memory":
            self.modeDataRequested.emit("memory:" + str(self.memory_scale.currentData() or "sessions"))

    def show_lyric_flow_fullscreen(self) -> None:
        if not self._lyrics.has_content:
            QMessageBox.information(
                self,
                "Lyric Flow",
                "Lyrics are not available for this track yet.",
            )
            return
        if self._lyric_flow_dialog is not None:
            self._lyric_flow_dialog.raise_()
            self._lyric_flow_dialog.activateWindow()
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Lyric Flow · Melodex")
        dialog.setModal(False)
        dialog.setStyleSheet("QDialog{background:#070b12;}")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scene = LivingScene(dialog)
        scene.setMinimumHeight(540)
        scene.set_immersive(True)
        scene.set_mode("lyrics")
        if self._profile is not None:
            scene.set_profile(self._profile)
        scene.set_accent_color(self._accent_color)
        if self._palette_colors:
            scene.set_palette(self._palette_colors)
        scene.set_artwork(self._artwork_path)
        scene.set_quality(str(self.quality_combo.currentData() or "auto"))
        scene.set_position_fraction(
            self._position_ms / self._duration_ms if self._duration_ms > 0 else 0.0
        )
        scene.set_lyrics(self._lyrics.frame(self._position_ms, self._duration_ms))
        scene.set_playing(self._playing)
        scene.set_window_minimized(self._window_minimized)
        layout.addWidget(scene, 1)

        dialog.finished.connect(self._lyric_flow_closed)
        self._lyric_flow_dialog = dialog
        self._lyric_flow_scene = scene
        dialog.showFullScreen()

    def _lyric_flow_closed(self, _result: int) -> None:
        self._lyric_flow_scene = None
        self._lyric_flow_dialog = None

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
        self._position_ms = position
        self._update_lyric_frame()
        if self._lyric_flow_scene is not None:
            self._lyric_flow_scene.set_position_fraction(
                position / duration if duration > 0 else 0.0
            )

    def _update_lyric_frame(self) -> None:
        frame = self._lyrics.frame(self._position_ms, self._duration_ms)
        self.scene.set_lyrics(frame)
        if self._lyric_flow_scene is not None:
            self._lyric_flow_scene.set_lyrics(frame)

    def _mode_changed(self, _index: int) -> None:
        data = self.mode_combo.currentData()
        is_plugin = isinstance(data, tuple) and data[0] == "plugin"
        self.remove_button.setVisible(is_plugin)
        self.remove_button.setEnabled(is_plugin)
        if isinstance(data, tuple) and data[0] == "plugin":
            self._active_mode = "plugin"
            self._active_plugin_id = str(data[1])
            recipe = self._plugins.get(self._active_plugin_id)
            self.scene.set_mode("plugin", recipe)
            self.memory_scale.hide()
            self.modeDataRequested.emit("plugin")
        else:
            self._active_mode = str(data or "living")
            self._active_plugin_id = ""
            self.scene.set_mode(self._active_mode)
            self.memory_scale.setVisible(self._active_mode == "memory")
            if self._active_mode in {"constellation", "memory"}:
                self.modeDataRequested.emit(self._active_mode)
        self._update_status()

    def _memory_scale_changed(self, _index: int) -> None:
        if self._active_mode == "memory":
            self.modeDataRequested.emit("memory:" + str(self.memory_scale.currentData() or "sessions"))

    def _quality_changed(self, _index: int) -> None:
        quality = str(self.quality_combo.currentData() or "auto")
        self.scene.set_quality(quality)
        if self._lyric_flow_scene is not None:
            self._lyric_flow_scene.set_quality(quality)

    def _quality_adjusted(self, quality: str) -> None:
        if quality == "eco":
            self.status.setText(self.status.text().split("  ·  Auto reduced")[0] + "  ·  Auto reduced scene detail after a slow frame.")
        else:
            self.status.setText(self.status.text().split("  ·  Auto reduced")[0])

    def _neighbour_selected(self, token: int) -> None:
        node = next((item for item in self._neighbours if item.token == token), None)
        if node:
            self.status.setText(
                f"{node.artist} — {node.title}  ·  {node.relation}  ·  "
                "hover reveals artwork, double-click queues"
            )
            self.neighbourPreviewRequested.emit(int(token))

    def _update_status(self) -> None:
        mode = self._active_mode
        profile = self._profile
        if profile is None:
            self.status.setText("Play a track to start its visual journey.")
        elif mode == "living":
            self.status.setText(
                "Profile Pulse turns cached musical features into a breathing radial portrait; "
                "the geometry remains deterministic for this recording."
            )
        elif mode == "fingerprint":
            self.status.setText(
                f"Track Sigil · {profile.fingerprint[:12].upper()} · identity-only compatibility view."
            )
        elif mode == "journey":
            self.status.setText("Cached Flow energy across the recording. Click or drag the contour below to seek.") if profile.energy_curve else self.status.setText("No cached Flow contour is available yet. Seeking still works from the position control below.")
        elif mode == "constellation":
            self.status.setText(
                f"{len(self._neighbours)} nearby tracks · distance shows relationship strength · "
                "hover for artwork, click to hold, double-click to queue."
            )
        elif mode == "lyrics":
            if self._lyrics.synced:
                self.status.setText("Lyric Flow follows synchronized lyrics with restrained music-reactive glow.")
            elif self._lyrics.text.strip():
                self.status.setText("Untimed lyrics use the same reader text, paced gently across the track.")
            else:
                self.status.setText("Lyric Flow is ready when lyrics become available.")
        elif mode == "album_world":
            self.status.setText("A deterministic world shaped by cached Flow and the cover-art palette.")
        elif mode == "weather":
            weather = describe_weather(profile)
            self.status.setText(
                f"{weather.summary} · atmosphere, density and motion are mapped into a procedural field."
            )
        elif mode == "memory":
            self.status.setText(
                "Memory Atlas: left-to-right is chronological time, height is average time of day, "
                "island size is play count; hover a group for details."
            )
        elif mode == "minimal":
            self.status.setText("A quiet identity scene. Choose Battery quality for a static, low-power view.")
        elif mode == "plugin":
            recipe = self._plugins.get(self._active_plugin_id)
            self.status.setText((recipe.description or recipe.name) + "  ·  validated local scene recipe") if recipe else self.status.setText("This visualizer recipe could not be loaded.")

    def _add_mode_section(self, label: str) -> None:
        self.mode_combo.addItem(label)
        index = self.mode_combo.count() - 1
        model = self.mode_combo.model()
        item = model.item(index) if hasattr(model, "item") else None
        if item is not None:
            item.setEnabled(False)
            item.setSelectable(False)
            item.setForeground(QColor("#77889d"))

    def _reload_plugins(self, select_id: str = "") -> None:
        self._plugins = {recipe.id: recipe for recipe, _path in installed_visualizers(self._visualizer_dir)}
        old = self.mode_combo.blockSignals(True)
        current = self.mode_combo.currentData()
        self.mode_combo.clear()

        for section, modes in self._MODE_GROUPS:
            self._add_mode_section(section)
            for label, mode in modes:
                self.mode_combo.addItem(label, mode)

        if self._plugins:
            self._add_mode_section("PERSONAL")
            for plugin_id, recipe in self._plugins.items():
                self.mode_combo.addItem(recipe.name, ("plugin", plugin_id))

        target = current
        target_id = select_id or (
            current[1]
            if isinstance(current, tuple) and current[0] == "plugin"
            else ""
        )
        if target_id:
            target = ("plugin", target_id)
        if target is None:
            target = "living"

        index = next(
            (
                i
                for i in range(self.mode_combo.count())
                if self.mode_combo.itemData(i) == target
            ),
            -1,
        )
        if index < 0:
            index = next(
                (
                    i
                    for i in range(self.mode_combo.count())
                    if self.mode_combo.itemData(i) == "living"
                ),
                0,
            )
        self.mode_combo.setCurrentIndex(index)
        self.mode_combo.blockSignals(old)
        self._mode_changed(self.mode_combo.currentIndex())

    def _install_visualizer(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Install Melodex visualizer", "", "Melodex visualizers (*.mdxviz)")
        if not path:
            return
        try:
            recipe, _target = install_visualizer_file(Path(path), self._visualizer_dir)
        except FileExistsError:
            answer = QMessageBox.question(
                self, "Replace visualizer?", "A visualizer with this ID is already installed. Replace it?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            try:
                recipe, _target = install_visualizer_file(Path(path), self._visualizer_dir, overwrite=True)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Could not install visualizer", str(exc))
                return
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not install visualizer", str(exc))
            return
        self._reload_plugins(recipe.id)
        self.status.setText(f"Installed {recipe.name} from a validated .mdxviz recipe.")

    def _remove_visualizer(self) -> None:
        plugin_id = self._active_plugin_id
        if not plugin_id:
            return
        recipe = self._plugins.get(plugin_id)
        if not recipe:
            return
        answer = QMessageBox.question(
            self, "Remove visualizer?", f"Remove {recipe.name} from this device?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        target = self._visualizer_dir / f"{plugin_id}.mdxviz"
        try:
            target.unlink()
        except OSError as exc:
            QMessageBox.warning(self, "Could not remove visualizer", str(exc))
            return
        self._reload_plugins()

    def _slider_value_changed(self, _value: int) -> None:
        if self._syncing_slider or self.journey.isSliderDown():
            return
        self._emit_seek()

    def _emit_seek(self) -> None:
        if self._duration_ms <= 0:
            return
        position = int(self._duration_ms * self.journey.value() / max(1, self.journey.maximum()))
        self.seekRequested.emit(position)
