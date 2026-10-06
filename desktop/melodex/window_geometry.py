from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QRegion


def contained_window_geometry(
    geometry: QRect,
    available_geometries: list[QRect],
    *,
    edge_inset: int = 0,
    recover_legacy_full_height: bool = False,
) -> QRect:
    """Contain restored normal geometry inside the best current work area.

    edge_inset is used only when recovery is actually required. Valid,
    trusted user geometry is returned unchanged. recover_legacy_full_height
    provides a one-time migration path for old normal-window state that exactly
    saturates a work area's vertical extent.

    This is intentionally a restore-time helper, not a live resize policy.
    """
    current = QRect(geometry)
    screens = [QRect(rect) for rect in available_geometries if rect.isValid()]
    if not current.isValid() or not screens:
        return current

    def overlap_area(available: QRect) -> int:
        overlap = current.intersected(available)
        return max(0, overlap.width()) * max(0, overlap.height())

    available = max(screens, key=overlap_area)
    available_region = QRegion()
    for rect in screens:
        available_region = available_region.united(QRegion(rect))

    vertically_saturated_legacy = bool(
        recover_legacy_full_height
        and available_region.contains(current)
        and current.height() >= available.height() - 4
        and abs(current.top() - available.top()) <= 4
        and abs(current.bottom() - available.bottom()) <= 4
    )
    if available_region.contains(current) and not vertically_saturated_legacy:
        return current

    inset = max(0, int(edge_inset))
    inset_x = min(inset, max(0, (available.width() - 1) // 4))
    inset_y = min(inset, max(0, (available.height() - 1) // 4))
    target = available.adjusted(inset_x, inset_y, -inset_x, -inset_y)
    if not target.isValid():
        target = available

    width = min(current.width(), target.width())
    height = min(current.height(), target.height())

    max_x = target.x() + target.width() - width
    max_y = target.y() + target.height() - height
    x = min(max(current.x(), target.x()), max_x)
    y = min(max(current.y(), target.y()), max_y)
    return QRect(x, y, width, height)
