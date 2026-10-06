from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QRegion


def contained_window_geometry(
    geometry: QRect,
    available_geometries: list[QRect],
) -> QRect:
    """Contain restored normal geometry inside the best current work area.

    This is intentionally a restore-time helper, not a live resize policy.
    """
    current = QRect(geometry)
    screens = [QRect(rect) for rect in available_geometries if rect.isValid()]
    if not current.isValid() or not screens:
        return current

    available_region = QRegion()
    for rect in screens:
        available_region = available_region.united(QRegion(rect))
    if available_region.contains(current):
        return current

    def overlap_area(available: QRect) -> int:
        overlap = current.intersected(available)
        return max(0, overlap.width()) * max(0, overlap.height())

    available = max(screens, key=overlap_area)
    width = min(current.width(), available.width())
    height = min(current.height(), available.height())

    max_x = available.x() + available.width() - width
    max_y = available.y() + available.height() - height
    x = min(max(current.x(), available.x()), max_x)
    y = min(max(current.y(), available.y()), max_y)
    return QRect(x, y, width, height)
