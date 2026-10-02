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
    metrics = browser.last_catalog_metrics
    assert metrics["track_count"] == 3
    assert metrics["album_count"] == 2
    assert metrics["artist_count"] == 2
    assert metrics["main_thread"] is True
    assert metrics["total_seconds"] >= metrics["album_model_seconds"]
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
        from PySide6.QtWidgets import QApplication, QLabel
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
    assert hasattr(window, "sources_overview")
    assert hasattr(window, "source_check_all")
    assert hasattr(window.rich_now, "import_lyrics_button")
    assert hasattr(window.rich_now, "paste_lyrics_button")
    assert hasattr(window.rich_now, "find_lyrics_plugin_button")
    assert hasattr(window.rich_now, "online_lyrics_button")
    assert window.rich_now.online_lyrics_button.text() == "Refresh lyrics"
    assert hasattr(window.rich_now, "auto_online_lyrics")
    assert window.rich_now.auto_online_lyrics.isChecked() is False
    assert hasattr(window, "source_summary_library")
    assert hasattr(window, "source_summary_included")
    assert hasattr(window, "source_summary_enhancements")
    assert set(window.source_feature_buttons) == {
        "search",
        "lyrics",
        "artwork",
        "recommendations",
        "context",
    }
    assert window.source_feature_buttons["lyrics"].text() == "Lyrics"
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


def test_artist_photo_lookup_runs_in_bounded_batches_with_progress():
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
    assert len(batches[0]) == 4
    assert browser.artist_image_lookup_remaining() == 15
    assert browser.images_button.isEnabled() is False
    assert browser.artwork_progress_panel.isVisible() is False or browser.artwork_progress.value() == 0

    first_outcomes = [
        {"key": row["key"], "status": "found" if i < 2 else "no_match"}
        for i, row in enumerate(batches[0])
    ]
    browser.finish_artist_image_lookup_batch(first_outcomes)

    assert len(batches) == 2
    assert len(batches[1]) == 4
    snapshot = browser.artwork_lookup_snapshot()
    assert snapshot["completed"] == 4
    assert snapshot["found"] == 2
    assert snapshot["skipped"] == 2
    assert snapshot["failed"] == 0
    assert snapshot["total"] == 15

    # Finish the remaining batches.
    while browser._artist_lookup_active:
        current = list(browser._artist_lookup_inflight_rows)
        outcomes = [
            {"key": row["key"], "status": "no_match"}
            for row in current
        ]
        browser.finish_artist_image_lookup_batch(outcomes)

    snapshot = browser.artwork_lookup_snapshot()
    assert snapshot["completed"] == 15
    assert snapshot["total"] == 15
    assert snapshot["active"] is False
    assert len(batches) == 4
    assert [len(batch) for batch in batches] == [4, 4, 4, 3]
    assert browser.images_button.isEnabled() is True
    assert browser.images_button.text() == "Get artist photos"
    browser.deleteLater()
    app.processEvents()

def test_album_artwork_lookup_runs_all_missing_albums_in_bounded_batches():
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
    assert len(batches[0]) == 4
    assert browser.album_artwork_lookup_remaining() == 17

    while browser._album_lookup_active:
        current = list(browser._album_lookup_inflight_rows)
        outcomes = [
            {"key": row["key"], "status": "found"}
            for row in current
        ]
        browser.finish_album_artwork_lookup_batch(outcomes)

    snapshot = browser.artwork_lookup_snapshot()
    assert snapshot["completed"] == 17
    assert snapshot["found"] == 17
    assert snapshot["total"] == 17
    assert [len(batch) for batch in batches] == [4, 4, 4, 4, 1]
    assert browser.images_button.isEnabled() is True
    assert browser.images_button.text() == "Find missing artwork"
    browser.deleteLater()
    app.processEvents()

def test_artwork_progress_labels_are_compact():
    try:
        from melodex.library_browser import LibraryBrowser
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    assert LibraryBrowser._progress_item_label("Air") == "Air"
    label = LibraryBrowser._progress_item_label(
        "A Winged Victory For The Sullen",
        22,
    )
    assert len(label) <= 22
    assert label.endswith("…")



def test_source_card_uses_icon_and_origin_badge():
    try:
        from PySide6.QtWidgets import QApplication, QLabel
        from melodex.ux_components import SourceCard
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    card = SourceCard(
        "Lyrics helper",
        "Adds lyrics to Now Playing.",
        "Ready",
        kind="Lyrics",
        icon_key="lyrics",
        origin="Registry",
    )
    badge = card.findChild(QLabel, "sourceBadge")
    assert badge is not None
    assert badge.text() == "“"
    assert card.findChild(QLabel, "originPill") is not None
    card.deleteLater()
    app.processEvents()



def test_plugin_centre_is_outcome_and_management_focused(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QApplication, QLabel
        import melodex.main_window as main_window
        from melodex.plugin_directory import PluginDirectoryDialog, PluginDirectoryCard
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)
    monkeypatch.setattr(PluginDirectoryDialog, "load_registry", lambda self, force=False: None)

    window = main_window.MainWindow()
    dialog = PluginDirectoryDialog(window.providers, parent=window)

    assert dialog.view.itemData(0) == "all"
    assert dialog.view.findData("installed") >= 0
    assert dialog.view.findData("available") >= 0
    assert dialog.view.findData("setup") >= 0
    assert dialog.view.findData("updates") >= 0
    assert set(dialog.view_buttons) == {
        "all",
        "installed",
        "available",
        "setup",
        "updates",
    }
    assert dialog.toggle_button.text() == "Disable"
    assert dialog.remove_button.text() == "Remove"
    assert dialog.toggle_button.isEnabled() is False
    assert dialog.remove_button.isEnabled() is False

    lyrics_entry = {
        "id": "org.example.lyrics",
        "name": "Lyrics helper",
        "kind": "enrichment",
        "status": "community",
        "description": "Adds lyrics.",
        "capabilities": ["lyrics"],
        "distribution": {},
        "source": {},
        "review": {},
        "permissions": [],
    }
    assert PluginDirectoryDialog._where_used(lyrics_entry) == "Now Playing → Lyrics"
    assert PluginDirectoryDialog._where_used(
        {**lyrics_entry, "kind": "provider", "capabilities": ["search", "playback"]}
    ) == "Explore → Search everything"

    card = PluginDirectoryCard(
        lyrics_entry,
        "Setup needed",
        installed=True,
    )
    state = card.findChild(QLabel, "pluginDirectoryState")
    assert state is not None
    assert state.text() == "Setup needed"
    assert state.property("state") == "attention"
    assert card.findChild(QLabel, "pluginCapabilityChip") is not None
    usage = card.findChild(QLabel, "pluginDirectoryUsage")
    assert usage is not None
    assert "Now Playing" in usage.text()

    dialog.plugins = [lyrics_entry]
    dialog._apply_filter()
    assert dialog.rows.count() == 1
    assert dialog.view_buttons["all"].text() == "All  1"
    assert dialog.view_buttons["available"].text() == "Available  1"
    assert dialog.list_stack.currentWidget() is dialog.rows

    dialog._select_view("installed")
    assert dialog.rows.count() == 0
    assert dialog.list_stack.currentWidget() is dialog.empty_state
    assert dialog.empty_title.text() == "No optional plugins installed"
    assert dialog.view_buttons["installed"].isChecked()

    dialog._clear_filters()
    assert dialog.view.currentData() == "all"
    assert dialog.rows.count() == 1

    card.deleteLater()
    dialog.close()
    window.close()
    app.processEvents()



def test_plugins_surface_where_their_features_are_used(monkeypatch, tmp_path):
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

    extensions = [
        {
            "id": "org.example.art",
            "name": "Cover Helper",
            "enabled": True,
            "capabilities": ["artwork"],
            "configuration_status": {"declared": False, "ready": True},
        },
        {
            "id": "org.example.lyrics",
            "name": "Lyric Helper",
            "enabled": True,
            "capabilities": ["lyrics"],
            "configuration_status": {"declared": False, "ready": True},
        },
        {
            "id": "org.example.context",
            "name": "Liner Notes",
            "enabled": True,
            "capabilities": ["context"],
            "configuration_status": {"declared": False, "ready": True},
        },
        {
            "id": "org.example.recommend",
            "name": "Taste Helper",
            "enabled": True,
            "capabilities": ["library_suggestions"],
            "configuration_status": {"declared": False, "ready": True},
        },
        {
            "id": "org.example.disabled",
            "name": "Disabled Helper",
            "enabled": False,
            "capabilities": ["artwork", "lyrics"],
            "configuration_status": {"declared": False, "ready": True},
        },
        {
            "id": "org.example.setup",
            "name": "Needs Setup",
            "enabled": True,
            "capabilities": ["context"],
            "configuration_status": {"declared": True, "ready": False},
        },
    ]
    monkeypatch.setattr(window.providers, "extensions", lambda: list(extensions))

    window._refresh_plugin_presence()
    app.processEvents()

    assert "Cover Helper" in window.artwork_plugin_presence.label.text()
    assert "Disabled Helper" not in window.artwork_plugin_presence.label.text()
    assert bool(window.artwork_plugin_presence.property("active"))

    assert "Taste Helper" in window.recommendation_plugin_presence.label.text()
    assert not hasattr(window.rich_now, "lyrics_plugin_presence")
    assert "Liner Notes" in window.rich_now.context_plugin_presence.label.text()
    assert "Needs Setup" not in window.rich_now.context_plugin_presence.label.text()

    opened = []
    monkeypatch.setattr(window, "_plugin_directory", lambda capability="": opened.append(capability))

    window.search_plugin_presence.action.click()
    window.artwork_plugin_presence.action.click()
    window.recommendation_plugin_presence.action.click()
    window.rich_now.manage_lyrics_sources_action.trigger()
    window.rich_now.context_plugin_presence.action.click()

    assert opened == [
        "search",
        "artwork",
        "library_suggestions",
        "lyrics",
        "context",
    ]

    window.close()
    app.processEvents()


def test_feature_presence_bar_distinguishes_core_only_from_active_plugins():
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.ux_components import FeaturePresenceBar
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    bar = FeaturePresenceBar(
        "Artwork helpers",
        baseline="Built-in matching is active",
        action_text="Add artwork helper…",
    )

    assert "Built-in matching is active" in bar.label.text()
    assert not bool(bar.property("active"))

    bar.set_items(["Cover Helper", "Cover Helper", "Second Source"])
    assert "Cover Helper" in bar.label.text()
    assert "Second Source" in bar.label.text()
    assert bool(bar.property("active"))

    bar.deleteLater()
    app.processEvents()



def test_lyrics_lookup_outcomes_are_distinct_in_now_playing(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
        from melodex.metadata import track_key
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)

    window = main_window.MainWindow()
    widget = window.rich_now
    widget.track = {
        "artist": "Example Artist",
        "title": "Example Song",
        "provider_id": "local",
        "track_id": "example-song",
    }
    key = track_key(widget.track)

    widget._stage_loaded(
        key,
        "community lyrics",
        {
            "lyrics": {
                "text": "",
                "synced": [],
                "source": "LRCLIB community lyrics",
                "instrumental": False,
                "status": "not_found",
                "error": "",
            }
        },
    )
    assert "No confident lyric match" in widget.lyrics.toPlainText()
    assert widget.online_lyrics_button.text() == "Try again"
    assert "no confident match" in widget.lyrics_source.text().casefold()

    widget._stage_loaded(
        key,
        "community lyrics",
        {
            "lyrics": {
                "text": "",
                "synced": [],
                "source": "LRCLIB",
                "instrumental": False,
                "status": "error",
                "error": "temporary service error",
            }
        },
    )
    assert "could not connect" in widget.lyrics.toPlainText().casefold()
    assert "temporary service error" in widget.lyrics_source.text()

    widget._stage_loaded(
        key,
        "community lyrics",
        {
            "lyrics": {
                "text": "",
                "synced": [],
                "source": "LRCLIB community lyrics",
                "instrumental": True,
                "status": "instrumental",
                "error": "",
            }
        },
    )
    assert "Instrumental track" in widget.lyrics.toPlainText()
    assert widget.online_lyrics_button.text() == "Refresh lyrics"

    window.close()
    app.processEvents()



def test_synced_lyrics_seek_source_switch_and_editability(monkeypatch, tmp_path):
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)

    window = main_window.MainWindow()
    widget = window.rich_now
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"audio")
    widget.track = {
        "artist": "Example Artist",
        "title": "Example Song",
        "provider_id": "local",
        "track_id": str(audio),
        "local_path": str(audio),
    }

    local = {
        "text": "First line\nSecond line",
        "synced": [
            {"time_ms": 1000, "text": "First line"},
            {"time_ms": 3500, "text": "Second line"},
        ],
        "source": "Example Song.lrc",
        "path": str(tmp_path / "Example Song.lrc"),
    }
    online = {
        "text": "Online first\nOnline second",
        "synced": [],
        "source": "LRCLIB community lyrics",
        "status": "found",
        "provenance": {"source_extension_id": "core.lrclib-on-demand"},
    }

    widget._local_lyrics = dict(local)
    widget._online_lyrics = dict(online)
    widget._active_lyrics_source = "online"
    widget._apply_lyrics(online)

    assert widget.lyrics_source_picker.isVisible() is False or widget.lyrics_source_picker.count() == 2
    assert widget.lyrics_source_picker.count() == 2
    assert widget.edit_lyrics_button.isEnabled() is False
    assert widget.translate_lyrics_button.isEnabled() is True

    local_index = widget.lyrics_source_picker.findData("local")
    widget.lyrics_source_picker.setCurrentIndex(local_index)
    assert widget._active_lyrics_source == "local"
    assert widget._current_lyrics["source"] == "Example Song.lrc"
    assert widget.edit_lyrics_button.isEnabled() is True
    assert widget.fullscreen_lyrics_button.isEnabled() is True

    seeks = []
    widget.lyricsSeekRequested.connect(seeks.append)
    widget._lyrics_anchor_clicked(QUrl("seek:3500"))
    assert seeks == [3500]

    widget.set_position(3600)
    assert widget._lyric_index == 1
    assert "Second line" in widget.lyrics.toPlainText()

    window.close()
    app.processEvents()


def test_fullscreen_lyrics_tracks_synced_position(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QApplication, QDialog
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)
    monkeypatch.setattr(QDialog, "showFullScreen", lambda self: self.show())

    window = main_window.MainWindow()
    widget = window.rich_now
    widget.track = {
        "artist": "Example Artist",
        "title": "Example Song",
        "provider_id": "local",
        "track_id": "example-song",
        "local_path": str(tmp_path / "song.mp3"),
    }
    lyrics = {
        "text": "One\nTwo",
        "synced": [
            {"time_ms": 1000, "text": "One"},
            {"time_ms": 4000, "text": "Two"},
        ],
        "source": "Example Song.lrc",
        "path": str(tmp_path / "Example Song.lrc"),
    }
    widget._local_lyrics = dict(lyrics)
    widget._active_lyrics_source = "local"
    widget._apply_lyrics(lyrics)

    widget._show_fullscreen_lyrics()
    app.processEvents()
    assert widget._lyrics_fullscreen_dialog is not None
    assert widget._lyrics_fullscreen_browser is not None
    assert "One" in widget._lyrics_fullscreen_browser.toPlainText()

    widget.set_position(4100)
    app.processEvents()
    assert widget._lyric_index == 1
    assert "Two" in widget._lyrics_fullscreen_browser.toPlainText()
    assert "font-size:38px" in widget._synced_lyrics_html(1, full_screen=True)

    dialog = widget._lyrics_fullscreen_dialog
    if dialog is not None:
        dialog.close()
    window.close()
    app.processEvents()


def test_translate_lyrics_is_explicit_and_uses_configured_llm(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog
        import melodex.main_window as main_window
        from melodex.llm_bridge import LLMSettings
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)

    window = main_window.MainWindow()
    settings = LLMSettings(
        provider="ollama",
        endpoint="http://localhost:11434/api/chat",
        model="qwen-test",
    )
    monkeypatch.setattr(window, "_llm_settings", lambda: settings)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.Yes,
    )
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Chinese", True),
    )

    prompts = []
    monkeypatch.setattr(
        window.llm,
        "complete",
        lambda settings, prompt, context, history: prompts.append(prompt) or "翻译结果",
    )
    monkeypatch.setattr(
        window,
        "_run_async",
        lambda work, done, *args, **kwargs: done(work()),
    )
    shown = []
    monkeypatch.setattr(
        window,
        "_show_lyrics_translation",
        lambda language, text: shown.append((language, text)),
    )

    window._translate_lyrics({
        "text": "First line\nSecond line",
        "artist": "Example Artist",
        "title": "Example Song",
    })

    assert len(prompts) == 1
    assert "Chinese" in prompts[0]
    assert "First line\nSecond line" in prompts[0]
    assert shown == [("Chinese", "翻译结果")]
    assert window.state.get_text("lyrics_translation_language", "") == "Chinese"

    window.close()
    app.processEvents()


def test_online_lyrics_translation_signal_contains_only_current_lyrics(monkeypatch, tmp_path):
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
    widget = window.rich_now
    widget.track = {
        "artist": "Artist",
        "title": "Song",
        "provider_id": "remote",
        "track_id": "song",
    }
    lyrics = {
        "text": "Line one\nLine two",
        "synced": [],
        "source": "LRCLIB community lyrics",
        "status": "found",
        "provenance": {"source_extension_id": "core.lrclib-on-demand"},
    }
    widget._online_lyrics = dict(lyrics)
    widget._active_lyrics_source = "online"
    widget._apply_lyrics(lyrics)

    payloads = []
    widget.lyricsTranslationRequested.connect(payloads.append)
    widget.translate_lyrics_button.click()
    app.processEvents()

    assert len(payloads) == 1
    assert payloads[0]["text"] == "Line one\nLine two"
    assert payloads[0]["artist"] == "Artist"
    assert payloads[0]["title"] == "Song"
    assert widget.edit_lyrics_button.isEnabled() is False

    window.close()
    app.processEvents()



def test_online_lyrics_miss_does_not_replace_existing_local_lyrics(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
        from melodex.metadata import track_key
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)

    window = main_window.MainWindow()
    widget = window.rich_now
    widget.track = {
        "artist": "Example Artist",
        "title": "Example Song",
        "provider_id": "local",
        "track_id": "example-song",
        "local_path": str(tmp_path / "song.mp3"),
    }
    local = {
        "text": "My local lyric",
        "synced": [],
        "source": "Example Song.txt",
        "path": str(tmp_path / "Example Song.txt"),
    }
    widget._local_lyrics = dict(local)
    widget._active_lyrics_source = "local"
    widget._apply_lyrics(local)

    widget._stage_loaded(
        track_key(widget.track),
        "community lyrics",
        {
            "lyrics": {
                "text": "",
                "synced": [],
                "source": "LRCLIB community lyrics",
                "instrumental": False,
                "status": "not_found",
                "error": "",
            }
        },
    )

    assert widget._active_lyrics_source == "local"
    assert widget._current_lyrics["source"] == "Example Song.txt"
    assert "My local lyric" in widget.lyrics.toPlainText()
    assert widget.online_lyrics_button.text() == "Try again"

    window.close()
    app.processEvents()



def test_artwork_batch_can_pause_resume_cancel_and_retry_failed():
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
            f"/albums/control-{index:02d}.mp3",
            f"Artist {index:02d}",
            f"Album {index:02d}",
            f"Track {index:02d}",
            1,
            2000 + index,
        )
        for index in range(10)
    ]
    browser.set_catalog(tracks)
    browser.set_view("albums")

    batches = []
    browser.onlineArtworkRequested.connect(
        lambda rows: batches.append([dict(row) for row in rows])
    )
    browser._request_online_artwork()
    assert len(batches) == 1
    assert len(browser._album_lookup_inflight_rows) == 4

    browser._toggle_artwork_lookup_pause()
    assert browser._album_lookup_paused is True
    assert browser.artwork_pause_button.text() == "Resume"

    first = list(browser._album_lookup_inflight_rows)
    browser.finish_album_artwork_lookup_batch([
        {"key": first[0]["key"], "status": "found"},
        {"key": first[1]["key"], "status": "error", "error": "temporary"},
        {"key": first[2]["key"], "status": "no_match"},
        {"key": first[3]["key"], "status": "found"},
    ])
    assert len(batches) == 1
    snapshot = browser.artwork_lookup_snapshot()
    assert snapshot["paused"] is True
    assert snapshot["completed"] == 4
    assert snapshot["found"] == 2
    assert snapshot["skipped"] == 1
    assert snapshot["failed"] == 1

    browser._toggle_artwork_lookup_pause()
    assert browser._album_lookup_paused is False
    assert len(batches) == 2

    # Cancel while the resumed batch is in flight. It should finish that
    # batch but not start another one.
    browser._cancel_artwork_lookup()
    assert browser._album_lookup_cancel_requested is True
    second = list(browser._album_lookup_inflight_rows)
    browser.finish_album_artwork_lookup_batch([
        {"key": row["key"], "status": "found"}
        for row in second
    ])
    assert browser._album_lookup_active is False
    assert len(batches) == 2
    assert browser._album_lookup_failures

    # Retry only the failed item from the first batch.
    browser._album_lookup_cancel_requested = False
    browser._retry_failed_artwork()
    assert browser._album_lookup_active is True
    assert len(browser._album_lookup_inflight_rows) == 1
    retry = list(browser._album_lookup_inflight_rows)
    browser.finish_album_artwork_lookup_batch([
        {"key": retry[0]["key"], "status": "found"}
    ])
    retry_snapshot = browser.artwork_lookup_snapshot()
    assert retry_snapshot["total"] == 1
    assert retry_snapshot["completed"] == 1
    assert retry_snapshot["found"] == 1
    assert retry_snapshot["failed"] == 0

    browser.deleteLater()
    app.processEvents()


def test_artwork_progress_panel_reports_found_no_match_and_failed_counts():
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.library_browser import LibraryBrowser
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    browser = LibraryBrowser()
    browser._album_lookup_stats = {
        "total": 832,
        "completed": 147,
        "found": 101,
        "skipped": 40,
        "failed": 6,
    }
    browser._album_lookup_active = True
    browser._refresh_artwork_progress(kind="albums")

    assert browser.artwork_progress.maximum() == 832
    assert browser.artwork_progress.value() == 147
    assert browser.artwork_progress.format() == "147 / 832"
    assert "Found 101" in browser.artwork_progress_summary.text()
    assert "No match 40" in browser.artwork_progress_summary.text()
    assert "Failed 6" in browser.artwork_progress_summary.text()
    assert "background" in browser.artwork_progress_detail.text().casefold()

    browser.deleteLater()
    app.processEvents()



def test_sources_first_run_orientation_is_dismissible_and_persistent(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QApplication, QLabel
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)

    first = main_window.MainWindow()
    first.show()
    first.open_page("sources")
    app.processEvents()

    assert first.source_welcome.isVisible()
    title = first.source_welcome.findChild(QLabel, "sourceFirstRunTitle")
    assert title is not None
    assert "already ready to listen" in title.text().casefold()

    first._dismiss_sources_intro()
    app.processEvents()
    assert first.source_welcome.isHidden()
    assert first.state.get_bool("sources_intro_seen", False) is True
    first.close()
    app.processEvents()

    second = main_window.MainWindow()
    second.show()
    second.open_page("sources")
    app.processEvents()
    assert second.source_welcome.isHidden()
    second.close()
    app.processEvents()



def test_native_lyrics_toolbar_hides_plugin_management_chrome(monkeypatch, tmp_path):
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
    widget = window.rich_now

    assert not hasattr(widget, "lyrics_plugin_presence")
    assert widget.online_lyrics_button.text() == "Refresh lyrics"
    assert widget.fullscreen_lyrics_button.text() == "Full screen"
    assert widget.translate_lyrics_button.text() == "Translate"
    assert widget.more_lyrics_button.text() == "More"
    assert widget.find_lyrics_plugin_button.isHidden()
    assert widget.import_lyrics_button.isHidden()
    assert widget.paste_lyrics_button.isHidden()
    assert widget.auto_online_lyrics.isHidden()

    menu_labels = [
        action.text()
        for action in widget.lyrics_more_menu.actions()
        if action.text()
    ]
    assert menu_labels == [
        "Edit saved lyrics…",
        "Add lyrics file…",
        "Paste lyrics…",
        "Auto-find online",
        "Manage lyric sources…",
    ]

    window.close()
    app.processEvents()


def test_refresh_lyrics_checks_native_and_installed_sources_before_online(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
        from melodex.metadata import track_key
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)

    window = main_window.MainWindow()
    widget = window.rich_now
    widget.track = {
        "artist": "Example Artist",
        "title": "Example Song",
        "provider_id": "local",
        "track_id": "example-song",
    }

    payload = {
        "track_key": track_key(widget.track),
        "track": dict(widget.track),
        "identity": {
            "artist": "Example Artist",
            "title": "Example Song",
        },
        "lyrics": {
            "text": "Lyrics supplied by an installed source",
            "synced": [],
            "source": "Public Domain Lyrics Example",
            "provenance": {
                "source_extension_id": "org.example.lyrics",
                "source_extension_name": "Public Domain Lyrics Example",
            },
        },
        "errors": [],
    }
    monkeypatch.setattr(widget.metadata, "enrich_identity", lambda track: payload)

    online_calls = []
    monkeypatch.setattr(
        widget,
        "_find_lyrics_online",
        lambda force=True: online_calls.append(force),
    )

    def run_immediately(key, name, fn):
        widget._pending.add(name)
        widget._stage_loaded(key, name, fn())

    monkeypatch.setattr(widget, "_run_stage", run_immediately)
    widget._refresh_lyrics_native()
    app.processEvents()

    assert online_calls == []
    assert widget._current_lyrics["source"] == "Public Domain Lyrics Example"
    assert "Lyrics supplied by an installed source" in widget.lyrics.toPlainText()
    assert widget.lyrics_source_picker.count() == 1
    assert widget.lyrics_source_picker.currentText() == "Public Domain Lyrics Example"
    assert widget.online_lyrics_button.text() == "Refresh lyrics"

    window.close()
    app.processEvents()


def test_plain_lyrics_html_uses_explicit_dark_theme_contrast():
    try:
        from melodex.rich_now_playing import RichNowPlayingWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Desktop runtime is unavailable: {exc}")

    rendered = RichNowPlayingWidget._plain_lyrics_html("Line one\nLine two")
    assert "color:#e5edf6" in rendered
    assert "font-size:21px" in rendered
    assert "Line one<br>Line two" in rendered
