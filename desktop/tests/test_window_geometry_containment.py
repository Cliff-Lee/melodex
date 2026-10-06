from __future__ import annotations


def _geometry_snapshot(window) -> dict[str, tuple[int, int]]:
    page = window.pages["music_map"]
    return {
        "window": (window.width(), window.height()),
        "window_min": (
            window.minimumSizeHint().width(),
            window.minimumSizeHint().height(),
        ),
        "stack_min": (
            window.stack.minimumSizeHint().width(),
            window.stack.minimumSizeHint().height(),
        ),
        "page_min": (
            page.minimumSizeHint().width(),
            page.minimumSizeHint().height(),
        ),
    }


def test_p14m_music_map_navigation_does_not_expand_main_window(monkeypatch, tmp_path):
    try:
        from PySide6.QtCore import QSettings
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest

        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    QSettings("Melodex", "Melodex").clear()
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)

    window = main_window.MainWindow()
    window.resize(900, 620)
    window.show()
    app.processEvents()

    before = _geometry_snapshot(window)

    window.open_page("music_map")
    QTest.qWait(window._page_refresh_delay_ms + 40)
    app.processEvents()
    after_map = _geometry_snapshot(window)

    window.open_page("library")
    QTest.qWait(window._page_refresh_delay_ms + 40)
    app.processEvents()
    after_library = _geometry_snapshot(window)

    window.open_page("music_map")
    QTest.qWait(window._page_refresh_delay_ms + 40)
    app.processEvents()
    after_return = _geometry_snapshot(window)

    assert after_map["window"][0] <= before["window"][0], (
        f"Music Map widened MainWindow: before={before}, after={after_map}"
    )
    assert after_map["window"][1] <= before["window"][1], (
        f"Music Map increased MainWindow height: before={before}, after={after_map}"
    )
    assert after_library["window"] == before["window"], (
        f"Oversized geometry persisted after leaving Music Map: "
        f"before={before}, library={after_library}"
    )
    assert after_return["window"] == before["window"], (
        f"Returning to Music Map changed geometry: before={before}, return={after_return}"
    )

    window.close()
    app.processEvents()
