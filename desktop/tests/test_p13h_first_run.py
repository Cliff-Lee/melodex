from pathlib import Path


class _LocalUrl:
    def __init__(self, path: str):
        self.path = path

    def isLocalFile(self) -> bool:
        return True

    def toLocalFile(self) -> str:
        return self.path


class _DropMime:
    def __init__(self, *paths: str):
        self._urls = [_LocalUrl(path) for path in paths]

    def urls(self):
        return list(self._urls)

    def hasUrls(self) -> bool:
        return bool(self._urls)


class _DropEvent:
    def __init__(self, *paths: str):
        self._mime = _DropMime(*paths)
        self.accepted = False
        self.ignored = False

    def mimeData(self):
        return self._mime

    def acceptProposedAction(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


def _desktop_runtime(tmp_path: Path, monkeypatch):
    try:
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest

        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)
    monkeypatch.setattr(
        main_window.MainWindow,
        "_start_local_scan",
        lambda self, reason="scan": None,
    )
    return app, main_window


def test_empty_home_shows_only_the_three_first_run_actions(monkeypatch, tmp_path: Path):
    app, main_window = _desktop_runtime(tmp_path, monkeypatch)
    window = main_window.MainWindow()
    window.show()
    app.processEvents()
    try:
        assert window.acceptDrops()
        assert window.home_first_run.isVisible()
        assert not window.home_hero.isVisible()
        buttons = window.home_first_run.findChildren(main_window.QPushButton)
        actions = {
            str(button.property("firstRunAction"))
            for button in buttons
        }
        assert actions == {
            "choose-folder",
            "connect-network",
            "try-files",
            "play-something",
        }
        assert sum(button.isVisible() for button in buttons) == 3
        assert not window.first_run_play_button.isVisible()
        assert window.page_titles["home"].text() == "Your music, immediately."
    finally:
        window.close()
        app.processEvents()


def test_first_discovered_music_enables_first_run_play_something(
    monkeypatch, tmp_path: Path
):
    app, main_window = _desktop_runtime(tmp_path, monkeypatch)
    window = main_window.MainWindow()
    track = {
        "provider_id": "local",
        "track_id": str(tmp_path / "first.flac"),
        "local_path": str(tmp_path / "first.flac"),
        "title": "First track",
        "artist": "Unknown artist",
        "provisional": True,
    }
    captured = {}
    window.show()
    monkeypatch.setattr(
        window.player,
        "set_queue",
        lambda tracks, start, autoplay, **kwargs: captured.update(
            tracks=tracks, autoplay=autoplay
        ),
    )
    try:
        window._cache_progressive_tracks([track])
        app.processEvents()

        assert window.first_run_play_button.isVisible()
        assert window.first_run_play_button.objectName() == "primaryButton"
        assert window.first_run_play_button.text() == "▶  Play Something · 1 track ready"
        window.first_run_play_button.click()
        assert captured["autoplay"] is True
        assert captured["tracks"][0]["local_path"] == track["local_path"]
    finally:
        window.close()
        app.processEvents()


def test_home_hides_session_tuning_until_cached_tracks_are_hydrated(
    monkeypatch, tmp_path: Path
):
    app, main_window = _desktop_runtime(tmp_path, monkeypatch)
    window = main_window.MainWindow()
    monkeypatch.setattr(window.providers, "local_catalog_count", lambda: 12)
    monkeypatch.setattr(window.providers, "local_catalog_is_loaded", lambda: False)
    window.show()
    try:
        window._show_home()

        assert window.home_hero.isVisible()
        assert not window.home_moods_widget.isVisible()
        assert window.home_primary_button.text() == "▶  Play something"

        monkeypatch.setattr(window.providers, "local_catalog_is_loaded", lambda: True)
        window._show_home()
        assert window.home_moods_widget.isVisible()
    finally:
        window.close()
        app.processEvents()


def test_home_play_during_scan_uses_discovered_tracks_immediately(
    monkeypatch, tmp_path: Path
):
    from types import SimpleNamespace

    app, main_window = _desktop_runtime(tmp_path, monkeypatch)
    window = main_window.MainWindow()
    window.local_scan._runner = SimpleNamespace(shutdown=lambda: None)
    played = []
    monkeypatch.setattr(
        window, "_discovered_playable_tracks", lambda: [{"local_path": "/music/one.flac"}]
    )
    monkeypatch.setattr(window, "_shuffle_discovered_tracks", lambda: played.append(True))
    monkeypatch.setattr(
        window,
        "_play_for_me",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("partial discovery must not wait for the full session planner")
        ),
    )

    try:
        window._home_primary_action()

        assert played == [True]
    finally:
        window.close()
        app.processEvents()


def test_dropped_audio_plays_without_being_added_to_the_catalog(
    monkeypatch, tmp_path: Path
):
    app, main_window = _desktop_runtime(tmp_path, monkeypatch)
    window = main_window.MainWindow()
    selected = tmp_path / "dropped.flac"
    selected.write_bytes(b"test audio placeholder")
    event = _DropEvent(str(selected))
    captured = {}
    monkeypatch.setattr(
        window.player,
        "set_queue",
        lambda tracks, start, autoplay, **kwargs: captured.update(
            tracks=tracks, autoplay=autoplay
        ),
    )
    try:
        window.dropEvent(event)

        assert event.accepted
        assert captured["autoplay"] is True
        assert captured["tracks"][0]["local_path"] == str(selected)
        assert window.providers.local_catalog_count() == 0
    finally:
        window.close()
        app.processEvents()


def test_dropped_folder_is_configured_and_scanned_in_background(
    monkeypatch, tmp_path: Path
):
    app, main_window = _desktop_runtime(tmp_path, monkeypatch)
    window = main_window.MainWindow()
    music = tmp_path / "Dropped Music"
    scan_reasons = []
    open_pages = []
    monkeypatch.setattr(
        window,
        "_start_local_scan",
        lambda reason="scan": scan_reasons.append(reason),
    )
    monkeypatch.setattr(window, "open_page", lambda page: open_pages.append(page))
    event = _DropEvent(str(music))
    try:
        window.dropEvent(event)

        assert event.accepted
        assert window.providers.local_roots() == [music]
        assert scan_reasons == ["folder dropped"]
        assert open_pages == ["library"]
    finally:
        window.close()
        app.processEvents()


def test_try_files_plays_selected_tracks_without_importing_them(
    monkeypatch, tmp_path: Path
):
    app, main_window = _desktop_runtime(tmp_path, monkeypatch)
    window = main_window.MainWindow()
    selected = tmp_path / "track.flac"
    selected.write_bytes(b"test audio placeholder")
    captured = {}
    monkeypatch.setattr(
        main_window.QFileDialog,
        "getOpenFileNames",
        lambda *args, **kwargs: ([str(selected)], ""),
    )
    monkeypatch.setattr(
        window.player,
        "set_queue",
        lambda tracks, start, autoplay, **kwargs: captured.update(
            tracks=tracks,
            start=start,
            autoplay=autoplay,
            intent=kwargs.get("intent"),
        ),
    )
    try:
        window._try_audio_files()

        assert captured["autoplay"] is True
        assert captured["tracks"][0]["local_path"] == str(selected)
        assert captured["tracks"][0]["provisional"] is True
        assert window.providers.local_catalog_count() == 0
    finally:
        window.close()
        app.processEvents()
