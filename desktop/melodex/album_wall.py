from __future__ import annotations

import hashlib
import time
from typing import Any

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)

from .album_wall_model import layout_album_positions


_TILE_W = 244.0
_TILE_H = 296.0
_COVER = 228.0


def _norm(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _identity(track: dict[str, Any]) -> tuple[str, str]:
    for key in ("local_path", "rel", "track_id"):
        value = str(track.get(key) or "").strip()
        if value:
            return key, value
    return "meta", "|".join(_norm(track.get(k)) for k in ("artist", "album", "title"))


def _placeholder_colours(key: str) -> tuple[QColor, QColor]:
    digest = hashlib.sha256(key.encode("utf-8", errors="ignore")).digest()
    hue = int.from_bytes(digest[:2], "big") % 360
    return (
        QColor.fromHsl(hue, 135, 105),
        QColor.fromHsl((hue + 35 + digest[2] % 65) % 360, 95, 65),
    )


class _AlbumTile(QGraphicsObject):
    def __init__(self, album: dict[str, Any], selected, activated):
        super().__init__()
        self.album = dict(album)
        self.key = str(album.get("key") or "")
        self._selected_callback = selected
        self._activated_callback = activated
        self._pixmap = QPixmap()
        self._cover_prepares = 0
        self._placeholder_colours = _placeholder_colours(self.key)
        title = str(self.album.get("title") or "?").strip()
        words = [word for word in title.replace("-", " ").split() if word]
        self._monogram = (
            "".join(word[0] for word in words[:2]).upper()
            if len(words) > 1 else title[:2].upper()
        ) or "?"
        self._selected = False
        self._current = False
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setToolTip(self._tooltip())

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, _TILE_W, _TILE_H)

    def _tooltip(self) -> str:
        year = int(self.album.get("year") or 0)
        genres = ", ".join(str(x) for x in list(self.album.get("genres") or [])[:3] if x)
        analysed = int(self.album.get("analysed_tracks") or 0)
        line = f"{int(self.album.get('track_count') or 0)} tracks"
        if year:
            line += f" · {year}"
        if genres:
            line += f" · {genres}"
        analysis = (
            f"{analysed} analysed · familiarity {float(self.album.get('familiarity') or 0):.0%}"
            if analysed else
            "Not yet audio-analysed"
        )
        return (
            f"{self.album.get('artist') or 'Unknown artist'} — "
            f"{self.album.get('title') or 'Unknown album'}\n{line}\n{analysis}"
        )

    def set_cover_path(self, value: str) -> bool:
        """Decode and prepare the cover once; paint only blits the result."""
        pixmap = QPixmap(str(value or ""))
        if pixmap.isNull():
            return False
        target = max(1, int(_COVER))
        scaled = pixmap.scaled(
            target,
            target,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        left = max(0, (scaled.width() - target) // 2)
        top = max(0, (scaled.height() - target) // 2)
        self._pixmap = scaled.copy(left, top, target, target)
        self._cover_prepares += 1
        self.update()
        return True

    def set_cover_image(self, image: QImage) -> bool:
        if not isinstance(image, QImage) or image.isNull():
            return False
        pixmap = QPixmap.fromImage(image)
        target = max(1, int(_COVER))
        if pixmap.width() != target or pixmap.height() != target:
            pixmap = pixmap.scaled(
                target,
                target,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            left = max(0, (pixmap.width() - target) // 2)
            top = max(0, (pixmap.height() - target) // 2)
            pixmap = pixmap.copy(left, top, target, target)
        self._pixmap = pixmap
        self._cover_prepares += 1
        self.update()
        return True

    def clear_cover(self) -> None:
        if self._pixmap.isNull():
            return
        self._pixmap = QPixmap()
        self.update()

    def set_selected_visual(self, value: bool) -> None:
        self._selected = bool(value)
        self.update()

    def set_current(self, value: bool) -> None:
        self._current = bool(value)
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        cover = QRectF(6, 5, _COVER, _COVER)
        # A quiet shadow makes the wall feel like physical sleeves rather than
        # debug nodes, without using expensive QGraphicsDropShadowEffect items.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 85))
        painter.drawRoundedRect(cover.translated(4, 5), 8, 8)

        clip = QPainterPath()
        clip.addRoundedRect(cover, 7, 7)
        painter.save()
        painter.setClipPath(clip)

        if self._pixmap.isNull():
            a, b = self._placeholder_colours
            gradient = QLinearGradient(cover.topLeft(), cover.bottomRight())
            gradient.setColorAt(0.0, a.darker(150))
            gradient.setColorAt(1.0, b.darker(175))
            painter.fillRect(cover, QBrush(gradient))

            font = painter.font()
            font.setBold(True)
            font.setPointSizeF(46)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255, 150))
            painter.drawText(cover, Qt.AlignCenter, self._monogram)
            painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
            step = 22
            x = int(cover.left()) - int(cover.height())
            while x < int(cover.right()) + int(cover.height()):
                painter.drawLine(
                    x,
                    int(cover.bottom()),
                    x + int(cover.height()),
                    int(cover.top()),
                )
                x += step
        else:
            painter.drawPixmap(cover.toRect(), self._pixmap)
        painter.restore()

        painter.setBrush(Qt.NoBrush)
        if self._current:
            painter.setPen(QPen(QColor("#67d7ff"), 4))
            painter.drawRoundedRect(cover.adjusted(-2, -2, 2, 2), 8, 8)
        elif self._selected:
            painter.setPen(QPen(QColor("#f2f5f8"), 3))
            painter.drawRoundedRect(cover.adjusted(-2, -2, 2, 2), 8, 8)
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 32), 1))
            painter.drawRoundedRect(cover, 7, 7)

        if int(self.album.get("analysed_tracks") or 0) == 0:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#9aa4b8"))
            painter.drawEllipse(QRectF(cover.right() - 12, cover.bottom() - 12, 6, 6))

        if lod >= 0.38:
            title = str(self.album.get("title") or "Unknown album")
            artist = str(self.album.get("artist") or "Unknown artist")
            painter.setPen(QColor("#f4f6fa"))
            font = painter.font()
            font.setPointSizeF(max(7.8, min(11.0, 9.4 * lod)))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(8, 240, 228, 22), Qt.AlignLeft | Qt.AlignVCenter, title[:36])
            if lod >= 0.56:
                font.setBold(False)
                font.setPointSizeF(max(7.2, min(9.8, 8.3 * lod)))
                painter.setFont(font)
                painter.setPen(QColor("#9da7b8"))
                painter.drawText(QRectF(8, 264, 228, 20), Qt.AlignLeft | Qt.AlignVCenter, artist[:36])

    def mousePressEvent(self, event):
        self._selected_callback(self.key)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._activated_callback(self.key)
        super().mouseDoubleClickEvent(event)

    def hoverEnterEvent(self, event):
        self.setZValue(20)
        self.setScale(1.06)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setZValue(0)
        self.setScale(1.0)
        super().hoverLeaveEvent(event)


class _WallView(QGraphicsView):
    """Canvas navigation with cheap frames and settled-only resize work."""

    viewportChanged = Signal()
    viewportSettled = Signal()
    RESIZE_SETTLE_MS = 180

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._viewport_emit_pending = False
        self._viewport_emit_timer = QTimer(self)
        self._viewport_emit_timer.setSingleShot(True)
        self._viewport_emit_timer.timeout.connect(self._emit_viewport_changed)
        self._motion_active = False
        self._resize_in_progress = False
        self._restoring_resize_anchor = False
        self._resize_anchor: QPointF | None = None
        self._resize_anchor_timer = QTimer(self)
        self._resize_anchor_timer.setSingleShot(True)
        self._resize_anchor_timer.timeout.connect(self._restore_resize_anchor)
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.setInterval(90)
        self._settle_timer.timeout.connect(self._settle_motion)
        self._zoom_animation = QVariantAnimation(self)
        self._zoom_animation.setDuration(135)
        self._zoom_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._zoom_animation.valueChanged.connect(self._apply_zoom_value)
        self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)

    def _apply_zoom_value(self, value) -> None:
        target = float(value)
        current = max(0.0001, float(self.transform().m11()))
        factor = target / current
        if abs(factor - 1.0) > 0.0005:
            self.scale(factor, factor)
        self._queue_viewport_changed()

    def smooth_zoom(self, multiplier: float) -> None:
        current = max(0.0001, float(self.transform().m11()))
        target = max(0.58, min(2.35, current * float(multiplier)))
        if abs(target - current) < 0.002:
            return
        if self._zoom_animation.state() == QAbstractAnimation.Running:
            self._zoom_animation.stop()
        self._zoom_animation.setStartValue(current)
        self._zoom_animation.setEndValue(target)
        self._zoom_animation.start()

    def wheelEvent(self, event):
        # Scrolling always moves through the wall. Zoom is deliberate and
        # uses the familiar Cmd/Ctrl + wheel gesture.
        pixel = event.pixelDelta()
        zoom_modifier = bool(event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier))
        if zoom_modifier:
            delta = event.angleDelta().y() or pixel.y()
            if delta:
                steps = max(-3.0, min(3.0, float(delta) / 120.0))
                self.smooth_zoom(1.10 ** steps)
            event.accept()
            return
        if not pixel.isNull():
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - pixel.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - pixel.y())
        else:
            delta = event.angleDelta().y()
            if event.modifiers() & Qt.ShiftModifier:
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta * 0.4))
            else:
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta * 0.4))
        event.accept()

    def _queue_viewport_changed(self, *, live_resize: bool = False) -> None:
        if not self._motion_active:
            self._motion_active = True
            self.setRenderHint(QPainter.Antialiasing, False)
            self.setRenderHint(QPainter.SmoothPixmapTransform, False)
        if live_resize:
            self._resize_in_progress = True
        settle_ms = self.RESIZE_SETTLE_MS if self._resize_in_progress else 90
        self._settle_timer.setInterval(settle_ms)
        self._settle_timer.start()
        if not self._viewport_emit_pending:
            self._viewport_emit_pending = True
            self._viewport_emit_timer.start(0)

    def _emit_viewport_changed(self) -> None:
        self._viewport_emit_pending = False
        self.viewportChanged.emit()

    def _settle_motion(self) -> None:
        if not self._motion_active:
            return
        self._motion_active = False
        if self._resize_in_progress:
            self._restore_resize_anchor()
        self._resize_in_progress = False
        self._resize_anchor = None
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.viewport().update()
        self.viewportSettled.emit()

    @property
    def motion_active(self) -> bool:
        return bool(self._motion_active)

    def scrollContentsBy(self, dx: int, dy: int):
        super().scrollContentsBy(dx, dy)
        if not self._restoring_resize_anchor:
            self._queue_viewport_changed()

    def resizeEvent(self, event):
        if not self._resize_in_progress:
            scene = self.scene()
            if scene is not None and not scene.sceneRect().isEmpty():
                self._resize_anchor = self.mapToScene(self.viewport().rect().center())
        self._resize_in_progress = True
        super().resizeEvent(event)
        # Let the parent layout finish assigning the viewport size before centering.
        if self._resize_anchor is not None:
            self._resize_anchor_timer.start(0)
        # Keep rendering cheap and defer the visible-art scan until resizing ends.
        self._queue_viewport_changed(live_resize=True)

    def _restore_resize_anchor(self) -> None:
        if self._resize_in_progress and self._resize_anchor is not None:
            self._restoring_resize_anchor = True
            try:
                self.centerOn(self._resize_anchor)
            finally:
                self._restoring_resize_anchor = False


class AlbumWallWidget(QWidget):
    albumSelected = Signal(object)
    albumActivated = Signal(object)
    artworkRequested = Signal(object)
    onlineArtworkRequested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model: dict[str, Any] = {}
        self.tiles: dict[str, _AlbumTile] = {}
        self.albums: dict[str, dict[str, Any]] = {}
        self._track_to_album: dict[tuple[str, str], str] = {}
        self.selected_key = ""
        self.current_key = ""
        self._art_requested: set[str] = set()
        self._online_requested: set[str] = set()
        self._resident_art: dict[str, None] = {}
        self._resident_art_limit = 192
        self._art_generation = 0
        self._animation: QVariantAnimation | None = None
        self._start_positions: dict[str, tuple[float, float]] = {}
        self._end_positions: dict[str, tuple[float, float]] = {}
        self._runtime_metrics: dict[str, float | int] = {
            "viewport_changes": 0,
            "viewport_settles": 0,
            "visible_art_scans": 0,
            "visible_art_candidates_last": 0,
            "visible_art_candidates_max": 0,
            "visible_art_batches": 0,
            "visible_art_items_requested": 0,
            "artwork_apply_batches": 0,
            "artwork_items_applied": 0,
            "cover_prepares": 0,
            "resident_cover_evictions": 0,
            "visible_art_scan_last_ms": 0.0,
            "visible_art_scan_max_ms": 0.0,
            "artwork_apply_last_ms": 0.0,
            "artwork_apply_max_ms": 0.0,
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.lens = QComboBox()
        self.lens.addItem("Sound", "sound")
        self.lens.addItem("Familiarity", "familiarity")
        self.lens.addItem("Time", "time")
        self.lens.addItem("A–Z shelves", "shelves")
        self.lens_info = QLabel("")
        self.lens_info.setStyleSheet("color:#8f99aa")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find artist or album…")
        self.search.setMaximumWidth(360)
        find = QPushButton("Find")
        now = QPushButton("Now playing")
        actual = QPushButton("Actual size")
        overview = QPushButton("Overview")
        controls.addWidget(QLabel("Arrange"))
        controls.addWidget(self.lens)
        controls.addWidget(self.lens_info)
        controls.addSpacing(10)
        controls.addWidget(self.search, 1)
        controls.addWidget(find)
        controls.addStretch(1)
        controls.addWidget(now)
        controls.addWidget(actual)
        controls.addWidget(overview)
        layout.addLayout(controls)

        self.scene = QGraphicsScene(self)
        self.view = _WallView(self.scene)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setBackgroundBrush(QBrush(QColor("#0f1116")))
        self.view.setRenderHint(QPainter.Antialiasing, True)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.view.setMinimumHeight(300)
        layout.addWidget(self.view, 1)

        self.selection = QLabel("Select an album to see its details.")
        self.selection.setStyleSheet("color:#e7ebf2;font-size:13px;padding:4px 2px")
        layout.addWidget(self.selection)

        self.status = QLabel("Add local music to build your Album Wall.")
        self.status.setStyleSheet("color:#8f99aa")
        layout.addWidget(self.status)

        self.lens.currentIndexChanged.connect(self._relayout)
        self.search.returnPressed.connect(self.find)
        find.clicked.connect(self.find)
        now.clicked.connect(self.centre_current)
        actual.clicked.connect(self.actual_size)
        overview.clicked.connect(self.fit_wall)
        self.view.viewportChanged.connect(self._viewport_changed)
        self.view.viewportSettled.connect(self._viewport_settled)
        self._art_timer = QTimer(self)
        self._art_timer.setSingleShot(True)
        self._art_timer.setInterval(120)
        self._art_timer.timeout.connect(self._request_visible_art)

    def set_model(self, model: dict[str, Any], current_track: dict[str, Any] | None = None) -> None:
        old_keys = set(self.tiles)
        old_selected = self.selected_key
        had_view = bool(old_keys)
        old_scale = float(self.view.transform().m11()) if had_view else 1.0
        old_center = (
            self.view.mapToScene(self.view.viewport().rect().center())
            if had_view else None
        )
        self._art_generation += 1
        self.model = dict(model or {})
        if self._animation is not None:
            self._animation.stop()
            self._animation = None
        self.scene.clear()
        self.tiles.clear()
        self.albums.clear()
        self._track_to_album.clear()
        self._art_requested.clear()
        self._online_requested.clear()
        self._resident_art.clear()
        self.selected_key = ""
        self.current_key = ""

        for raw in list(self.model.get("albums") or []):
            if not isinstance(raw, dict):
                continue
            album = dict(raw)
            key = str(album.get("key") or "")
            if not key:
                continue
            self.albums[key] = album
            for track in list(album.get("tracks") or []):
                if isinstance(track, dict):
                    self._track_to_album[_identity(track)] = key
            tile = _AlbumTile(album, self._select, self._activate)
            self.tiles[key] = tile
            self.scene.addItem(tile)

        self._place(immediate=True)
        self.highlight_track(current_track or {})
        albums = int(self.model.get("album_count") or len(self.albums))
        analysed = int(self.model.get("analysed_albums") or 0)
        self._update_lens_info()
        if albums:
            new_keys = set(self.tiles)
            overlap = len(old_keys & new_keys) / max(1, len(old_keys))
            if had_view and overlap >= 0.5 and old_center is not None:
                self.view.resetTransform()
                scale = max(0.58, min(2.35, old_scale))
                self.view.scale(scale, scale)
                self.view.centerOn(old_center)
                if old_selected in self.tiles:
                    self._select(old_selected)
            else:
                self._initial_view()
            self.status.setText(
                f"{albums:,} albums · {analysed:,} positioned from Flow analysis · "
                "drag / two-finger scroll to pan · wheel or Cmd/Ctrl-scroll to zoom · "
                "double-click an album to play"
            )
            self._schedule_visible_art()
        else:
            self.selection.setText("Select an album to see its details.")
            self.status.setText("Add local music to build your Album Wall.")

    def selected_album(self) -> dict[str, Any]:
        return dict(self.albums.get(self.selected_key) or {})

    def _select(self, key: str) -> None:
        if self.selected_key in self.tiles:
            self.tiles[self.selected_key].set_selected_visual(False)
        self.selected_key = str(key)
        if self.selected_key in self.tiles:
            self.tiles[self.selected_key].set_selected_visual(True)
            album = dict(self.albums[self.selected_key])
            year = int(album.get("year") or 0)
            details = [
                str(album.get("artist") or "Unknown artist"),
                str(year) if year else "year unknown",
                f"{int(album.get('track_count') or 0)} tracks",
            ]
            self.selection.setText(
                f"{album.get('title') or 'Unknown album'}   ·   " + "   ·   ".join(details)
            )
            self.albumSelected.emit(album)

    def _activate(self, key: str) -> None:
        self._select(key)
        album = self.albums.get(key)
        if album:
            self.albumActivated.emit(dict(album))

    def _place(self, immediate: bool = False) -> None:
        lens = str(self.lens.currentData() or "sound")
        positions = layout_album_positions(self.model, lens)
        if immediate or len(self.tiles) > 850:
            for key, tile in self.tiles.items():
                x, y = positions.get(key, (0.0, 0.0))
                tile.setPos(x, y)
            self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-180, -180, 180, 180))
            return

        self._start_positions = {key: (tile.pos().x(), tile.pos().y()) for key, tile in self.tiles.items()}
        self._end_positions = positions
        if self._animation is not None:
            self._animation.stop()
        animation = QVariantAnimation(self)
        animation.setDuration(520)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)

        def update(value):
            t = float(value)
            smooth = t * t * (3.0 - 2.0 * t)
            for key, tile in self.tiles.items():
                sx, sy = self._start_positions.get(key, (0.0, 0.0))
                ex, ey = self._end_positions.get(key, (sx, sy))
                tile.setPos(sx + (ex - sx) * smooth, sy + (ey - sy) * smooth)

        animation.valueChanged.connect(update)
        animation.finished.connect(
            lambda: self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-180, -180, 180, 180))
        )
        self._animation = animation
        animation.start()

    def _relayout(self) -> None:
        self._place(immediate=False)
        self._update_lens_info()
        QTimer.singleShot(560, self._schedule_visible_art)

    def _update_lens_info(self) -> None:
        lens = str(self.lens.currentData() or "sound")
        albums = list(self.albums.values())
        total = len(albums)
        if lens == "time":
            dated = sum(1 for album in albums if int(album.get("year") or 0) > 0)
            suffix = f"{dated}/{total} dated" if total else ""
        elif lens == "sound":
            analysed = sum(1 for album in albums if int(album.get("analysed_tracks") or 0) > 0)
            suffix = f"{analysed}/{total} sonic positions" if total else ""
        elif lens == "familiarity":
            suffix = "your listening history"
        else:
            suffix = "artist → album"
        self.lens_info.setText(suffix)

    def _initial_view(self) -> None:
        # Browsing starts close to sleeve size. "Overview" is an explicit
        # temporary overview, not the default scale for a large collection.
        self.view.resetTransform()
        count = max(1, len(self.tiles))
        scale = 1.02 if count <= 40 else 0.96 if count <= 220 else 0.90
        self.view.scale(scale, scale)
        if self.current_key and self.current_key in self.tiles:
            self.view.centerOn(self.tiles[self.current_key])
        else:
            rect = self.scene.itemsBoundingRect()
            if rect.isValid() and not rect.isEmpty():
                self.view.centerOn(rect.center())

    def actual_size(self) -> None:
        centre = self.view.mapToScene(self.view.viewport().rect().center())
        self.view.resetTransform()
        self.view.scale(1.0, 1.0)
        if self.selected_key in self.tiles:
            self.view.centerOn(self.tiles[self.selected_key])
        elif self.current_key in self.tiles:
            self.view.centerOn(self.tiles[self.current_key])
        else:
            self.view.centerOn(centre)
        self._schedule_visible_art()

    def fit_wall(self) -> None:
        rect = self.scene.itemsBoundingRect()
        if rect.isValid() and not rect.isEmpty():
            self.view.fitInView(rect.adjusted(-80, -80, 80, 80), Qt.KeepAspectRatio)
        self._schedule_visible_art()

    def focus_album(self, key: str) -> None:
        tile = self.tiles.get(str(key))
        if not tile:
            return
        self._select(str(key))
        self.view.centerOn(tile)
        if self.view.transform().m11() < 0.86:
            self.view.resetTransform()
            self.view.scale(0.98, 0.98)
            self.view.centerOn(tile)
        self._schedule_visible_art()

    def find(self) -> None:
        query = _norm(self.search.text())
        if not query:
            return
        matches = [
            key for key, album in self.albums.items()
            if query in _norm(f"{album.get('artist','')} {album.get('title','')}")
        ]
        if not matches:
            self.status.setText(f"No Album Wall match for “{self.search.text().strip()}”.")
            return
        matches.sort(key=lambda key: (
            not _norm(self.albums[key].get("title")).startswith(query),
            not _norm(self.albums[key].get("artist")).startswith(query),
            _norm(self.albums[key].get("artist")),
            _norm(self.albums[key].get("title")),
        ))
        self.focus_album(matches[0])

    def highlight_track(self, track: dict[str, Any]) -> None:
        key = self._track_to_album.get(_identity(dict(track or {})), "")
        if self.current_key in self.tiles:
            self.tiles[self.current_key].set_current(False)
        self.current_key = key
        if key in self.tiles:
            self.tiles[key].set_current(True)

    def centre_current(self) -> None:
        if self.current_key:
            self.focus_album(self.current_key)
        else:
            self.status.setText("The current track is not on this local Album Wall.")

    def _viewport_changed(self) -> None:
        self._runtime_metrics["viewport_changes"] += 1
        self._art_generation += 1

    def _viewport_settled(self) -> None:
        self._runtime_metrics["viewport_settles"] += 1
        self._trim_resident_artwork()
        self._request_visible_art()

    def _schedule_visible_art(self) -> None:
        self._art_timer.start()

    def _trim_resident_artwork(self) -> None:
        if not self._resident_art:
            return
        viewport=self.view.viewport().rect()
        keep_rect=self.view.mapToScene(viewport).boundingRect().adjusted(-520,-520,520,520)
        protected={
            item.key
            for item in self.scene.items(
                keep_rect,
                Qt.IntersectsItemBoundingRect,
                Qt.AscendingOrder,
            )
            if isinstance(item,_AlbumTile)
        }
        evict=[key for key in list(self._resident_art) if key not in protected]
        survivors=[key for key in self._resident_art if key not in evict]
        overflow=max(0,len(survivors)-self._resident_art_limit)
        if overflow:
            evict.extend(survivors[:overflow])
        for key in dict.fromkeys(evict):
            tile=self.tiles.get(key)
            if tile is not None:
                tile.clear_cover()
            self._resident_art.pop(key,None)
            self._art_requested.discard(key)
            self._runtime_metrics["resident_cover_evictions"] += 1

    def _request_visible_art(self) -> None:
        started = time.perf_counter()
        self._runtime_metrics["visible_art_scans"] += 1
        if not self.tiles:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self._runtime_metrics["visible_art_scan_last_ms"] = round(elapsed_ms, 3)
            self._runtime_metrics["visible_art_scan_max_ms"] = round(
                max(float(self._runtime_metrics["visible_art_scan_max_ms"]), elapsed_ms),
                3,
            )
            return
        viewport = self.view.viewport().rect()
        visible = self.view.mapToScene(viewport).boundingRect().adjusted(-220, -220, 220, 220)
        candidates = [
            item for item in self.scene.items(
                visible,
                Qt.IntersectsItemBoundingRect,
                Qt.AscendingOrder,
            )
            if isinstance(item, _AlbumTile)
        ]
        count = len(candidates)
        self._runtime_metrics["visible_art_candidates_last"] = count
        self._runtime_metrics["visible_art_candidates_max"] = max(
            int(self._runtime_metrics["visible_art_candidates_max"]),
            count,
        )
        batch = []
        for tile in candidates:
            key = tile.key
            if key in self._art_requested:
                continue
            album = self.albums.get(key) or {}
            track = dict(album.get("representative_track") or {})
            if track:
                self._art_requested.add(key)
                batch.append({
                    "key": key,
                    "generation": self._art_generation,
                    "track": track,
                })
            if len(batch) >= 36:
                break
        if batch:
            self._runtime_metrics["visible_art_batches"] += 1
            self._runtime_metrics["visible_art_items_requested"] += len(batch)
            self.artworkRequested.emit(batch)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._runtime_metrics["visible_art_scan_last_ms"] = round(elapsed_ms, 3)
        self._runtime_metrics["visible_art_scan_max_ms"] = round(
            max(float(self._runtime_metrics["visible_art_scan_max_ms"]), elapsed_ms),
            3,
        )

    def request_missing_covers(self) -> None:
        """Explicitly request online cover recovery for the visible wall."""
        self._request_online_art()

    def _request_online_art(self) -> None:
        if not self.tiles:
            return
        viewport = self.view.viewport().rect()
        visible = self.view.mapToScene(viewport).boundingRect().adjusted(-100, -100, 100, 100)
        visible_tiles = [
            item for item in self.scene.items(
                visible,
                Qt.IntersectsItemBoundingRect,
                Qt.AscendingOrder,
            )
            if isinstance(item, _AlbumTile)
        ]
        batch = []
        preferred = [self.selected_key] if self.selected_key else []
        preferred.extend(
            tile.key for tile in visible_tiles if tile.key != self.selected_key
        )
        for key in preferred:
            tile = self.tiles.get(key)
            if tile is None or key in self._online_requested or not tile._pixmap.isNull():
                continue
            album = self.albums.get(key) or {}
            track = dict(album.get("representative_track") or {})
            if track:
                self._online_requested.add(key)
                batch.append({
                    "key": key,
                    "generation": self._art_generation,
                    "track": track,
                })
            if len(batch) >= 6:
                break
        if not batch:
            self.status.setText("No visible missing covers to look up.")
            return
        self.status.setText(f"Looking up {len(batch)} missing cover{'s' if len(batch) != 1 else ''}…")
        self.onlineArtworkRequested.emit(batch)

    def set_artwork(self, mapping: dict[str, object]) -> None:
        started = time.perf_counter()
        loaded = 0
        rows = dict(mapping or {})
        if rows:
            self._runtime_metrics["artwork_apply_batches"] += 1
        for key, raw in rows.items():
            key = str(key)
            structured = isinstance(raw, dict)
            payload = dict(raw) if structured else {"path": str(raw or "")}
            raw_generation = payload.get("generation")
            generation = self._art_generation if raw_generation is None else int(raw_generation)
            self._online_requested.discard(key)
            if generation != self._art_generation:
                self._art_requested.discard(key)
                continue
            tile = self.tiles.get(key)
            image = payload.get("image")
            path = str(payload.get("path") or "")
            applied = False
            if tile is not None and isinstance(image, QImage):
                applied = tile.set_cover_image(image)
            elif tile is not None and not structured and path:
                applied = tile.set_cover_path(path)
            if applied:
                loaded += 1
                self._resident_art.pop(key,None)
                self._resident_art[key]=None
                self._runtime_metrics["cover_prepares"] += 1
        if loaded:
            self._runtime_metrics["artwork_items_applied"] += loaded
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._runtime_metrics["artwork_apply_last_ms"] = round(elapsed_ms, 3)
        self._runtime_metrics["artwork_apply_max_ms"] = round(
            max(float(self._runtime_metrics["artwork_apply_max_ms"]), elapsed_ms),
            3,
        )
        if rows:
            if loaded:
                self.status.setText(f"Loaded {loaded} album cover{'s' if loaded != 1 else ''}.")
            elif any(str(key) in self.tiles for key in rows):
                self.status.setText("No additional covers were found for that batch.")

    def diagnostics_snapshot(self) -> dict[str, Any]:
        """Return aggregate Album Wall runtime timings without collection metadata."""
        return {
            **dict(self._runtime_metrics),
            "tile_count": len(self.tiles),
            "art_requested_count": len(self._art_requested),
            "online_requested_count": len(self._online_requested),
            "motion_active": bool(self.view.motion_active),
            "resident_cover_count": len(self._resident_art),
            "resident_cover_limit": int(self._resident_art_limit),
        }


__all__ = ["AlbumWallWidget"]
