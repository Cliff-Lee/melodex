from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QMimeData, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QFontMetrics
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
)


STAGE_MIME_TYPE = "application/x-melodex-journey-stage+json"

STAGE_EXPLANATIONS = {
    "calm": "Prefers gentler energy, tempo and rhythmic density.",
    "dark": "Prefers lower brightness and a darker tonal character.",
    "forgotten": "Looks for music with a strong rediscovery signal.",
    "energetic": "Prefers energy, tempo drive and rhythmic density.",
    "bright": "Prefers brighter spectral and tonal character.",
    "rhythmic": "Prefers rhythmic density, tempo drive and mixability.",
    "familiar": "Leans toward positively rated and previously played music.",
    "surprising": "Leans toward less familiar, less played music.",
}


def _stage_from_mime(mime) -> dict[str, Any]:
    if not mime.hasFormat(STAGE_MIME_TYPE):
        return {}
    try:
        stage = json.loads(bytes(mime.data(STAGE_MIME_TYPE)).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return stage if isinstance(stage, dict) else {}


class JourneyEndpointDropTarget(QPushButton):
    """Clickable route endpoint that also accepts a dragged Music Map track."""

    trackDropped = Signal(object)

    def __init__(self, endpoint: str, parent=None):
        super().__init__(parent)
        self.endpoint = "start" if str(endpoint).casefold() == "start" else "destination"
        self.track_label = ""
        self.setAcceptDrops(True)
        self.setMinimumHeight(52)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("journeyEndpointDropTarget")
        title = "START" if self.endpoint == "start" else "DESTINATION"
        self.setAccessibleName(f"Journey {title.casefold()} track")
        self.setAccessibleDescription(
            "Click to use the selected Music Map track, or drag a track from Music Map here."
        )
        self.setStyleSheet(
            "QPushButton#journeyEndpointDropTarget { border: 1px dashed #60758b; border-radius: 7px; "
            "background: #121a24; color: #e0e8f1; padding: 5px 10px; text-align: left; }"
            "QPushButton#journeyEndpointDropTarget:hover { border-color: #8ecfff; background: #172331; }"
        )
        self._refresh_text()

    def set_track_label(self, label: str) -> None:
        self.track_label = str(label or "")
        self._refresh_text()

    def _refresh_text(self) -> None:
        title = "Start" if self.endpoint == "start" else "Destination"
        detail = self.track_label or "Drop a track from Music Map"
        full_text = f"{title}  ·  {detail}"
        available_width = max(80, self.width() - 24)
        self.setText(QFontMetrics(self.font()).elidedText(full_text, Qt.ElideRight, available_width))
        self.setToolTip(
            f"{full_text}\nClick to use the selected Music Map track, or drag a track here."
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_text()

    def _accepts_track(self, mime) -> bool:
        stage = _stage_from_mime(mime)
        return str(stage.get("type") or "") == "track" and bool(str(stage.get("ref") or ""))

    def dragEnterEvent(self, event) -> None:
        if self._accepts_track(event.mimeData()):
            event.setDropAction(Qt.CopyAction)
            event.accept()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._accepts_track(event.mimeData()):
            event.setDropAction(Qt.CopyAction)
            event.accept()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        stage = _stage_from_mime(event.mimeData())
        if str(stage.get("type") or "") != "track" or not str(stage.get("ref") or ""):
            event.ignore()
            return
        self.set_track_label(str(stage.get("label") or "Selected track"))
        self.trackDropped.emit(stage)
        event.setDropAction(Qt.CopyAction)
        event.accept()


class JourneyStagePaletteButton(QPushButton):
    """A click-to-add semantic direction that can also be dragged to a slot."""

    def __init__(self, label: str, stage: dict[str, Any], parent=None):
        super().__init__(label, parent)
        self.stage = dict(stage)
        self._drag_origin = None
        self._drag_performed = False
        self.setObjectName("quietButton")
        self.setCursor(Qt.OpenHandCursor)
        explanation = STAGE_EXPLANATIONS.get(
            str(self.stage.get("constraint") or ""),
            "Add this direction to the listening route.",
        )
        self.setAccessibleName(f"Add {label} direction")
        self.setAccessibleDescription(
            f"Click to add at the end, or drag into the journey timeline. {explanation}"
        )
        self.setToolTip(
            f"<b>{label}</b><br>{explanation}<br><br>Click to add at the end, or drag into the timeline."
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_origin = event.position().toPoint()
            self._drag_performed = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_origin is None
            or not (event.buttons() & Qt.LeftButton)
            or (event.position().toPoint() - self._drag_origin).manhattanLength()
            < QApplication.startDragDistance()
        ):
            super().mouseMoveEvent(event)
            return
        self._drag_performed = True
        self.setDown(False)
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(
            STAGE_MIME_TYPE,
            json.dumps(self.stage, ensure_ascii=False).encode("utf-8"),
        )
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)
        self._drag_origin = None

    def mouseReleaseEvent(self, event):
        if self._drag_performed:
            self._drag_performed = False
            self._drag_origin = None
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self._drag_origin = None


class JourneyStageTimeline(QListWidget):
    """Accessible ordered stage timeline with drag and keyboard reordering."""

    orderChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("journeyStageTimeline")
        self.setAccessibleName("Journey stages")
        self.setAccessibleDescription(
            "An ordered left-to-right route shape. Drag stages to reorder them, or use the "
            "Move up and Move down buttons. Press Delete to remove the selected stage."
        )
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(False)
        self.setResizeMode(QListView.Adjust)
        self.setSpacing(8)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.setMinimumHeight(96)
        self.setMaximumHeight(120)
        self.setStyleSheet(
            "QListWidget#journeyStageTimeline { background: transparent; border: none; }"
            "QListWidget#journeyStageTimeline::item { background: #121a24; border: 1px solid #405367; "
            "border-radius: 8px; color: #e0e8f1; padding: 8px; }"
            "QListWidget#journeyStageTimeline::item:selected { background: #20384a; border-color: #8ecfff; }"
        )
        self.model().rowsMoved.connect(self._emit_order)

    def set_stages(self, stages: list[dict[str, Any]]) -> None:
        selected = self.currentRow()
        self.clear()
        if not stages:
            empty = QListWidgetItem("Drop a direction here · or click one to add it")
            empty.setFlags(Qt.NoItemFlags)
            empty.setSizeHint(QSize(260, 78))
            empty.setToolTip("Stages are optional. A route can go directly from its start to its destination.")
            self.addItem(empty)
            return
        for raw in stages:
            self.addItem(self._stage_item(dict(raw or {})))
        self._renumber()
        if self.count():
            self.setCurrentRow(min(max(selected, 0), self.count() - 1))

    def _stage_item(self, stage: dict[str, Any]) -> QListWidgetItem:
        kind = str(stage.get("type") or "constraint")
        label = str(stage.get("label") or "Stage")
        marker = "♪" if kind == "track" else "◆"
        item = QListWidgetItem()
        item.setData(Qt.UserRole, stage)
        item.setSizeHint(QSize(168, 78))
        explanation = (
            "Exact track waypoint · the route must pass through this track."
            if kind == "track"
            else STAGE_EXPLANATIONS.get(
                str(stage.get("constraint") or ""),
                f"Melodex scores tracks for the {label.casefold()} direction.",
            )
        )
        item.setToolTip(f"<b>{label}</b><br>{explanation}<br><br>Drag to change its position.")
        item.setData(Qt.AccessibleDescriptionRole, f"{label}. {explanation}")
        return item

    def _renumber(self) -> None:
        total = self.count()
        for row in range(total):
            item = self.item(row)
            stage = item.data(Qt.UserRole)
            if isinstance(stage, dict):
                marker = "♪" if str(stage.get("type") or "") == "track" else "◆"
                kind = "Track waypoint" if str(stage.get("type") or "") == "track" else "Direction"
                item.setText(
                    f"{row + 1} / {total}\n{marker}  {stage.get('label') or 'Stage'}\n{kind}"
                )

    def ordered_stages(self) -> list[dict[str, Any]]:
        return [
            dict(self.item(row).data(Qt.UserRole) or {})
            for row in range(self.count())
            if isinstance(self.item(row).data(Qt.UserRole), dict)
        ]

    def move_stage(self, source: int, target: int) -> bool:
        """Move one stage and emit the same update as a drag operation."""
        if source < 0 or source >= self.count() or target < 0 or target >= self.count():
            return False
        if source == target:
            return False
        item = self.takeItem(source)
        self.insertItem(target, item)
        self.setCurrentItem(item)
        self._emit_order()
        return True

    def move_current(self, offset: int) -> bool:
        row = self.currentRow()
        return self.move_stage(row, row + int(offset))

    def remove_current_stage(self) -> bool:
        row = self.currentRow()
        if row < 0 or row >= self.count() or not self.ordered_stages():
            return False
        self.takeItem(row)
        if not self.ordered_stages():
            self.set_stages([])
        else:
            self.setCurrentRow(min(row, self.count() - 1))
        self._emit_order()
        return True

    def insert_stage(self, stage: dict[str, Any], row: int = -1) -> bool:
        """Insert a copied palette stage at a timeline position."""
        if not isinstance(stage, dict) or not stage:
            return False
        if not self.ordered_stages():
            self.clear()
        if row < 0:
            row = self.count()
        row = min(max(int(row), 0), self.count())
        self.insertItem(row, self._stage_item(dict(stage)))
        self.setCurrentRow(row)
        self._emit_order()
        return True

    def _emit_order(self, *_args) -> None:
        self._renumber()
        self.orderChanged.emit(self.ordered_stages())

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(STAGE_MIME_TYPE):
            event.setDropAction(Qt.CopyAction)
            event.accept()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(STAGE_MIME_TYPE):
            event.setDropAction(Qt.CopyAction)
            event.accept()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasFormat(STAGE_MIME_TYPE):
            super().dropEvent(event)
            return
        try:
            stage = json.loads(bytes(event.mimeData().data(STAGE_MIME_TYPE)).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            event.ignore()
            return
        if not isinstance(stage, dict) or not stage:
            event.ignore()
            return
        row = self.indexAt(event.position().toPoint()).row()
        if row < 0 and self.ordered_stages():
            row = self.count()
        if not self.insert_stage(stage, row):
            event.ignore()
            return
        event.setDropAction(Qt.CopyAction)
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() in {Qt.Key_Delete, Qt.Key_Backspace} and self.remove_current_stage():
            event.accept()
            return
        if event.modifiers() & Qt.AltModifier:
            if event.key() == Qt.Key_Up and self.move_current(-1):
                event.accept()
                return
            if event.key() == Qt.Key_Down and self.move_current(1):
                event.accept()
                return
        super().keyPressEvent(event)
