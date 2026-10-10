from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QMimeData, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QBrush, QDrag, QImage, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGraphicsObject,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .journey_composer import STAGE_MIME_TYPE


_KEY_NAMES = ("C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B")


def _track_identity(track: dict[str, Any]) -> str:
    for key in ("local_path", "rel", "track_id"):
        value = str(track.get(key) or "").strip()
        if value:
            return f"{key}:{value}"
    return "meta:" + "|".join(
        str(track.get(key) or "").strip().casefold()
        for key in ("artist", "album", "title")
    )


class _MapView(QGraphicsView):
    """Smooth map navigation with trackpad panning and bounded zoom."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._zoom_animation = QVariantAnimation(self)
        self._zoom_animation.setDuration(135)
        self._zoom_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._zoom_animation.valueChanged.connect(self._apply_zoom_value)
        self.setFrameShape(QFrame.NoFrame)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor("#111923"))
        gradient.setColorAt(0.52, QColor("#0d141d"))
        gradient.setColorAt(1.0, QColor("#091018"))
        painter.fillRect(rect, gradient)

    def _apply_zoom_value(self, value) -> None:
        target = float(value)
        current = max(0.0001, float(self.transform().m11()))
        factor = target / current
        if abs(factor - 1.0) > 0.0005:
            self.scale(factor, factor)

    def smooth_zoom(self, multiplier: float) -> None:
        current = max(0.0001, float(self.transform().m11()))
        target = max(0.62, min(3.0, current * float(multiplier)))
        if abs(target - current) < 0.002:
            return
        if self._zoom_animation.state() == QAbstractAnimation.Running:
            self._zoom_animation.stop()
        self._zoom_animation.setStartValue(current)
        self._zoom_animation.setEndValue(target)
        self._zoom_animation.start()

    def wheelEvent(self, event):
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
            return

        delta = event.angleDelta().y()
        if not delta and not pixel.isNull():
            delta = pixel.y()
        if not delta:
            return
        steps = max(-3.0, min(3.0, float(delta) / 120.0))
        self.smooth_zoom(1.10 ** steps)
        event.accept()


class _NodeItem(QGraphicsObject):
    """Album-art point that expands into a track detail card on hover."""

    def __init__(self, ref: str, node: dict[str, Any], selected, activated, stage_for_ref):
        super().__init__()
        self.ref = ref
        self.node = node
        self._selected = selected
        self._activated = activated
        self._stage_for_ref = stage_for_ref
        self._press_scene_pos = None
        self._bounds = QRectF(0, 0, 84, 84)
        self._base_size = (84.0, 84.0)
        self._hovered = False
        self._artwork = QPixmap()
        self._pen = QPen(QColor(255, 255, 255, 95), 1.0)
        self._brush = QBrush(QColor(91, 145, 194))
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(10)

    def boundingRect(self) -> QRectF:
        return self._bounds

    def setCardSize(self, width: float, height: float) -> None:
        self.prepareGeometryChange()
        self._base_size = (float(width), float(height))
        self._bounds = QRectF(0, 0, width, height)
        self.update()

    def setArtwork(self, image: QImage) -> bool:
        if not isinstance(image, QImage) or image.isNull():
            return False
        self._artwork = QPixmap.fromImage(image)
        self.update()
        return True

    def setPen(self, pen: QPen) -> None:
        self._pen = QPen(pen)
        self.update()

    def setBrush(self, brush: QBrush) -> None:
        self._brush = QBrush(brush)
        self.update()

    def _resize_on_hover(self, hovered: bool) -> None:
        center = self.mapToScene(self._bounds.center())
        width, height = (296.0, 148.0) if hovered else self._base_size
        self.prepareGeometryChange()
        self._bounds = QRectF(0, 0, width, height)
        self.setPos(center.x() - width / 2.0, center.y() - height / 2.0)
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        r = self._bounds
        expanded = self._hovered
        radius = 10 if expanded else 8
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 54))
        painter.drawRoundedRect(r.translated(2, 3), radius, radius)
        painter.setBrush(QColor(19, 27, 38, 245))
        painter.drawRoundedRect(r, radius, radius)
        inset = 8.0 if expanded else 3.0
        art_size = r.height() - inset * 2.0
        art = QRectF(inset, inset, art_size, art_size)
        clip = QPainterPath()
        clip.addRoundedRect(art, 6, 6)
        painter.save()
        painter.setClipPath(clip)
        if not self._artwork.isNull():
            painter.drawPixmap(
                art,
                self._artwork,
                QRectF(self._artwork.rect()),
            )
        else:
            gradient = QLinearGradient(art.topLeft(), art.bottomRight())
            gradient.setColorAt(0, self._brush.color().lighter(135))
            gradient.setColorAt(1, self._brush.color().darker(155))
            painter.fillRect(art, gradient)
            initials = "".join(x[0] for x in str(self.node.get("artist") or "♫").split()[:2]).upper()
            painter.setPen(QColor(255, 255, 255, 210))
            font = painter.font()
            font.setBold(True)
            font.setPointSizeF(max(10.0, art.width() * 0.28))
            painter.setFont(font)
            painter.drawText(art, Qt.AlignCenter, initials or "♫")
        painter.restore()

        if expanded:
            left = art.right() + 12.0
            width = r.right() - left - 10.0
            rows = (
                (str(self.node.get("title") or "Unknown track"), 13.0, True, "#f4f6fa"),
                (str(self.node.get("artist") or "Unknown artist"), 10.0, False, "#d1dae6"),
                (str(self.node.get("album") or "Album unknown"), 9.5, False, "#aebcce"),
                (
                    f"{float(self.node.get('bpm') or 0):.0f} BPM  ·  "
                    f"Energy {float(self.node.get('energy') or 0):.0%}  ·  "
                    f"Taste {float(self.node.get('taste') or 0):.0%}",
                    9.0,
                    False,
                    "#aebcce",
                ),
            )
            for index, (value, point_size, bold, color) in enumerate(rows):
                font = painter.font()
                font.setPointSizeF(point_size)
                font.setBold(bold)
                painter.setFont(font)
                painter.setPen(QColor(color))
                line = QRectF(left, 12 + index * 27, width, 22)
                value = painter.fontMetrics().elidedText(value, Qt.ElideRight, int(width))
                painter.drawText(line, Qt.AlignLeft | Qt.AlignVCenter, value)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(self._pen))
        painter.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), radius, radius)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_scene_pos = event.scenePos()
        self._selected(self.ref)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._press_scene_pos is not None
            and event.buttons() & Qt.LeftButton
            and (event.scenePos() - self._press_scene_pos).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            stage = self._stage_for_ref(self.ref)
            if stage:
                drag = QDrag(self)
                mime = QMimeData()
                mime.setData(
                    STAGE_MIME_TYPE,
                    json.dumps(stage, ensure_ascii=False).encode("utf-8"),
                )
                drag.setMimeData(mime)
                drag.exec(Qt.CopyAction)
                self._press_scene_pos = None
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._press_scene_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._activated(self.ref)
        super().mouseDoubleClickEvent(event)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self._resize_on_hover(True)
        self.setZValue(30)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self._resize_on_hover(False)
        self.setZValue(10)
        super().hoverLeaveEvent(event)


class MusicMapWidget(QWidget):
    trackSelected = Signal(object)
    trackActivated = Signal(object)
    artworkRequested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model: dict[str, Any] = {}
        self.ref_map: dict[str, dict[str, Any]] = {}
        self.node_items: dict[str, _NodeItem] = {}
        self.edge_items: list[Any] = []
        self.route_items: list[Any] = []
        self.positions: dict[str, tuple[float, float]] = {}
        self.knowledge_graph: dict[str, Any] = {}
        self.route_result: dict[str, Any] = {}
        self.route_start_ref = ""
        self.route_end_ref = ""
        self.selected_ref = ""
        self.current_identity = ""
        self._current_track: dict[str, Any] = {}
        # Camera history is a local UI concern and does not affect playback.
        self._back_locations: list[tuple[float, float, float, str]] = []
        self._forward_locations: list[tuple[float, float, float, str]] = []
        self._art_generation = 0
        self._art_prefetch_queue: list[str] = []
        self._visible_art_refs: set[str] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        controls = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem("Sonic colour", "sonic")
        self.mode.addItem("Energy", "energy")
        self.mode.addItem("Taste", "taste")
        self.mode.addItem("Rediscovery", "rediscovery")
        self.edge_mode = QComboBox()
        self.edge_mode.addItem("Selected relationships", "focused")
        self.edge_mode.addItem("All sonic links", "sonic")
        self.edge_mode.addItem("Actually connected · all", "knowledge")
        self.edge_mode.addItem("Same artist", "artist")
        self.edge_mode.addItem("Same album", "album")
        self.edge_mode.addItem("Production", "production")
        self.edge_mode.addItem("Performers", "performer")
        self.edge_mode.addItem("Composition credits", "composition_credit")
        self.edge_mode.addItem("Shared works", "work")
        self.edge_mode.addItem("Samples / remixes / versions", "song_relation")
        self.edge_mode.addItem("Artist relationships", "artist_relation")
        self.edge_mode.addItem("Recording places", "place")

        self.search = QLineEdit()
        self.search.setPlaceholderText("Find an artist or track on this map…")
        self.search.setAccessibleName("Find a track on Music Map")
        self.back_button = QPushButton("‹")
        self.back_button.setObjectName("quietButton")
        self.back_button.setFixedWidth(32)
        self.back_button.setAccessibleName("Go back to previous Music Map location")
        self.back_button.setToolTip("Back · Alt+Left")
        self.forward_button = QPushButton("›")
        self.forward_button.setObjectName("quietButton")
        self.forward_button.setFixedWidth(32)
        self.forward_button.setAccessibleName("Go forward to next Music Map location")
        self.forward_button.setToolTip("Forward · Alt+Right")
        self.now_playing_button = QPushButton("◎")
        self.now_playing_button.setObjectName("quietButton")
        self.now_playing_button.setFixedWidth(34)
        self.now_playing_button.setAccessibleName("Locate currently playing track on Music Map")
        self.now_playing_button.setToolTip("Find the track currently playing")
        self.back_button.setEnabled(False)
        self.forward_button.setEnabled(False)
        self.now_playing_button.setEnabled(False)
        self.view_button = QPushButton("View")
        self.view_button.setObjectName("quietButton")
        self.view_button.setToolTip("Colour and relationship settings")
        self.view_button.setAccessibleName("Show Music Map view settings")
        self.view_button.clicked.connect(self._toggle_view_settings)
        self.zoom_out_button = QPushButton("−")
        self.zoom_out_button.setObjectName("quietButton")
        self.zoom_out_button.setFixedWidth(38)
        self.zoom_out_button.setAccessibleName("Zoom out of Music Map")
        self.zoom_out_button.setToolTip("Zoom out · Ctrl/⌘-scroll also works")
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setObjectName("quietButton")
        self.zoom_in_button.setFixedWidth(38)
        self.zoom_in_button.setAccessibleName("Zoom into Music Map")
        self.zoom_in_button.setToolTip("Zoom in · Ctrl/⌘-scroll also works")
        reset = QPushButton("Fit")
        reset.setObjectName("quietButton")
        reset.setToolTip("Show the whole mapped collection")
        reset.setAccessibleName("Fit Music Map to view")
        controls.addWidget(self.back_button)
        controls.addWidget(self.forward_button)
        controls.addWidget(self.search, 1)
        controls.addWidget(self.now_playing_button)
        controls.addWidget(self.view_button)
        controls.addWidget(self.zoom_out_button)
        controls.addWidget(self.zoom_in_button)
        controls.addWidget(reset)
        layout.addLayout(controls)

        # The appearance controls float *over* the map, not in its layout.
        self.view_settings_panel = QFrame(self)
        self.view_settings_panel.setObjectName("powerPanel")
        view_layout = QVBoxLayout(self.view_settings_panel)
        view_layout.setContentsMargins(12, 10, 12, 10)
        view_layout.addWidget(QLabel("Colour by"))
        view_layout.addWidget(self.mode)
        view_layout.addWidget(QLabel("Connections"))
        view_layout.addWidget(self.edge_mode)
        view_layout.addStretch(1)
        self.view_settings_panel.hide()

        self.scene = QGraphicsScene(self)
        self.view = _MapView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing, True)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.view, 1)

        self.status = QLabel("Analyse your local library to build a Music Map.")
        self.status.setWordWrap(True)
        self.status.setObjectName("mutedText")
        layout.addWidget(self.status)

        self.mode.currentIndexChanged.connect(lambda *_: self._recolour())
        self.edge_mode.currentIndexChanged.connect(lambda *_: self._redraw_edges())
        self.search.returnPressed.connect(self._find)
        self.back_button.clicked.connect(self.navigate_back)
        self.forward_button.clicked.connect(self.navigate_forward)
        self.now_playing_button.clicked.connect(self.locate_now_playing)
        self._back_shortcut = QShortcut(QKeySequence("Alt+Left"), self)
        self._back_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._back_shortcut.activated.connect(self.navigate_back)
        self._forward_shortcut = QShortcut(QKeySequence("Alt+Right"), self)
        self._forward_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._forward_shortcut.activated.connect(self.navigate_forward)
        self.zoom_out_button.clicked.connect(lambda: self.view.smooth_zoom(1 / 1.25))
        self.zoom_in_button.clicked.connect(lambda: self.view.smooth_zoom(1.25))
        reset.clicked.connect(self._fit_with_history)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._position_view_settings)

    def _position_view_settings(self) -> None:
        if not hasattr(self, "view_settings_panel") or not hasattr(self, "view"):
            return
        rect = self.view.geometry()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        margin = 10
        width = min(250, max(1, rect.width() - 2 * margin))
        height = min(172, max(1, rect.height() - 2 * margin))
        self.view_settings_panel.setGeometry(
            rect.right() - width - margin + 1,
            rect.top() + margin,
            width,
            height,
        )

    def _toggle_view_settings(self) -> None:
        visible = not self.view_settings_panel.isVisible()
        self._position_view_settings()
        self.view_settings_panel.setVisible(visible)
        if visible:
            self.view_settings_panel.raise_()

    @staticmethod
    def _node_colour(node: dict[str, Any], mode: str) -> QColor:
        if mode == "energy":
            energy = max(0.0, min(1.0, float(node.get("energy") or 0.0)))
            hue = int(220 - 205 * energy)
            return QColor.fromHsv(hue, 190, 235)
        if mode == "taste":
            taste = max(0.0, min(1.0, float(node.get("taste") or 0.0)))
            return QColor.fromHsv(int(205 - 85 * taste), int(90 + 145 * taste), 235)
        if mode == "rediscovery":
            value = max(0.0, min(1.0, float(node.get("rediscovery") or 0.0)))
            return QColor.fromHsv(int(280 - 235 * value), int(65 + 180 * value), 235)

        pc = int(node.get("key_pc", -1))
        if 0 <= pc < 12:
            hue = int((pc / 12.0) * 359)
        else:
            hue = 210
        energy = max(0.0, min(1.0, float(node.get("energy") or 0.0)))
        return QColor.fromHsv(hue, int(110 + 105 * energy), int(185 + 60 * energy))

    def set_map(
        self,
        model: dict[str, Any],
        ref_map: dict[str, dict[str, Any]],
        current_track: dict[str, Any] | None = None,
        knowledge_graph: dict[str, Any] | None = None,
    ) -> None:
        old_refs = set(self.node_items)
        old_selected = self.selected_ref
        old_center = (
            self.view.mapToScene(self.view.viewport().rect().center())
            if old_refs else None
        )
        old_scale = float(self.view.transform().m11()) if old_refs else 1.0
        self._art_generation += 1
        self.model = dict(model or {})
        self.ref_map = {str(key): dict(value) for key, value in ref_map.items()}
        self.knowledge_graph = dict(knowledge_graph or {})
        self._current_track = dict(current_track or {})
        self.current_identity = _track_identity(self._current_track) if self._current_track else ""
        self.now_playing_button.setEnabled(bool(self._current_track))
        self.selected_ref = old_selected
        self._art_prefetch_queue.clear()
        self.scene.clear()
        self.node_items.clear()
        self.edge_items.clear()
        self.route_items.clear()
        self.positions.clear()
        self.route_result = {}
        self.route_start_ref = ""
        self.route_end_ref = ""

        nodes = [dict(x) for x in list(self.model.get("nodes") or []) if isinstance(x, dict)]
        by_ref = {str(node.get("ref") or ""): node for node in nodes}

        width, height, margin = 1280.0, 820.0, 60.0
        for node in nodes:
            ref = str(node.get("ref") or "")
            x = margin + (float(node.get("x") or 0.0) + 1.0) * 0.5 * (width - 2 * margin)
            y = margin + (1.0 - (float(node.get("y") or 0.0) + 1.0) * 0.5) * (height - 2 * margin)
            self.positions[ref] = (x, y)

        for ref, node in by_ref.items():
            if ref not in self.positions:
                continue
            x, y = self.positions[ref]
            item = _NodeItem(
                ref,
                node,
                self._select_ref,
                self._activate_ref,
                self._journey_stage_for_ref,
            )
            tooltip = (
                "Drag this track to the Journey Composer timeline to add it as an exact waypoint."
            )
            rediscovery_reason = str(node.get("rediscovery_reason") or "").strip()
            if rediscovery_reason:
                tooltip += f"\nRediscovery: {rediscovery_reason}"
            taste_reason = str(node.get("taste_reason") or "").strip()
            if taste_reason:
                tooltip += f"\nTaste model: {taste_reason}"
            item.setToolTip(tooltip)
            if len(nodes) <= 55:
                card_w, card_h = 86.0, 86.0
            elif len(nodes) <= 180:
                card_w, card_h = 66.0, 66.0
            elif len(nodes) <= 420:
                card_w, card_h = 40.0, 40.0
            else:
                # Dense libraries show album covers as small map points at
                # overview scale; zoom and hover reveal the full-size artwork
                # and track details without turning the whole map into a wall.
                card_w, card_h = 28.0, 28.0
            item.setCardSize(card_w, card_h)
            item.setPos(x - card_w / 2.0, y - card_h / 2.0)
            self.scene.addItem(item)
            self.node_items[ref] = item

        self.scene.setSceneRect(0, 0, width, height)
        new_refs = set(self.node_items)
        overlap = len(old_refs & new_refs) / max(1, len(old_refs))
        if self.selected_ref not in new_refs:
            self.selected_ref = ""
        self._redraw_edges()
        self._redraw_route()
        self._recolour()
        self.highlight_track(current_track or {})
        if old_refs and overlap >= 0.5 and old_center is not None:
            self.view.resetTransform()
            scale = max(0.62, min(3.0, old_scale))
            self.view.scale(scale, scale)
            self.view.centerOn(old_center)
        else:
            self.reset_view()
        # The projection can move after a new analysis. Do not replay stale
        # scene coordinates against a different map, even with shared refs.
        self._back_locations.clear()
        self._forward_locations.clear()
        self._update_navigation_buttons()
        analysed = int(self.model.get("analysed") or 0)
        total = int(self.model.get("input_profiles") or 0)
        if analysed:
            known = int(self.knowledge_graph.get("known_tracks") or 0)
            self.status.setText(
                f"{analysed:,} tracks mapped · {known:,} with cached knowledge · "
                "select a track for relationships · drag to pan · zoom into local clusters"
            )
        else:
            self.status.setText("No cached Flow analysis yet. Use Analyse my library, then refresh the map.")
        visible_rect = self.view.mapToScene(self.view.viewport().rect()).boundingRect()
        visible_refs = [
            item.ref
            for item in self.scene.items(
                visible_rect,
                Qt.IntersectsItemBoundingRect,
                Qt.AscendingOrder,
            )
            if isinstance(item, _NodeItem) and item.ref in self.ref_map
        ]
        self._visible_art_refs = set(visible_refs)
        self._art_prefetch_queue = visible_refs + [
            ref for ref in self.node_items
            if ref in self.ref_map and ref not in self._visible_art_refs
        ]
        self._request_artwork_batch()

    def _request_artwork_batch(self) -> None:
        batch = []
        while self._art_prefetch_queue and len(batch) < 36:
            ref = self._art_prefetch_queue.pop(0)
            track = dict(self.ref_map.get(ref) or {})
            if not track:
                continue
            batch.append({
                "ref": ref,
                "generation": self._art_generation,
                "track": track,
                "prefetch": ref not in self._visible_art_refs,
            })
        if batch:
            self.artworkRequested.emit(batch)

    def set_artwork(self, mapping: dict[str, object]) -> None:
        """Apply prepared local cover thumbnails to their map points."""
        for raw_ref, raw in dict(mapping or {}).items():
            ref = str(raw_ref)
            if ref not in self.node_items or not isinstance(raw, dict):
                continue
            payload = dict(raw)
            if int(payload.get("generation") or 0) != self._art_generation:
                continue
            image = payload.get("image")
            if isinstance(image, QImage):
                self.node_items[ref].setArtwork(image)
        if self._art_prefetch_queue:
            QTimer.singleShot(0, self._request_artwork_batch)

    @staticmethod
    def _knowledge_colour(kind: str) -> QColor:
        colours = {
            "artist": QColor(77, 190, 185, 150),
            "album": QColor(92, 139, 230, 135),
            "production": QColor(235, 185, 85, 170),
            "performer": QColor(103, 205, 120, 165),
            "composition_credit": QColor(191, 122, 230, 165),
            "people": QColor(205, 160, 100, 150),
            "work": QColor(174, 110, 235, 175),
            "song_relation": QColor(235, 92, 126, 190),
            "artist_relation": QColor(83, 210, 155, 175),
            "place": QColor(235, 142, 72, 165),
        }
        return colours.get(str(kind), QColor(160, 170, 190, 135))

    def _redraw_edges(self) -> None:
        for item in list(self.edge_items):
            try:
                self.scene.removeItem(item)
            except Exception:
                pass
        self.edge_items.clear()
        if not self.positions:
            return

        mode = str(self.edge_mode.currentData() or "focused")
        if mode in {"focused", "sonic"}:
            edges = [
                dict(x)
                for x in list(self.model.get("edges") or [])
                if isinstance(x, dict)
            ]
            if mode == "focused":
                if not self.selected_ref:
                    return
                edges = [
                    edge
                    for edge in edges
                    if self.selected_ref
                    in {str(edge.get("a") or ""), str(edge.get("b") or "")}
                ]
            for edge in edges:
                a, b = str(edge.get("a") or ""), str(edge.get("b") or "")
                if a not in self.positions or b not in self.positions:
                    continue
                ax, ay = self.positions[a]
                bx, by = self.positions[b]
                similarity = max(0.0, min(1.0, float(edge.get("similarity") or 0.0)))
                if mode == "focused":
                    colour = QColor(126, 166, 205, int(72 + 92 * similarity))
                    width = 0.9 + 1.7 * similarity
                    z_value = 4
                else:
                    colour = QColor(118, 131, 153, int(10 + 30 * similarity))
                    width = 0.22 + 0.52 * similarity
                    z_value = 1
                pen = QPen(colour)
                pen.setWidthF(width)
                line = self.scene.addLine(ax, ay, bx, by, pen)
                line.setZValue(z_value)
                line.setToolTip(f"Sonic neighbour · similarity {similarity:.0%}")
                self.edge_items.append(line)
            return

        edges = [
            dict(x)
            for x in list(self.knowledge_graph.get("edges") or [])
            if isinstance(x, dict)
        ]
        allowed = None if mode == "knowledge" else {mode}
        for edge in edges:
            kind = str(edge.get("kind") or "")
            if allowed is not None and kind not in allowed:
                continue
            a, b = str(edge.get("a") or ""), str(edge.get("b") or "")
            if a not in self.positions or b not in self.positions:
                continue
            ax, ay = self.positions[a]
            bx, by = self.positions[b]
            strength = max(0.0, min(1.0, float(edge.get("strength") or 0.0)))
            colour = self._knowledge_colour(kind)
            pen = QPen(colour)
            pen.setWidthF(0.7 + 2.0 * strength)
            line = self.scene.addLine(ax, ay, bx, by, pen)
            line.setZValue(2)
            label = str(edge.get("label") or kind or "Knowledge connection")
            evidence = str(edge.get("evidence") or "")
            line.setToolTip(label + (f"\n{evidence}" if evidence else ""))
            self.edge_items.append(line)

        if mode != "sonic" and not self.edge_items:
            self.status.setText(
                "No cached connections of this type yet. Listen normally or use Enrich knowledge on the Music Map."
            )
        self._redraw_route()

    def set_knowledge_graph(self, graph: dict[str, Any]) -> None:
        self.knowledge_graph = dict(graph or {})
        self._redraw_edges()

    def selected_ref_value(self) -> str:
        return str(self.selected_ref or "")

    def set_route_endpoints(self, start_ref: str = "", end_ref: str = "") -> None:
        self.route_start_ref = str(start_ref or "")
        self.route_end_ref = str(end_ref or "")
        self.route_result = {}
        self._redraw_route()
        self._recolour()

    def show_route(self, result: dict[str, Any]) -> None:
        self.route_result = dict(result or {})
        refs = [str(x) for x in list(self.route_result.get("path_refs") or []) if str(x)]
        if refs:
            self.route_start_ref = refs[0]
            self.route_end_ref = refs[-1]
        self._redraw_route()
        self._recolour()
        surface = "Journey Designer" if self.route_result.get("journey") else "Pathfinder"
        if self.route_result.get("found"):
            self.status.setText(
                surface + " · "
                + str(self.route_result.get("reason") or "route ready")
                + f" · score {float(self.route_result.get('score') or 0.0):.0%}"
            )
        else:
            self.status.setText(
                surface + " · " + str(self.route_result.get("reason") or "no route found")
            )

    def clear_route(self) -> None:
        self.route_result = {}
        self.route_start_ref = ""
        self.route_end_ref = ""
        self._redraw_route()
        self._recolour()

    def _redraw_route(self) -> None:
        for item in list(self.route_items):
            try:
                self.scene.removeItem(item)
            except Exception:
                pass
        self.route_items.clear()
        refs = [str(x) for x in list(self.route_result.get("path_refs") or []) if str(x)]
        hops = [
            dict(x)
            for x in list(self.route_result.get("hops") or [])
            if isinstance(x, dict)
        ]
        if len(refs) < 2:
            return
        for index, (a, b) in enumerate(zip(refs, refs[1:])):
            if a not in self.positions or b not in self.positions:
                continue
            ax, ay = self.positions[a]
            bx, by = self.positions[b]
            pen = QPen(QColor("#71d8ff"))
            pen.setWidthF(4.2)
            line = self.scene.addLine(ax, ay, bx, by, pen)
            line.setZValue(6)
            reason = str(hops[index].get("reason") or "Pathfinder hop") if index < len(hops) else "Pathfinder hop"
            if index < len(hops) and hops[index].get("journey_stage"):
                stage = str(hops[index].get("journey_stage") or "")
                fit = float(hops[index].get("journey_stage_score") or 0.0)
                stage_reason = str(hops[index].get("journey_stage_reason") or "")
                reason += f"\nJourney stage: {stage} · fit {fit:.0%}"
                if stage_reason:
                    reason += f"\n{stage_reason}"
            line.setToolTip(f"Step {index + 1}: {reason}")
            self.route_items.append(line)

            label = self.scene.addText(str(index + 1))
            label.setDefaultTextColor(QColor("#dff7ff"))
            label.setZValue(7)
            label.setScale(0.75)
            label.setPos((ax + bx) / 2.0 - 5.0, (ay + by) / 2.0 - 10.0)
            label.setToolTip(reason)
            self.route_items.append(label)

    def reset_view(self) -> None:
        self.view.resetTransform()
        if not self.scene.items():
            return
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        # A slightly closer starting view makes the map feel explorable instead
        # of presenting the whole library as a tiny diagram.
        self.view.scale(1.16, 1.16)
        self.view.centerOn(self.scene.sceneRect().center())

    def _capture_location(self) -> tuple[float, float, float, str]:
        center = self.view.mapToScene(self.view.viewport().rect().center())
        return (float(center.x()), float(center.y()),
                float(self.view.transform().m11()), str(self.selected_ref or ""))

    @staticmethod
    def _same_location(a: tuple[float, float, float, str],
                       b: tuple[float, float, float, str]) -> bool:
        return (a[3] == b[3] and abs(a[0] - b[0]) < 1.0
                and abs(a[1] - b[1]) < 1.0 and abs(a[2] - b[2]) < 0.001)

    def _update_navigation_buttons(self) -> None:
        self.back_button.setEnabled(bool(self._back_locations))
        self.forward_button.setEnabled(bool(self._forward_locations))

    def _remember_departure(self, previous: tuple[float, float, float, str]) -> None:
        if self._same_location(previous, self._capture_location()):
            return
        self._back_locations.append(previous)
        del self._back_locations[:-32]
        self._forward_locations.clear()
        self._update_navigation_buttons()

    def _restore_location(self, location: tuple[float, float, float, str]) -> None:
        x, y, scale, ref = location
        self.view.resetTransform()
        self.view.scale(max(0.0001, scale), max(0.0001, scale))
        self.view.centerOn(x, y)
        if ref and ref in self.ref_map:
            self._select_ref(ref)
        elif self.selected_ref:
            self.selected_ref = ""
            self._redraw_edges()
            self._recolour()
            self.trackSelected.emit({})

    def navigate_back(self) -> None:
        if not self._back_locations:
            return
        current = self._capture_location()
        destination = self._back_locations.pop()
        self._forward_locations.append(current)
        self._restore_location(destination)
        self._update_navigation_buttons()

    def navigate_forward(self) -> None:
        if not self._forward_locations:
            return
        current = self._capture_location()
        destination = self._forward_locations.pop()
        self._back_locations.append(current)
        self._restore_location(destination)
        self._update_navigation_buttons()

    def focus_ref(self, ref: str) -> bool:
        """Select and centre a mapped track, keeping a reversible camera visit."""
        item = self.node_items.get(str(ref or ""))
        if item is None:
            return False
        previous = self._capture_location()
        self._select_ref(str(ref))
        self.view.centerOn(item)
        self._remember_departure(previous)
        return True

    def locate_now_playing(self) -> bool:
        """Navigate only when playing music is represented in this map preview."""
        if not self._current_track:
            self.status.setText("No track is currently playing.")
            return False
        identity = _track_identity(self._current_track)
        for ref, track in self.ref_map.items():
            if _track_identity(track) == identity:
                return self.focus_ref(ref)
        self.status.setText(
            "The currently playing track is not in this map's analysed preview. "
            "Playback continues normally."
        )
        return False

    def _fit_with_history(self) -> None:
        previous = self._capture_location()
        self.reset_view()
        self._remember_departure(previous)

    def _recolour(self) -> None:
        mode = str(self.mode.currentData() or "sonic")
        for ref, item in self.node_items.items():
            node = item.node
            colour = self._node_colour(node, mode)
            track = self.ref_map.get(ref, {})
            is_current = bool(self.current_identity and _track_identity(track) == self.current_identity)
            is_selected = ref == self.selected_ref
            route_refs = set(str(x) for x in list(self.route_result.get("path_refs") or []))
            waypoint_refs = set(str(x) for x in list(self.route_result.get("waypoint_refs") or []))
            if ref == self.route_start_ref:
                pen = QPen(QColor("#6ee7c8"))
                pen.setWidthF(3.5)
            elif ref == self.route_end_ref:
                pen = QPen(QColor("#ff8fb1"))
                pen.setWidthF(3.5)
            elif ref in waypoint_refs:
                pen = QPen(QColor("#c89bff"))
                pen.setWidthF(3.4)
            elif ref in route_refs:
                pen = QPen(QColor("#7ed0ff"))
                pen.setWidthF(2.7)
            elif is_current:
                pen = QPen(QColor("#ffffff"))
                pen.setWidthF(3.0)
            elif is_selected:
                pen = QPen(QColor("#f5d76e"))
                pen.setWidthF(2.5)
            else:
                pen = QPen(QColor(255, 255, 255, 42))
                pen.setWidthF(0.7)
            item.setPen(pen)
            item.setBrush(QBrush(colour))

    def _select_ref(self, ref: str) -> None:
        if ref not in self.ref_map:
            return
        self.selected_ref = ref
        if str(self.edge_mode.currentData() or "") == "focused":
            self._redraw_edges()
        self._recolour()
        track = dict(self.ref_map[ref])
        node = self.node_items[ref].node
        connections = []
        for edge in list(self.knowledge_graph.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            if ref in {str(edge.get("a") or ""), str(edge.get("b") or "")}:
                label = str(edge.get("label") or edge.get("kind") or "").strip()
                if label and label not in connections:
                    connections.append(label)
        connection_text = (
            " · connections: " + ", ".join(connections[:3])
            if connections
            else ""
        )
        rediscovery_reason = str(node.get("rediscovery_reason") or "").strip()
        rediscovery_text = f" · {rediscovery_reason}" if rediscovery_reason else ""
        taste_reason = str(node.get("taste_reason") or "").strip()
        taste_text = f" · {taste_reason}" if taste_reason else ""
        self.status.setText(
            f"{node.get('artist') or 'Unknown artist'} — {node.get('title') or 'Unknown track'} · "
            f"{float(node.get('bpm') or 0):.0f} BPM · energy {float(node.get('energy') or 0):.0%} · "
            f"taste {float(node.get('taste') or 0):.0%} · rediscovery {float(node.get('rediscovery') or 0):.0%}"
            + rediscovery_text
            + taste_text
            + connection_text
            + " · drag to Compose to add as a waypoint"
        )
        self.trackSelected.emit(track)

    def _activate_ref(self, ref: str) -> None:
        if ref in self.ref_map:
            self.trackActivated.emit(dict(self.ref_map[ref]))

    def mapped_tracks(self) -> list[dict[str, Any]]:
        return [
            dict(self.ref_map[ref])
            for ref in self.node_items
            if ref in self.ref_map
        ]

    def mapped_refs(self) -> list[str]:
        return [ref for ref in self.node_items if ref in self.ref_map]

    def selected_track(self) -> dict[str, Any]:
        if self.selected_ref and self.selected_ref in self.ref_map:
            return dict(self.ref_map[self.selected_ref])
        return {}

    def related_tracks(self, ref: str, limit: int = 2) -> list[dict[str, Any]]:
        """Explain genuine mapped connections; never infer ties from screen distance."""
        source = str(ref or "")
        if source not in self.node_items or limit <= 0:
            return []
        sonic: dict[str, dict[str, Any]] = {}
        factual: dict[str, dict[str, Any]] = {}
        for edge in self.model.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            a, b = str(edge.get("a") or ""), str(edge.get("b") or "")
            other = b if a == source else a if b == source else ""
            if not other or other not in self.node_items:
                continue
            similarity = max(0.0, min(1.0, float(edge.get("similarity") or 0.0)))
            existing = sonic.get(other)
            if existing is None or similarity > existing["score"]:
                sonic[other] = {
                    "ref": other, "kind": "Sonic neighbour",
                    "reason": f"Audio-feature similarity estimate: {similarity:.0%}",
                    "score": similarity,
                }
        for edge in self.knowledge_graph.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            a, b = str(edge.get("a") or ""), str(edge.get("b") or "")
            other = b if a == source else a if b == source else ""
            if not other or other not in self.node_items:
                continue
            kind = str(edge.get("kind") or "connection")
            label = str(edge.get("label") or "").strip()
            evidence = str(edge.get("evidence") or "").strip()
            strength = max(0.0, min(1.0, float(edge.get("strength") or 0.0)))
            short_kind = {
                "artist": "Same artist", "album": "Same album",
                "production": "Production", "performer": "Performer",
                "composition_credit": "Composition", "work": "Shared work",
                "song_relation": "Song relationship", "artist_relation": "Artist link",
                "place": "Recording place",
            }.get(kind, "Known connection")
            explanation = short_kind + (f": {label}" if label else "")
            if evidence:
                explanation += f" · {evidence}"
            entry = {
                "ref": other, "kind": short_kind, "reason": explanation,
                "score": strength,
            }
            if other not in factual or strength > factual[other]["score"]:
                factual[other] = entry

        def ranked(rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
            return sorted(rows.values(), key=lambda row: (-row["score"], row["ref"]))

        # Mix the strongest sonic and factual links where both are available.
        # Otherwise show the next-best genuine relationships, without duplicates.
        picked: list[dict[str, Any]] = []
        seen: set[str] = set()
        for candidate in (
            ranked(sonic)[:1] + ranked(factual)[:1]
            + ranked(sonic)[1:] + ranked(factual)[1:]
        ):
            if candidate["ref"] in seen:
                continue
            seen.add(candidate["ref"])
            track = self.ref_map.get(candidate["ref"], {})
            if not track:
                continue
            picked.append({
                **candidate,
                "artist": str(track.get("artist") or "Unknown artist"),
                "title": str(track.get("title") or "Unknown track"),
            })
            if len(picked) >= limit:
                break
        return picked

    def _journey_stage_for_ref(self, ref: str) -> dict[str, Any]:
        track = dict(self.ref_map.get(str(ref) or "") or {})
        if not track:
            return {}
        artist = str(track.get("artist") or "Unknown artist")
        title = str(track.get("title") or "Unknown track")
        return {
            "type": "track",
            "ref": str(ref),
            "label": f"{artist} — {title}",
        }

    def highlight_track(self, track: dict[str, Any]) -> None:
        self._current_track = dict(track or {})
        self.current_identity = _track_identity(self._current_track) if self._current_track else ""
        self.now_playing_button.setEnabled(bool(self._current_track))
        self._recolour()

    def _find(self) -> None:
        query = self.search.text().strip().casefold()
        if not query:
            return
        for ref, item in self.node_items.items():
            node = item.node
            hay = f"{node.get('artist','')} {node.get('title','')} {node.get('album','')}".casefold()
            if query in hay:
                self.focus_ref(ref)
                return
        self.status.setText(f"No mapped track matches “{self.search.text().strip()}”.")


__all__ = ["MusicMapWidget"]
