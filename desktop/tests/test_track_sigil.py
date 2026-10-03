from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_track_sigil_geometry_is_deterministic_and_identity_specific():
    from melodex.track_sigil import sigil_radii

    first = sigil_radii(123456789)
    again = sigil_radii(123456789)
    other = sigil_radii(987654321)

    assert first == again
    assert first != other
    assert len(first) == 10
    assert all(0.60 <= radius <= 1.0 for radius in first)


def test_track_sigil_is_a_compact_identity_surface_not_public_visualizer():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QApplication

        from melodex.living_canvas import LivingCanvasView
        from melodex.track_sigil import TrackSigilBadge
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    view = LivingCanvasView()
    view.set_track({"artist": "Example", "title": "Identity", "duration": 210})

    public_modes = [
        view.mode_combo.itemData(i)
        for i in range(view.mode_combo.count())
        if isinstance(view.mode_combo.itemData(i), str)
    ]
    assert "fingerprint" not in public_modes
    assert isinstance(view.track_sigil, TrackSigilBadge)
    assert view.track_sigil._profile is view._profile
    assert view._profile.fingerprint[:12].upper() in view.sigil_caption.text()

    image = QImage(view.track_sigil.size(), QImage.Format_ARGB32)
    image.fill(QColor("#000000"))
    view.track_sigil.render(image)
    assert image.pixelColor(image.width() // 2, image.height() // 2) != QColor("#000000")

    view.deleteLater()
    app.processEvents()


def test_visual_mode_headers_are_purpose_sections_not_selectable_modes():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication

        from melodex.living_canvas import LivingCanvasView
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    view = LivingCanvasView()

    headers = []
    for index in range(view.mode_combo.count()):
        if view.mode_combo.itemData(index) is None:
            headers.append(view.mode_combo.itemText(index))
            model = view.mode_combo.model()
            item = model.item(index) if hasattr(model, "item") else None
            if item is not None:
                assert not item.isEnabled()
                assert not item.isSelectable()

    assert headers[:2] == ["WATCH", "EXPLORE"]

    view.deleteLater()
    app.processEvents()
