"""Repeated Qt close events must never reuse already-closed service state."""
from __future__ import annotations

import pytest


def test_main_window_second_close_event_is_safe_after_services_closed(
    tmp_path, monkeypatch,
):
    try:
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtGui import QCloseEvent
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)
    window = main_window.MainWindow()
    try:
        window.close()
        app.processEvents()
        assert window._closing

        # The first event closed UserState and provider databases. A second
        # direct call must not try to write the queue into the closed DB.
        repeated_event = QCloseEvent()
        window.closeEvent(repeated_event)
        assert repeated_event.isAccepted()
        assert window._closing
    finally:
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
