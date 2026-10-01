from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QStyle,
)


def set_help(widget: QWidget, title: str, body: str) -> QWidget:
    """Attach explanatory help rather than a tooltip that repeats the label."""
    safe_title = str(title or "").strip()
    safe_body = str(body or "").strip()
    widget.setToolTip(
        f"<b>{safe_title}</b><br>{safe_body}"
        if safe_title
        else safe_body
    )
    return widget


def _cover_colours(key: str) -> tuple[QColor, QColor]:
    digest = hashlib.sha256(str(key or "").encode("utf-8", errors="ignore")).digest()
    hue = int.from_bytes(digest[:2], "big") % 360
    return (
        QColor.fromHsl(hue, 90, 70),
        QColor.fromHsl((hue + 28 + digest[2] % 48) % 360, 80, 42),
    )


def placeholder_cover(title: str, key: str, size: int = 160) -> QPixmap:
    """Generate a restrained deterministic fallback sleeve."""
    size = max(48, int(size))
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)

    a, b = _cover_colours(key)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, a.darker(170))
    gradient.setColorAt(1.0, b.darker(185))
    painter.fillRect(0, 0, size, size, QBrush(gradient))

    painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
    step = max(16, size // 7)
    x = -size
    while x < size * 2:
        painter.drawLine(x, size, x + size, 0)
        x += step

    words = [part for part in str(title or "?").replace("-", " ").split() if part]
    letters = (
        "".join(word[0] for word in words[:2]).upper()
        if len(words) > 1
        else str(title or "?")[:2].upper()
    )
    font = painter.font()
    font.setBold(True)
    font.setPointSizeF(max(16.0, size * 0.20))
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255, 155))
    painter.drawText(pix.rect(), Qt.AlignCenter, letters or "?")
    painter.end()
    return pix


class CoverLabel(QLabel):
    def __init__(self, size: int = 160, parent=None):
        super().__init__(parent)
        self._size = max(48, int(size))
        self.setFixedSize(self._size, self._size)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)
        self.setObjectName("coverArt")

    def set_cover(self, path: str, *, title: str = "", key: str = "") -> None:
        source = Path(str(path or "")).expanduser()
        pix = QPixmap(str(source)) if source.is_file() else QPixmap()
        if pix.isNull():
            pix = placeholder_cover(title, key or title, self._size)
        else:
            pix = pix.scaled(
                self._size,
                self._size,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            if pix.width() != self._size or pix.height() != self._size:
                x = max(0, (pix.width() - self._size) // 2)
                y = max(0, (pix.height() - self._size) // 2)
                pix = pix.copy(x, y, self._size, self._size)
        self.setPixmap(pix)


class ActionCard(QFrame):
    clicked = Signal()

    def __init__(
        self,
        title: str,
        body: str,
        *,
        eyebrow: str = "",
        action_text: str = "Open",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("actionCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(118)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 15)
        layout.setSpacing(5)

        if eyebrow:
            eyebrow_label = QLabel(str(eyebrow).upper())
            eyebrow_label.setObjectName("cardEyebrow")
            layout.addWidget(eyebrow_label)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.body_label = QLabel(body)
        self.body_label.setObjectName("cardBody")
        self.body_label.setWordWrap(True)
        layout.addWidget(self.body_label)
        layout.addStretch(1)

        self.action_label = QLabel(f"{action_text}  →")
        self.action_label.setObjectName("cardAction")
        layout.addWidget(self.action_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class SourceCard(QFrame):
    """Human-readable source/plugin row with a recognisable native icon."""

    _ICON_MAP = {
        "local": QStyle.SP_DriveHDIcon,
        "stream": QStyle.SP_MediaPlay,
        "provider": QStyle.SP_DriveNetIcon,
        "radio": QStyle.SP_MediaVolume,
        "recommendation": QStyle.SP_BrowserReload,
        "artwork": QStyle.SP_FileDialogContentsView,
        "lyrics": QStyle.SP_FileIcon,
        "context": QStyle.SP_MessageBoxInformation,
        "metadata": QStyle.SP_FileDialogDetailedView,
        "plugin": QStyle.SP_CommandLink,
        "built-in": QStyle.SP_ComputerIcon,
    }

    def __init__(
        self,
        name: str,
        description: str,
        status: str,
        *,
        kind: str = "",
        icon_key: str = "",
        origin: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("sourceCard")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(13, 11, 13, 11)
        outer.setSpacing(12)

        badge = QLabel()
        badge.setObjectName("sourceBadge")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(46, 46)
        standard = self._ICON_MAP.get(str(icon_key or "").casefold(), QStyle.SP_CommandLink)
        icon = self.style().standardIcon(standard)
        pixmap = icon.pixmap(25, 25)
        if not pixmap.isNull():
            badge.setPixmap(pixmap)
        else:
            badge.setText((str(name or "?").strip()[:1] or "?").upper())
        outer.addWidget(badge)

        text = QVBoxLayout()
        text.setSpacing(3)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel(str(name or "Unknown source"))
        title.setObjectName("sourceTitle")
        title_row.addWidget(title)
        if origin:
            origin_label = QLabel(str(origin))
            origin_label.setObjectName("originPill")
            title_row.addWidget(origin_label)
        title_row.addStretch(1)
        text.addLayout(title_row)

        desc = QLabel(str(description or ""))
        desc.setObjectName("sourceDescription")
        desc.setWordWrap(True)
        text.addWidget(desc)
        outer.addLayout(text, 1)

        if kind:
            kind_label = QLabel(str(kind))
            kind_label.setObjectName("sourceKind")
            outer.addWidget(kind_label)

        status_label = QLabel(str(status or ""))
        status_label.setObjectName("statusPill")
        outer.addWidget(status_label)


class EmptyState(QFrame):
    actionRequested = Signal()

    def __init__(
        self,
        title: str,
        body: str,
        action: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("emptyState")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 34, 28, 34)
        outer.setSpacing(10)
        outer.addStretch(1)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setObjectName("emptyTitle")
        outer.addWidget(title_label)

        body_label = QLabel(body)
        body_label.setWordWrap(True)
        body_label.setAlignment(Qt.AlignCenter)
        body_label.setObjectName("emptyBody")
        body_label.setMaximumWidth(560)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(body_label)
        row.addStretch(1)
        outer.addLayout(row)

        if action:
            button = QPushButton(action)
            button.setObjectName("primaryButton")
            button.clicked.connect(self.actionRequested)
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(button)
            row.addStretch(1)
            outer.addLayout(row)
        outer.addStretch(1)


class CommandPaletteDialog(QDialog):
    """Small action palette for expert navigation without exposing more chrome."""

    def __init__(
        self,
        actions: list[tuple[str, str, Callable[[], None]]],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Search Melodex")
        self.resize(620, 420)
        self._actions = list(actions)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Type an action, e.g. album wall, analyse library…")
        outer.addWidget(self.search)

        self.list = QListWidget()
        outer.addWidget(self.list, 1)

        self.search.textChanged.connect(self._refresh)
        self.search.returnPressed.connect(self._activate_current)
        self.list.itemActivated.connect(lambda _item: self._activate_current())
        self._refresh("")
        self.search.setFocus()

    def _refresh(self, query: str) -> None:
        needle = " ".join(str(query or "").casefold().split())
        self.list.clear()
        for index, (title, description, _callback) in enumerate(self._actions):
            haystack = f"{title} {description}".casefold()
            if needle and needle not in haystack:
                continue
            item = QListWidgetItem(f"{title}\n{description}")
            item.setData(Qt.UserRole, index)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _activate_current(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        index = int(item.data(Qt.UserRole))
        if not (0 <= index < len(self._actions)):
            return
        callback = self._actions[index][2]
        self.accept()
        callback()


__all__ = [
    "ActionCard",
    "CommandPaletteDialog",
    "CoverLabel",
    "EmptyState",
    "SourceCard",
    "placeholder_cover",
    "set_help",
]
