from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QBrush, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsObject,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


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
    """Visible album-sleeve card used as a point in the music landscape."""

    def __init__(self, ref: str, node: dict[str, Any], selected, activated):
        super().__init__()
        self.ref = ref
        self.node = node
        self._selected = selected
        self._activated = activated
        self._bounds = QRectF(0, 0, 184, 120)
        self._pen = QPen(QColor(255, 255, 255, 95), 1.0)
        self._brush = QBrush(QColor(91, 145, 194))
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(10)
        self.setToolTip(self._tooltip())

    def boundingRect(self) -> QRectF:
        return self._bounds

    def setCardSize(self, width: float, height: float) -> None:
        self.prepareGeometryChange()
        self._bounds = QRectF(0, 0, width, height)
        self.update()

    def setPen(self, pen: QPen) -> None:
        self._pen = QPen(pen)
        self.update()

    def setBrush(self, brush: QBrush) -> None:
        self._brush = QBrush(brush)
        self.update()

    def _tooltip(self) -> str:
        return (
            f"{self.node.get('artist') or 'Unknown artist'} — {self.node.get('title') or 'Unknown track'}\n"
            f"{float(self.node.get('bpm') or 0):.0f} BPM · energy {float(self.node.get('energy') or 0):.0%}"
        )

    def paint(self, painter: QPainter, option, widget=None):
        r = self._bounds
        compact = r.width() < 150
        radius = 9 if compact else 12
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 78))
        painter.drawRoundedRect(r.translated(2, 3), radius, radius)
        painter.setBrush(QColor("#1a2230"))
        painter.drawRoundedRect(r, radius, radius)
        art_w = min(r.height() - 16, r.width() * 0.38)
        art = QRectF(8, 8, art_w, r.height() - 16)
        gradient = QLinearGradient(art.topLeft(), art.bottomRight())
        gradient.setColorAt(0, self._brush.color().lighter(135))
        gradient.setColorAt(1, self._brush.color().darker(155))
        painter.fillRect(art, gradient)
        painter.setPen(QColor(255, 255, 255, 190))
        font = painter.font()
        font.setBold(True)
        font.setPointSizeF(16 if not compact else 10)
        painter.setFont(font)
        initials = "".join(x[0] for x in str(self.node.get("artist") or "♫").split()[:2]).upper()
        painter.drawText(art, Qt.AlignCenter, initials or "♫")
        left = art.right() + 9
        width = r.right() - left - 7
        font.setPointSizeF(9.5 if not compact else 7)
        painter.setFont(font)
        painter.setPen(QColor("#f4f6fa"))
        painter.drawText(QRectF(left, 10, width, r.height() * .42), Qt.AlignLeft | Qt.AlignVCenter,
                         str(self.node.get("title") or "Unknown track"))
        font.setBold(False)
        font.setPointSizeF(8 if not compact else 6.5)
        painter.setFont(font)
        painter.setPen(QColor("#aeb8c8"))
        painter.drawText(QRectF(left, r.height() * .50, width, r.height() * .25), Qt.AlignLeft | Qt.AlignTop,
                         str(self.node.get("artist") or "Unknown artist"))
        if not compact:
            painter.setPen(QColor("#8494a8"))
            painter.drawText(QRectF(left, r.bottom() - 24, width, 15), Qt.AlignLeft | Qt.AlignVCenter,
                             f"{float(self.node.get('bpm') or 0):.0f} BPM · {float(self.node.get('energy') or 0):.0%} energy")
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(self._pen))
        painter.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), radius, radius)

    def mousePressEvent(self, event):
        self._selected(self.ref)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._activated(self.ref)
        super().mouseDoubleClickEvent(event)

    def hoverEnterEvent(self, event):
        self.setScale(1.06)
        self.setZValue(30)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setScale(1.0)
        self.setZValue(10)
        super().hoverLeaveEvent(event)


class MusicMapWidget(QWidget):
    trackSelected = Signal(object)
    trackActivated = Signal(object)

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
        self.search.setPlaceholderText("Find artist or track on map…")
        reset = QPushButton("Fit map")
        self.connections_button = QPushButton("Connections…")
        self.connections_button.setObjectName("quietButton")
        self.connections_button.clicked.connect(
            lambda: self.edge_mode.setVisible(not self.edge_mode.isVisible())
        )
        controls.addWidget(QLabel("Colour"))
        controls.addWidget(self.mode)
        self.edge_mode.hide()
        controls.addWidget(self.connections_button)
        controls.addWidget(self.edge_mode)
        controls.addSpacing(8)
        controls.addWidget(self.search, 1)
        controls.addWidget(reset)
        layout.addLayout(controls)

        self.scene = QGraphicsScene(self)
        self.view = _MapView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing, True)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setBackgroundBrush(QBrush(QColor("#0e141d")))
        self.view.setMinimumHeight(340)
        layout.addWidget(self.view, 1)

        self.status = QLabel("Analyse your local library to build a Music Map.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#aab0ba")
        layout.addWidget(self.status)

        self.mode.currentIndexChanged.connect(lambda *_: self._recolour())
        self.edge_mode.currentIndexChanged.connect(lambda *_: self._redraw_edges())
        self.search.returnPressed.connect(self._find)
        reset.clicked.connect(self.reset_view)

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
        self.model = dict(model or {})
        self.ref_map = {str(key): dict(value) for key, value in ref_map.items()}
        self.knowledge_graph = dict(knowledge_graph or {})
        self.current_identity = _track_identity(dict(current_track or {})) if current_track else ""
        self.selected_ref = old_selected
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
            item = _NodeItem(ref, node, self._select_ref, self._activate_ref)
            if len(nodes) <= 55:
                card_w, card_h = 190.0, 126.0
            elif len(nodes) <= 180:
                card_w, card_h = 142.0, 94.0
            else:
                card_w, card_h = 112.0, 72.0
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
        analysed = int(self.model.get("analysed") or 0)
        total = int(self.model.get("input_profiles") or 0)
        if analysed:
            known = int(self.knowledge_graph.get("known_tracks") or 0)
            self.status.setText(
                f"{analysed:,} analysed tracks mapped from {total:,} local profiles · "
                f"{known:,} tracks have cached knowledge. "
                "Select a track to reveal its closest relationships; pan and zoom to explore."
            )
        else:
            self.status.setText("No cached Flow analysis yet. Use Analyse my library, then refresh the map.")

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
                    colour = QColor(126, 166, 205, int(95 + 120 * similarity))
                    width = 1.0 + 2.0 * similarity
                    z_value = 4
                else:
                    colour = QColor(118, 131, 153, int(22 + 52 * similarity))
                    width = 0.28 + 0.72 * similarity
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
                pen = QPen(QColor(255, 255, 255, 105))
                pen.setWidthF(0.8)
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
        self.status.setText(
            f"{node.get('artist') or 'Unknown artist'} — {node.get('title') or 'Unknown track'} · "
            f"{float(node.get('bpm') or 0):.0f} BPM · energy {float(node.get('energy') or 0):.0%} · "
            f"taste {float(node.get('taste') or 0):.0%} · rediscovery {float(node.get('rediscovery') or 0):.0%}"
            + connection_text
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

    def highlight_track(self, track: dict[str, Any]) -> None:
        self.current_identity = _track_identity(dict(track or {})) if track else ""
        self._recolour()

    def _find(self) -> None:
        query = self.search.text().strip().casefold()
        if not query:
            return
        for ref, item in self.node_items.items():
            node = item.node
            hay = f"{node.get('artist','')} {node.get('title','')} {node.get('album','')}".casefold()
            if query in hay:
                self._select_ref(ref)
                self.view.centerOn(item)
                return
        self.status.setText(f"No mapped track matches “{self.search.text().strip()}”.")


__all__ = ["MusicMapWidget"]
