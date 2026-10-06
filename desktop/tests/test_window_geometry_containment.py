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

    assert after_map["window_min"][0] <= before["window_min"][0], (
        f"Music Map raised MainWindow minimum width: before={before}, after={after_map}"
    )
    assert after_map["window_min"][1] <= before["window_min"][1], (
        f"Music Map raised MainWindow minimum height: before={before}, after={after_map}"
    )
    assert after_map["stack_min"][0] <= before["stack_min"][0], (
        f"Music Map raised stack minimum width: before={before}, after={after_map}"
    )
    assert after_map["stack_min"][1] <= before["stack_min"][1], (
        f"Music Map raised stack minimum height: before={before}, after={after_map}"
    )
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



def test_p14m_dynamic_map_and_tools_do_not_own_outer_geometry(monkeypatch, tmp_path):
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
    window.resize(760, 520)
    window.show()
    app.processEvents()
    baseline = (window.width(), window.height())
    assert baseline == (760, 520), (
        "A hidden/inactive page already owns the top-level minimum before Music Map: "
        f"requested=(760, 520), actual={baseline}, snapshot={_geometry_snapshot(window)}"
    )

    window.open_page("music_map")
    QTest.qWait(window._page_refresh_delay_ms + 40)
    app.processEvents()
    built = (window.width(), window.height())

    nodes = [
        {
            "ref": f"track-{index}",
            "title": f"Track {index}",
            "artist": f"Artist {index % 5}",
            "x": ((index % 7) / 3.0) - 1.0,
            "y": ((index % 5) / 2.0) - 1.0,
            "energy": 0.5,
        }
        for index in range(35)
    ]
    ref_map = {
        node["ref"]: {
            "provider_id": "local",
            "track_id": node["ref"],
            "title": node["title"],
            "artist": node["artist"],
        }
        for node in nodes
    }
    window.journey_workspace.music_map.set_map(
        {"nodes": nodes, "edges": [], "analysed": len(nodes), "input_profiles": len(nodes)},
        ref_map,
    )
    app.processEvents()
    hydrated = (window.width(), window.height())

    window.journey_workspace._toggle_music_map_tools()
    window.journey_workspace._toggle_music_journey_options()
    app.processEvents()
    tools = (window.width(), window.height())

    assert built == baseline, f"Music Map build changed outer geometry: {baseline=} {built=}"
    assert hydrated == baseline, f"Map hydration changed outer geometry: {baseline=} {hydrated=}"
    assert tools == baseline, f"Map tool panels changed outer geometry: {baseline=} {tools=}"

    window.close()
    app.processEvents()



def test_p14m_feature_page_minimum_cannot_escape_viewport_stack():
    try:
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget
        from melodex.main_window import _ViewportStack
    except ImportError as exc:
        import pytest

        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    stock_stack = QStackedWidget()
    stock_page = QWidget()
    stock_page.setMinimumSize(1800, 1200)
    stock_stack.addWidget(stock_page)
    assert stock_stack.minimumSizeHint().width() >= 1800
    assert stock_stack.minimumSizeHint().height() >= 1200

    stack = _ViewportStack()
    oversized_page = QWidget()
    oversized_page.setMinimumSize(1800, 1200)
    stack.addWidget(oversized_page)

    assert stack.minimumSizeHint() == QSize(0, 0)

    stock_stack.deleteLater()
    stack.deleteLater()
    app.processEvents()



def test_p14m_restored_geometry_is_contained_in_available_work_area():
    try:
        from PySide6.QtCore import QRect
        from melodex.window_geometry import contained_window_geometry
    except ImportError as exc:
        import pytest

        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    work_area = QRect(0, 0, 1440, 860)

    too_large = contained_window_geometry(
        QRect(100, 50, 1900, 1100),
        [work_area],
    )
    assert too_large == QRect(0, 0, 1440, 860)

    off_screen = contained_window_geometry(
        QRect(2200, 900, 900, 620),
        [work_area],
    )
    assert off_screen == QRect(540, 240, 900, 620)

    valid = QRect(120, 90, 1100, 700)
    assert contained_window_geometry(valid, [work_area]) == valid


def test_p14m_restore_selects_best_current_monitor_work_area():
    try:
        from PySide6.QtCore import QRect
        from melodex.window_geometry import contained_window_geometry
    except ImportError as exc:
        import pytest

        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    left = QRect(0, 0, 1280, 720)
    right = QRect(1280, 40, 1920, 1040)
    saved = QRect(1500, 100, 1000, 760)

    assert contained_window_geometry(saved, [left, right]) == saved



def test_p14m_major_page_transitions_preserve_user_geometry(monkeypatch, tmp_path):
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
    window.resize(860, 560)
    window.show()
    app.processEvents()
    baseline = (window.width(), window.height())

    for page in ("library", "now_playing", "album_wall", "music_map"):
        window.navigation.ensure_lazy_page_built(page)
    app.processEvents()

    window.library_browser.set_view("albums")
    window.library_browser.set_view("artists")
    window.library_browser.set_view("tracks")
    window.library_browser.search.setText("geometry check")
    window.library_browser.search.clear()

    window.playback_feature.rich_now.tabs.setCurrentWidget(
        window.playback_feature.rich_now.lyrics_page
    )
    app.processEvents()

    for page in (
        "library",
        "music_map",
        "now_playing",
        "album_wall",
        "library",
        "journeys",
        "playlists",
        "sources",
        "explore",
        "home",
    ):
        window.open_page(page)
        QTest.qWait(window._page_refresh_delay_ms + 10)
        app.processEvents()
        assert (window.width(), window.height()) == baseline, (
            f"page {page!r} changed user geometry: "
            f"baseline={baseline}, actual={(window.width(), window.height())}, "
            f"window_min={(window.minimumSizeHint().width(), window.minimumSizeHint().height())}, "
            f"stack_min={(window.stack.minimumSizeHint().width(), window.stack.minimumSizeHint().height())}"
        )

    window.close()
    app.processEvents()


def test_p14m_maximize_navigation_restore_preserves_normal_geometry(monkeypatch, tmp_path):
    try:
        import pytest
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
    window.resize(880, 600)
    window.show()
    app.processEvents()
    baseline = (window.width(), window.height())

    window.showMaximized()
    app.processEvents()
    if not window.isMaximized():
        window.close()
        pytest.skip("Qt platform backend does not expose maximized state")

    window.open_page("music_map")
    QTest.qWait(window._page_refresh_delay_ms + 40)
    app.processEvents()
    window.showNormal()
    app.processEvents()

    assert (window.width(), window.height()) == baseline

    window.open_page("library")
    QTest.qWait(window._page_refresh_delay_ms + 20)
    app.processEvents()
    assert (window.width(), window.height()) == baseline

    window.close()
    app.processEvents()
