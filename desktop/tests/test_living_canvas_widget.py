from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def test_canvas_animation_stops_when_paused_hidden_or_minimized():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from melodex.living_canvas import _LivingScene

    app = QApplication.instance() or QApplication([])
    scene = _LivingScene()
    scene.resize(640, 320)
    scene.show()
    app.processEvents()
    assert not scene._timer.isActive()

    scene.set_playing(True)
    assert scene._timer.isActive()

    scene.set_window_minimized(True)
    assert not scene._timer.isActive()
    scene.set_window_minimized(False)
    assert scene._timer.isActive()

    scene.set_playing(False)
    assert not scene._timer.isActive()
    scene.set_playing(True)
    scene.hide()
    app.processEvents()
    assert not scene._timer.isActive()
    scene.deleteLater()
    app.processEvents()
