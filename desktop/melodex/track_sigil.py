"""Reusable deterministic Track Sigil identity primitives.

Track Sigil is intentionally not a standalone visualizer. The same fixed
geometry can be reused in compact track identity surfaces such as the Visuals
header, Constellation centre, share cards and metadata views.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .track_sigil_model import sigil_radii
from .visualization_profile import VisualProfile


def sigil_path(rect: QRectF, seed: int, scale: float = 1.0) -> QPainterPath:
    """Build one stable closed sigil path inside the supplied rectangle."""

    radii = sigil_radii(seed)
    center = rect.center()
    radius = min(rect.width(), rect.height()) * 0.5 * max(0.1, float(scale))
    phase = (int(seed) % 360) / 360.0 * math.tau
    path = QPainterPath()
    for index, value in enumerate(radii):
        angle = phase + math.tau * index / len(radii)
        point = QPointF(
            center.x() + math.cos(angle) * radius * value,
            center.y() + math.sin(angle) * radius * value,
        )
        if index == 0:
            path.moveTo(point)
        else:
            path.lineTo(point)
    path.closeSubpath()
    return path


def paint_track_sigil(
    painter: QPainter,
    rect: QRectF,
    seed: int,
    accent: QColor,
    *,
    glow: float = 0.35,
    compact: bool = False,
) -> None:
    """Paint stable geometry with optional playback-like glow around it.

    Geometry never changes with playback. Only surrounding luminance may vary.
    """

    painter.save()
    accent = QColor(accent)
    glow = max(0.0, min(1.0, float(glow)))
    center = rect.center()
    radius = min(rect.width(), rect.height()) * (0.47 if compact else 0.44)

    if glow > 0:
        halo = QColor(accent)
        halo.setAlpha(int(16 + 42 * glow))
        painter.setPen(Qt.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(center, radius * (1.05 + 0.12 * glow), radius * (1.05 + 0.12 * glow))

    for layer, scale in enumerate((0.58, 0.78, 0.96)):
        color = QColor(accent)
        color.setAlpha(72 + layer * 48)
        width = 0.8 + layer * 0.45
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(sigil_path(rect, seed ^ (layer * 0x45D9F3B), scale))

    core = QColor("#f6fbff")
    core.setAlpha(210)
    painter.setPen(Qt.NoPen)
    painter.setBrush(core)
    painter.drawEllipse(center, 1.8 if compact else 2.2, 1.8 if compact else 2.2)
    painter.restore()


class TrackSigilBadge(QWidget):
    """Small reusable identity badge for the current recording."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile: VisualProfile | None = None
        self._accent = QColor("#7eb4ff")
        self.setFixedSize(46, 46)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setAccessibleName("Track Sigil")
        self.setToolTip("Track Sigil · stable visual identity for this recording")

    def set_profile(self, profile: VisualProfile | None) -> None:
        self._profile = profile
        if profile is None:
            self.setAccessibleDescription("No current recording identity.")
            self.setToolTip("Track Sigil · stable visual identity for this recording")
        else:
            short = profile.fingerprint[:12].upper()
            self.setAccessibleDescription(
                f"Stable Track Sigil {short}, repeatable for this recording."
            )
            self.setToolTip(
                f"Track Sigil · {short}\nSame recording → same geometry."
            )
        self.update()

    def set_accent_color(self, color: QColor) -> None:
        self._accent = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self._profile is None:
            painter.setPen(QPen(QColor(125, 143, 164, 70), 1.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QRectF(self.rect()).adjusted(11, 11, -11, -11))
            painter.end()
            return
        paint_track_sigil(
            painter,
            QRectF(self.rect()).adjusted(3, 3, -3, -3),
            self._profile.seed,
            self._accent,
            glow=0.28,
            compact=True,
        )
        painter.end()
