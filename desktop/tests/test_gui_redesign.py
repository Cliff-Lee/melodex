from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _track(path: str, artist: str, album: str, title: str, number: int, year: int = 2000):
    return {
        "provider_id": "local",
        "track_id": path,
        "local_path": path,
        "artist": artist,
        "album": album,
        "title": title,
        "track_number": number,
        "year": year,
    }


def test_visual_library_defaults_to_album_cards_and_filters():
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.library_browser import LibraryBrowser
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    browser = LibraryBrowser()
    browser.resize(1000, 700)
    browser.show()
    browser.set_catalog(
        [
            _track("/a/01.mp3", "Artist A", "Album A", "One", 1, 2001),
            _track("/a/02.mp3", "Artist A", "Album A", "Two", 2, 2001),
            _track("/b/01.mp3", "Artist B", "Album B", "Three", 1, 2010),
        ]
    )
    app.processEvents()

    assert browser.current_view() == "albums"
    assert len(browser.albums) == 2
    assert len(browser.cards) == 2
    assert all(not card.cover.pixmap().isNull() for card in browser.cards.values())

    browser.search.setText("Album A")
    app.processEvents()
    assert len(browser._visible_albums) == 1
    assert browser._visible_albums[0]["title"] == "Album A"

    browser.set_view("artists")
    assert browser.stack.currentWidget() is browser.artist_list
    browser.set_view("tracks")
    assert browser.stack.currentWidget() is browser.track_list

    browser.set_catalog([])
    assert browser.stack.currentWidget() is browser.empty

    browser.deleteLater()
    app.processEvents()


def test_redesigned_main_window_builds_with_goal_navigation(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)

    window = main_window.MainWindow()
    window.show()
    app.processEvents()

    assert list(window.nav_buttons) == [
        "home",
        "library",
        "explore",
        "journeys",
        "playlists",
        "sources",
    ]
    assert "now_playing" not in window.nav_buttons
    assert "album_wall" not in window.nav_buttons
    assert hasattr(window, "library_browser")
    assert window.now_views.tabText(0) == "Now Playing"
    assert window.now_views.tabText(1) == "Visuals"

    window.open_page("explore")
    app.processEvents()
    assert window.stack.currentWidget() is window.pages["explore"]
    assert bool(window.nav_buttons["explore"].property("active"))

    window.power_toggle.setChecked(False)
    app.processEvents()
    assert not window.source_power_panel.isVisible()
    assert not window.player_power_actions.isVisible()

    window.close()
    app.processEvents()
