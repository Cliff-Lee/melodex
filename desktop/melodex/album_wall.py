from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
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


_TILE_W = 144.0
_TILE_H = 178.0
_COVER = 132.0


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

        if self._pixmap.isNull():
            a, b = _placeholder_colours(self.key)
            painter.fillRect(cover, a)
            painter.fillRect(cover.adjusted(18, 18, -18, -18), b)
            painter.setPen(QColor(255, 255, 255, 125))
            painter.drawEllipse(cover.center(), 26, 26)
            painter.drawEllipse(cover.center(), 7, 7)
        else:
            painter.drawPixmap(cover.toRect(), self._pixmap)

        if self._current:
            painter.setPen(QPen(QColor("#66d9ff"), 4))
            painter.drawRoundedRect(cover.adjusted(-2, -2, 2, 2), 5, 5)
        elif self._selected:
            painter.setPen(QPen(QColor("#f4f6fa"), 3))
            painter.drawRoundedRect(cover.adjusted(-2, -2, 2, 2), 5, 5)

        if int(self.album.get("analysed_tracks") or 0) == 0:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(12, 15, 20, 105))
            painter.drawRect(cover)

        if lod >= 0.48:
            title = str(self.album.get("title") or "Unknown album")
            artist = str(self.album.get("artist") or "Unknown artist")
            painter.setPen(QColor("#f4f6fa"))
            font = painter.font()
            font.setPointSizeF(max(7.5, min(10.5, 8.3 * lod)))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(5, 141, 134, 17), Qt.AlignLeft | Qt.AlignVCenter, title[:32])
            if lod >= 0.7:
                font.setBold(False)
                font.setPointSizeF(max(7.0, min(9.5, 7.7 * lod)))
                painter.setFont(font)
                painter.setPen(QColor("#aab0ba"))
                painter.drawText(QRectF(5, 158, 134, 16), Qt.AlignLeft | Qt.AlignVCenter, artist[:32])

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
    viewportChanged = Signal()

    def wheelEvent(self, event):
        factor = 1.16 if event.angleDelta().y() > 0 else 1 / 1.16
        current = self.transform().m11()
        if (factor > 1 and current < 4.2) or (factor < 1 and current > 0.10):
            self.scale(factor, factor)
        self.viewportChanged.emit()

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model: dict[str, Any] = {}
        self.tiles: dict[str, _AlbumTile] = {}
        self.albums: dict[str, dict[str, Any]] = {}
        self._track_to_album: dict[tuple[str, str], str] = {}
        self.selected_key = ""
        self.current_key = ""
        self._art_requested: set[str] = set()
        self._animation: QVariantAnimation | None = None
        self._start_positions: dict[str, tuple[float, float]] = {}
        self._end_positions: dict[str, tuple[float, float]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        controls = QHBoxLayout()
        self.lens = QComboBox()
        self.lens.addItem("Sound", "sound")
        self.lens.addItem("Familiarity", "familiarity")
        self.lens.addItem("Time", "time")
        self.lens.addItem("A–Z shelves", "shelves")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find artist or album…")
        find = QPushButton("Find")
        now = QPushButton("Now playing")
        fit = QPushButton("Fit wall")
        controls.addWidget(QLabel("Arrange by"))
        controls.addWidget(self.lens)
        controls.addWidget(self.search, 1)
        controls.addWidget(find)
        controls.addWidget(now)
        controls.addWidget(fit)
        layout.addLayout(controls)

        self.scene = QGraphicsScene(self)
        self.view = _WallView(self.scene)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.view.setBackgroundBrush(QBrush(QColor("#0f1116")))
        self.view.setRenderHint(QPainter.Antialiasing, True)
        layout.addWidget(self.view, 1)

        self.status = QLabel("Add local music to build your Album Wall.")
        self.status.setStyleSheet("color:#aab0ba")
        layout.addWidget(self.status)

        self.lens.currentIndexChanged.connect(self._relayout)
        self.search.returnPressed.connect(self.find)
        find.clicked.connect(self.find)
        now.clicked.connect(self.centre_current)
        fit.clicked.connect(self.fit_wall)
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
        self.selected_key = ""

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
        self.fit_wall()
        albums = int(self.model.get("album_count") or len(self.albums))
        analysed = int(self.model.get("analysed_albums") or 0)
        self.status.setText(
            f"{albums:,} albums · {analysed:,} positioned from Flow analysis · "
            "wheel to zoom · drag to explore · double-click an album to play"
        )
        self._schedule_visible_art()

    def selected_album(self) -> dict[str, Any]:
        return dict(self.albums.get(self.selected_key) or {})

    def _select(self, key: str) -> None:
        if self.selected_key in self.tiles:
            self.tiles[self.selected_key].set_selected_visual(False)
        self.selected_key = str(key)
        if self.selected_key in self.tiles:
            self.tiles[self.selected_key].set_selected_visual(True)
            self.albumSelected.emit(dict(self.albums[self.selected_key]))

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
        QTimer.singleShot(560, self._schedule_visible_art)

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
        if self.view.transform().m11() < 0.8:
            self.view.resetTransform()
            self.view.scale(0.95, 0.95)
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

    def set_artwork(self, mapping: dict[str, str]) -> None:
        for key, path in dict(mapping or {}).items():
            tile = self.tiles.get(str(key))
            if tile and path:
                tile.set_cover_path(str(path))
        QTimer.singleShot(60, self._request_visible_art)


__all__ = ["AlbumWallWidget"]
