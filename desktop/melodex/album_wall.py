from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEasingCurve, QRect, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
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


_TILE_W = 176.0
_TILE_H = 216.0
_COVER = 164.0


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

    def set_cover_path(self, value: str) -> None:
        path = Path(str(value or ""))
        pixmap = QPixmap(str(path)) if path.is_file() else QPixmap()
        if not pixmap.isNull():
            self._pixmap = pixmap
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
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

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
            a, b = _placeholder_colours(self.key)
            gradient = QLinearGradient(cover.topLeft(), cover.bottomRight())
            gradient.setColorAt(0.0, a.darker(150))
            gradient.setColorAt(1.0, b.darker(175))
            painter.fillRect(cover, QBrush(gradient))

            title = str(self.album.get("title") or "?").strip()
            words = [word for word in title.replace("-", " ").split() if word]
            monogram = (
                "".join(word[0] for word in words[:2]).upper()
                if len(words) > 1
                else title[:2].upper()
            )
            font = painter.font()
            font.setBold(True)
            font.setPointSizeF(34)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255, 150))
            painter.drawText(cover, Qt.AlignCenter, monogram or "?")
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
            target_w = max(1, int(cover.width()))
            target_h = max(1, int(cover.height()))
            scaled = self._pixmap.scaled(
                target_w,
                target_h,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            source = QRect(
                max(0, (scaled.width() - target_w) // 2),
                max(0, (scaled.height() - target_h) // 2),
                min(target_w, scaled.width()),
                min(target_h, scaled.height()),
            )
            painter.drawPixmap(cover.toRect(), scaled, source)
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
            painter.drawText(QRectF(6, 173, 164, 18), Qt.AlignLeft | Qt.AlignVCenter, title[:36])
            if lod >= 0.56:
                font.setBold(False)
                font.setPointSizeF(max(7.2, min(9.8, 8.3 * lod)))
                painter.setFont(font)
                painter.setPen(QColor("#9da7b8"))
                painter.drawText(QRectF(6, 193, 164, 17), Qt.AlignLeft | Qt.AlignVCenter, artist[:36])

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
    """Canvas-like wall navigation with gentle zoom and trackpad panning."""

    viewportChanged = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._zoom_animation = QVariantAnimation(self)
        self._zoom_animation.setDuration(135)
        self._zoom_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._zoom_animation.valueChanged.connect(self._apply_zoom_value)

    def _apply_zoom_value(self, value) -> None:
        target = float(value)
        current = max(0.0001, float(self.transform().m11()))
        factor = target / current
        if abs(factor - 1.0) > 0.0005:
            self.scale(factor, factor)
        self.viewportChanged.emit()

    def smooth_zoom(self, multiplier: float) -> None:
        current = max(0.0001, float(self.transform().m11()))
        target = max(0.58, min(2.35, current * float(multiplier)))
        if abs(target - current) < 0.002:
            return
        if self._zoom_animation.state() == QVariantAnimation.Running:
            self._zoom_animation.stop()
        self._zoom_animation.setStartValue(current)
        self._zoom_animation.setEndValue(target)
        self._zoom_animation.start()

    def wheelEvent(self, event):
        # Native-feeling trackpad navigation: two-finger scrolling pans the
        # wall. Mouse wheels still zoom; Cmd/Ctrl + trackpad scroll zooms.
        pixel = event.pixelDelta()
        zoom_modifier = bool(
            event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)
        )
        if not pixel.isNull() and not zoom_modifier:
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - pixel.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - pixel.y()
            )
            event.accept()
            self.viewportChanged.emit()
            return

        delta = event.angleDelta().y()
        if not delta and not pixel.isNull():
            delta = pixel.y()
        if not delta:
            return
        steps = max(-3.0, min(3.0, float(delta) / 120.0))
        self.smooth_zoom(1.10 ** steps)
        event.accept()

    def scrollContentsBy(self, dx: int, dy: int):
        super().scrollContentsBy(dx, dy)
        self.viewportChanged.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.viewportChanged.emit()


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
        self._animation: QVariantAnimation | None = None
        self._start_positions: dict[str, tuple[float, float]] = {}
        self._end_positions: dict[str, tuple[float, float]] = {}

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
        self.view.setMinimumHeight(430)
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
        self.view.viewportChanged.connect(self._schedule_visible_art)
        self._art_timer = QTimer(self)
        self._art_timer.setSingleShot(True)
        self._art_timer.setInterval(120)
        self._art_timer.timeout.connect(self._request_visible_art)

    def set_model(self, model: dict[str, Any], current_track: dict[str, Any] | None = None) -> None:
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

    def _schedule_visible_art(self) -> None:
        self._art_timer.start()

    def _request_visible_art(self) -> None:
        if not self.tiles:
            return
        viewport = self.view.viewport().rect()
        visible = self.view.mapToScene(viewport).boundingRect().adjusted(-220, -220, 220, 220)
        batch = []
        for key, tile in self.tiles.items():
            if key in self._art_requested:
                continue
            if not tile.sceneBoundingRect().intersects(visible):
                continue
            album = self.albums.get(key) or {}
            track = dict(album.get("representative_track") or {})
            if track:
                self._art_requested.add(key)
                batch.append({"key": key, "track": track})
            if len(batch) >= 36:
                break
        if batch:
            self.artworkRequested.emit(batch)

    def request_missing_covers(self) -> None:
        """Explicitly request online cover recovery for the visible wall."""
        self._request_online_art()

    def _request_online_art(self) -> None:
        if not self.tiles:
            return
        viewport = self.view.viewport().rect()
        visible = self.view.mapToScene(viewport).boundingRect().adjusted(-100, -100, 100, 100)
        batch = []
        preferred = [self.selected_key] if self.selected_key else []
        preferred.extend(key for key in self.tiles if key != self.selected_key)
        for key in preferred:
            tile = self.tiles.get(key)
            if tile is None or key in self._online_requested or not tile._pixmap.isNull():
                continue
            if key != self.selected_key and not tile.sceneBoundingRect().intersects(visible):
                continue
            album = self.albums.get(key) or {}
            track = dict(album.get("representative_track") or {})
            if track:
                self._online_requested.add(key)
                batch.append({"key": key, "track": track})
            if len(batch) >= 6:
                break
        if not batch:
            self.status.setText("No visible missing covers to look up.")
            return
        self.status.setText(f"Looking up {len(batch)} missing cover{'s' if len(batch) != 1 else ''}…")
        self.onlineArtworkRequested.emit(batch)

    def set_artwork(self, mapping: dict[str, str]) -> None:
        loaded = 0
        rows = dict(mapping or {})
        for key, path in rows.items():
            key = str(key)
            self._online_requested.discard(key)
            tile = self.tiles.get(key)
            if tile and path:
                tile.set_cover_path(str(path))
                loaded += 1
        if rows:
            if loaded:
                self.status.setText(f"Loaded {loaded} album cover{'s' if loaded != 1 else ''}.")
            elif any(str(key) in self.tiles for key in rows):
                self.status.setText("No additional covers were found for that batch.")


__all__ = ["AlbumWallWidget"]
