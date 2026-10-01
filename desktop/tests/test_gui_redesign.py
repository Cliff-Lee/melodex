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
    assert browser.stack.currentWidget() is browser.artist_page
    assert len(browser.artist_rows) == 2
    assert len(browser.artist_cards) == 2
    assert browser.images_button.text() == "Get artist photos"
    assert all(not card.has_artist_photo for card in browser.artist_cards.values())
    assert all(hasattr(card, "photo_button") for card in browser.artist_cards.values())

    browser.set_view("tracks")
    assert browser.stack.currentWidget() is browser.track_list
    assert len(browser.track_rows) == 3

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
    assert window.playlists_stack.currentWidget() is window.playlists_empty
    assert window.journey_recipes_stack.currentWidget() is window.journey_recipes_empty

    window._update_play_button(True)
    assert window.play_button.text() == "❚❚"
    window._update_play_button(False)
    assert window.play_button.text() == "▶"

    window.open_page("sources")
    app.processEvents()
    assert window.source_primary_button.text() == "Use selected"
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


def test_artist_photo_lookup_walks_the_whole_missing_artist_list():
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.library_browser import LibraryBrowser
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    browser = LibraryBrowser()
    tracks = [
        _track(
            f"/artists/{index:02d}.mp3",
            f"Artist {index:02d}",
            f"Album {index:02d}",
            f"Track {index:02d}",
            1,
            2000 + index,
        )
        for index in range(15)
    ]
    browser.set_catalog(tracks)
    browser.set_view("artists")

    batches = []
    browser.artistImageRequested.connect(
        lambda rows: batches.append([dict(row) for row in rows])
    )

    browser._request_online_artwork()
    assert len(batches) == 1
    assert len(batches[0]) == 1
    assert browser.artist_image_lookup_remaining() == 15
    assert browser.images_button.isEnabled() is False
    assert "Artist 00" in browser.images_button.text()
    assert browser.images_button.text().endswith("15 left")

    for expected_remaining in range(14, 0, -1):
        assert browser.continue_artist_image_lookup() is True
        assert len(batches[-1]) == 1
        assert browser.artist_image_lookup_remaining() == expected_remaining

    assert browser.continue_artist_image_lookup() is False
    assert len(batches) == 15
    assert browser.images_button.isEnabled() is True
    assert browser.images_button.text() == "Get artist photos"
    browser.deleteLater()
    app.processEvents()


def test_album_artwork_lookup_walks_all_missing_albums_not_just_twelve():
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.library_browser import LibraryBrowser
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    browser = LibraryBrowser()
    tracks = [
        _track(
            f"/albums/{index:02d}.mp3",
            f"Artist {index:02d}",
            f"Album {index:02d}",
            f"Track {index:02d}",
            1,
            1990 + index,
        )
        for index in range(17)
    ]
    browser.set_catalog(tracks)
    browser.set_view("albums")

    batches = []
    browser.onlineArtworkRequested.connect(
        lambda rows: batches.append([dict(row) for row in rows])
    )

    browser._request_online_artwork()
    assert len(batches) == 1
    assert len(batches[0]) == 1
    assert browser.album_artwork_lookup_remaining() == 17
    assert browser.images_button.isEnabled() is False
    assert "Album 00" in browser.images_button.text()
    assert browser.images_button.text().endswith("17 left")

    for expected_remaining in range(16, 0, -1):
        assert browser.continue_album_artwork_lookup() is True
        assert len(batches[-1]) == 1
        assert browser.album_artwork_lookup_remaining() == expected_remaining

    assert browser.continue_album_artwork_lookup() is False
    assert len(batches) == 17
    assert browser.images_button.isEnabled() is True
    assert browser.images_button.text() == "Find missing artwork"
    browser.deleteLater()
    app.processEvents()
