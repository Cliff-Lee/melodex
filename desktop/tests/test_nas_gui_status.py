from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _browser():
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.library_browser import LibraryBrowser
    except ImportError as exc:
        import pytest

        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    browser = LibraryBrowser()
    browser.resize(900, 600)
    browser.show()
    app.processEvents()
    return app, browser


def test_library_browser_keeps_unavailable_nas_warning_visible():
    app, browser = _browser()

    browser.begin_scan("test")
    browser.finish_scan(
        "degraded",
        count=12700,
        storage_outcome={
            "roots_unavailable": 1,
            "roots_incomplete": 0,
        },
    )
    app.processEvents()

    assert browser.scan_progress_title.text() == "Library kept available"
    assert browser.scan_progress_summary.text() == "1 music location unavailable"
    detail = browser.scan_progress_detail.text()
    assert "last indexed library" in detail
    assert "No cached tracks were removed" in detail
    assert browser.scan_progress_panel.isVisible()

    browser.clear_scan_status()
    app.processEvents()
    # Degraded status deliberately remains visible because finish_scan marks
    # the scan inactive but MainWindow does not schedule auto-clear for it.
    assert browser.scan_progress_panel.isVisible()

    browser.deleteLater()
    app.processEvents()


def test_library_browser_explains_incomplete_network_scan():
    app, browser = _browser()

    browser.begin_scan("test")
    browser.finish_scan(
        "degraded",
        count=12700,
        storage_outcome={
            "roots_unavailable": 0,
            "roots_incomplete": 1,
        },
    )
    app.processEvents()

    assert "Could not finish reading 1 music location" == browser.scan_progress_summary.text()
    detail = browser.scan_progress_detail.text()
    assert "No partial scan was applied" in detail

    browser.deleteLater()
    app.processEvents()
