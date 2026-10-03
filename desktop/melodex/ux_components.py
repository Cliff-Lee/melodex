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


def source_icon_spec(name: str = "", icon_key: str = "") -> tuple[str, str, str]:
    """Return a compact recognisable glyph tile for sources/plugins."""
    name_key=" ".join(str(name or "").casefold().split())
    key=str(icon_key or "").casefold().strip()

    specific=(
        ("internet archive", ("IA", "#8e7af0", "#2d2750")),
        ("librivox", ("LV", "#e08b48", "#4f311d")),
        ("somafm", ("S", "#e36d94", "#502536")),
        ("radio browser", ("◉", "#46bbb4", "#173f40")),
        ("wikimedia", ("W", "#75a1e3", "#253b59")),
        ("ccmixter", ("CC", "#87b85d", "#30471f")),
        ("jamendo", ("J", "#ee8c48", "#59331d")),
        ("openverse", ("O", "#8f7ce8", "#302a58")),
        ("musicbrainz", ("MB", "#d47597", "#522b3a")),
        ("listenbrainz", ("LB", "#e57360", "#572c25")),
        ("last.fm", ("L", "#e45252", "#551f1f")),
        ("cover art archive", ("CA", "#8fa2bf", "#303a4c")),
        ("lyrics", ("“", "#bd7cda", "#442a50")),
    )
    for token,spec in specific:
        if token in name_key:
            return spec

    generic={
        "local": ("♫", "#49a6f2", "#183c5e"),
        "stream": ("◉", "#4db8ae", "#173f3b"),
        "radio": ("◉", "#4db8ae", "#173f3b"),
        "provider": ("↗", "#6f9be2", "#263d61"),
        "recommendation": ("✦", "#b47ae0", "#452d59"),
        "artwork": ("▣", "#df8a54", "#58351f"),
        "lyrics": ("“", "#bd7cda", "#442a50"),
        "context": ("i", "#63b197", "#214638"),
        "metadata": ("#", "#8fa0bc", "#313b4e"),
        "identity": ("◎", "#7da3e0", "#2b3d60"),
        "plugin": ("◇", "#91a0b5", "#313842"),
        "built-in": ("⌂", "#91a0b5", "#303842"),
    }
    return generic.get(key, ("◇", "#91a0b5", "#313842"))


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
        self.setMinimumHeight(106)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

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


class FeaturePresenceBar(QFrame):
    """Small in-context summary showing what powers a feature and where to add more."""

    actionRequested = Signal()

    def __init__(
        self,
        title: str,
        *,
        baseline: str = "Built into Melodex",
        action_text: str = "Add more…",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("featurePresenceBar")
        self._title_text=str(title or "Feature")
        self._baseline=str(baseline or "Built into Melodex")

        row=QHBoxLayout(self)
        row.setContentsMargins(11,8,11,8)
        row.setSpacing(9)

        glyph=QLabel("✦")
        glyph.setObjectName("featurePresenceIcon")
        glyph.setAlignment(Qt.AlignCenter)
        glyph.setFixedSize(26,26)
        row.addWidget(glyph)

        self.label=QLabel()
        self.label.setObjectName("featurePresenceText")
        self.label.setWordWrap(True)
        row.addWidget(self.label,1)

        self.action=QPushButton(str(action_text or "Add more…"))
        self.action.setObjectName("featurePresenceAction")
        self.action.clicked.connect(self.actionRequested)
        row.addWidget(self.action)

        self.set_items([])

    def set_items(self, names: list[str] | tuple[str, ...]) -> None:
        cleaned=[]
        seen=set()
        for raw in names or []:
            name=" ".join(str(raw or "").split())
            key=name.casefold()
            if not name or key in seen:
                continue
            seen.add(key)
            cleaned.append(name)

        if cleaned:
            shown=" · ".join(cleaned[:3])
            if len(cleaned) > 3:
                shown+=f" · +{len(cleaned)-3} more"
            self.label.setText(
                f"<b>{self._title_text}</b>  <span style='color:#8fa7c3'>Active: {shown}</span>"
            )
            self.setProperty("active",True)
        else:
            self.label.setText(
                f"<b>{self._title_text}</b>  <span style='color:#7f8b9c'>{self._baseline}</span>"
            )
            self.setProperty("active",False)

        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class SourceCard(QFrame):
    """Human-readable source/plugin row with a distinctive category tile."""

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
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(12)

        badge = QLabel()
        badge.setObjectName("sourceBadge")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(48, 48)
        glyph,accent,background=source_icon_spec(name,icon_key)
        badge.setText(glyph)
        badge.setStyleSheet(
            "font-weight:800;font-size:15px;"
            f"color:{accent};background:{background};"
            f"border:1px solid {accent};border-radius:12px;"
        )
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
        outer.setContentsMargins(24, 28, 24, 28)
        outer.setSpacing(8)
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
    "source_icon_spec",
    "placeholder_cover",
    "set_help",
]
