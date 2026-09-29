from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsEllipseItem,
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
    def wheelEvent(self, event):
        factor = 1.16 if event.angleDelta().y() > 0 else 1 / 1.16
        self.scale(factor, factor)


class _NodeItem(QGraphicsEllipseItem):
    def __init__(self, ref: str, node: dict[str, Any], selected, activated):
        super().__init__()
        self.ref = ref
        self.node = node
        self._selected = selected
        self._activated = activated
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(10)
        self.setToolTip(self._tooltip())

    def _tooltip(self) -> str:
        key_pc = int(self.node.get("key_pc", -1))
        key = _KEY_NAMES[key_pc] if 0 <= key_pc < 12 else "?"
        mode = str(self.node.get("key_mode") or "")
        if mode:
            key += f" {mode}"
        return (
            f"{self.node.get('artist') or 'Unknown artist'} — {self.node.get('title') or 'Unknown track'}\n"
            f"BPM {float(self.node.get('bpm') or 0):.0f} · {key} · "
            f"energy {float(self.node.get('energy') or 0):.0%}\n"
            f"taste {float(self.node.get('taste') or 0):.0%} · "
            f"rediscovery {float(self.node.get('rediscovery') or 0):.0%}"
        )

    def mousePressEvent(self, event):
        self._selected(self.ref)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._activated(self.ref)
        super().mouseDoubleClickEvent(event)

    def hoverEnterEvent(self, event):
        self.setScale(1.35)
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
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find artist or track on map…")
        reset = QPushButton("Reset view")
        controls.addWidget(QLabel("Colour"))
        controls.addWidget(self.mode)
        controls.addWidget(self.search, 1)
        controls.addWidget(reset)
        layout.addLayout(controls)

        self.scene = QGraphicsScene(self)
        self.view = _MapView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing, True)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.view.setBackgroundBrush(QBrush(QColor("#10141c")))
        layout.addWidget(self.view, 1)

        self.status = QLabel("Analyse your local library to build a Music Map.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#aab0ba")
        layout.addWidget(self.status)

        self.mode.currentIndexChanged.connect(lambda *_: self._recolour())
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
    ) -> None:
        self.model = dict(model or {})
        self.ref_map = {str(key): dict(value) for key, value in ref_map.items()}
        self.current_identity = _track_identity(dict(current_track or {})) if current_track else ""
        self.selected_ref = ""
        self.scene.clear()
        self.node_items.clear()

        nodes = [dict(x) for x in list(self.model.get("nodes") or []) if isinstance(x, dict)]
        edges = [dict(x) for x in list(self.model.get("edges") or []) if isinstance(x, dict)]
        by_ref = {str(node.get("ref") or ""): node for node in nodes}

        width, height, margin = 1280.0, 820.0, 60.0
        positions: dict[str, tuple[float, float]] = {}
        for node in nodes:
            ref = str(node.get("ref") or "")
            x = margin + (float(node.get("x") or 0.0) + 1.0) * 0.5 * (width - 2 * margin)
            y = margin + (1.0 - (float(node.get("y") or 0.0) + 1.0) * 0.5) * (height - 2 * margin)
            positions[ref] = (x, y)

        for edge in edges:
            a, b = str(edge.get("a") or ""), str(edge.get("b") or "")
            if a not in positions or b not in positions:
                continue
            ax, ay = positions[a]
            bx, by = positions[b]
            similarity = max(0.0, min(1.0, float(edge.get("similarity") or 0.0)))
            colour = QColor(118, 131, 153, int(35 + 85 * similarity))
            pen = QPen(colour)
            pen.setWidthF(0.35 + 1.1 * similarity)
            line = self.scene.addLine(ax, ay, bx, by, pen)
            line.setZValue(1)

        for ref, node in by_ref.items():
            if ref not in positions:
                continue
            x, y = positions[ref]
            taste = max(0.0, min(1.0, float(node.get("taste") or 0.0)))
            rediscovery = max(0.0, min(1.0, float(node.get("rediscovery") or 0.0)))
            radius = 4.5 + 3.5 * taste + 2.0 * rediscovery
            item = _NodeItem(ref, node, self._select_ref, self._activate_ref)
            item.setRect(-radius, -radius, radius * 2, radius * 2)
            item.setPos(x, y)
            self.scene.addItem(item)
            self.node_items[ref] = item

        self.scene.setSceneRect(0, 0, width, height)
        self._recolour()
        self.highlight_track(current_track or {})
        self.reset_view()
        analysed = int(self.model.get("analysed") or 0)
        total = int(self.model.get("input_profiles") or 0)
        if analysed:
            self.status.setText(
                f"{analysed:,} analysed tracks mapped from {total:,} local profiles. "
                "Nearby dots have similar Flow features; lines show the closest local neighbours."
            )
        else:
            self.status.setText("No cached Flow analysis yet. Use Analyse my library, then refresh the map.")

    def reset_view(self) -> None:
        self.view.resetTransform()
        if not self.scene.items():
            return
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def _recolour(self) -> None:
        mode = str(self.mode.currentData() or "sonic")
        for ref, item in self.node_items.items():
            node = item.node
            colour = self._node_colour(node, mode)
            track = self.ref_map.get(ref, {})
            is_current = bool(self.current_identity and _track_identity(track) == self.current_identity)
            is_selected = ref == self.selected_ref
            if is_current:
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
        self._recolour()
        track = dict(self.ref_map[ref])
        node = self.node_items[ref].node
        self.status.setText(
            f"{node.get('artist') or 'Unknown artist'} — {node.get('title') or 'Unknown track'} · "
            f"{float(node.get('bpm') or 0):.0f} BPM · energy {float(node.get('energy') or 0):.0%} · "
            f"taste {float(node.get('taste') or 0):.0%} · rediscovery {float(node.get('rediscovery') or 0):.0%}"
        )
        self.trackSelected.emit(track)

    def _activate_ref(self, ref: str) -> None:
        if ref in self.ref_map:
            self.trackActivated.emit(dict(self.ref_map[ref]))

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
