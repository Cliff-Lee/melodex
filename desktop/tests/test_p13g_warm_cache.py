from pathlib import Path

from melodex.provider_manager import ProviderManager
from melodex.providers.local_files import LocalFilesProvider
from melodex.user_state import UserState


def test_playback_checkpoint_and_recent_directories_survive_restart(tmp_path: Path):
    db = tmp_path / "taste.sqlite3"
    music = tmp_path / "NAS" / "Music"
    track = {
        "provider_id": "local",
        "track_id": str(music / "track.flac"),
        "local_path": str(music / "track.flac"),
        "title": "Track",
        "artist": "Artist",
    }
    state = UserState(db)
    state.save_playback_checkpoint(track, 42_000)
    state.record_recent_directory(music)
    state.set_source_status(str(music.parent), "unavailable", "NAS asleep")
    state.close()

    restored = UserState(db)
    try:
        checkpoint = restored.playback_checkpoint()
        assert checkpoint["track"] == track
        assert checkpoint["position_ms"] == 42_000
        assert restored.recent_directories()[0]["path"] == str(music.absolute())
        assert restored.source_statuses()[str(music.parent)]["status"] == "unavailable"
    finally:
        restored.close()


def test_local_playback_queue_survives_restart_without_stream_credentials(
    tmp_path: Path,
):
    db = tmp_path / "taste.sqlite3"
    first = UserState(db)
    queue = [
        {
            "provider_id": "local",
            "track_id": "/music/a.flac",
            "local_path": "/music/a.flac",
            "title": "A",
            "stream_url": "https://expired.example/a",
        },
        {
            "provider_id": "local",
            "track_id": "/music/b.flac",
            "local_path": "/music/b.flac",
            "title": "B",
        },
        {"provider_id": "radio", "track_id": "radio:1", "stream_url": "https://secret.example"},
    ]
    first.save_playback_queue(queue, 1)
    first.close()

    restored = UserState(db)
    try:
        snapshot = restored.playback_queue()
        assert snapshot is not None
        assert [row["track_id"] for row in snapshot["tracks"]] == [
            "/music/a.flac", "/music/b.flac"
        ]
        assert snapshot["queue_index"] == 1
        assert all("stream_url" not in row for row in snapshot["tracks"])
    finally:
        restored.close()


def test_cached_track_availability_is_annotated_without_stat(tmp_path: Path):
    root = tmp_path / "offline-nas"
    audio = root / "Artist" / "Album" / "track.flac"
    provider = LocalFilesProvider([root], scan_on_init=False)
    provider.load_cached_tracks(
        [{"provider_id": "local", "track_id": str(audio), "local_path": str(audio)}]
    )

    provider.set_source_availability(root, "unavailable")

    assert provider.tracks[0]["availability"] == "unavailable"


def test_returning_provider_hydrates_indexed_cache_without_source_probe(tmp_path: Path):
    data_dir = tmp_path / "data"
    root = tmp_path / "offline-nas"
    track = {
        "provider_id": "local",
        "track_id": str(root / "Artist" / "track.flac"),
        "local_path": str(root / "Artist" / "track.flac"),
        "title": "Track",
    }

    first = ProviderManager(data_dir)
    try:
        first.set_local_roots([root])
        first.persist_local_scan_snapshot(
            [root], {"tracks": [track], "directories": [], "metrics": {}}
        )
    finally:
        first.close()

    returning = ProviderManager(data_dir)
    try:
        assert not returning.local_catalog_is_loaded()
        assert returning.local_catalog_count() == 1
        first_track = returning.first_indexed_local_track([root])
        assert first_track["track_id"] == track["track_id"]
        assert not returning.local_catalog_is_loaded()
        rows = returning.load_indexed_local_tracks([root])
        assert returning.hydrate_local_catalog_cache(rows, [root])
        assert returning.local_catalog_is_loaded()
        assert returning.local_catalog()[0]["track_id"] == track["track_id"]
        assert not returning.hydrate_local_catalog_cache(rows, [tmp_path / "other"])
    finally:
        returning.close()


def test_changing_roots_prunes_removed_tracks_but_keeps_shared_cache(tmp_path: Path):
    data_dir = tmp_path / "data"
    root_a = tmp_path / "Music A"
    root_b = tmp_path / "Music B"
    track_a = {
        "provider_id": "local",
        "track_id": str(root_a / "a.flac"),
        "local_path": str(root_a / "a.flac"),
        "title": "A",
    }
    track_b = {
        "provider_id": "local",
        "track_id": str(root_b / "b.flac"),
        "local_path": str(root_b / "b.flac"),
        "title": "B",
    }
    manager = ProviderManager(data_dir)
    try:
        manager.configure_local_roots([root_a, root_b])
        provider = manager.providers["local"]
        assert isinstance(provider, LocalFilesProvider)
        provider.load_cached_tracks([track_a, track_b])

        manager.configure_local_roots([root_b])

        assert manager.local_catalog_count() == 1
        assert [track["title"] for track in manager.local_catalog()] == ["B"]
    finally:
        manager.close()


def test_changing_roots_updates_deferred_cache_loader(tmp_path: Path):
    data_dir = tmp_path / "data"
    root_a = tmp_path / "Music A"
    root_b = tmp_path / "Music B"
    track_a = {
        "provider_id": "local",
        "track_id": str(root_a / "a.flac"),
        "local_path": str(root_a / "a.flac"),
        "title": "A",
    }
    track_b = {
        "provider_id": "local",
        "track_id": str(root_b / "b.flac"),
        "local_path": str(root_b / "b.flac"),
        "title": "B",
    }
    first = ProviderManager(data_dir)
    try:
        first.configure_local_roots([root_a, root_b])
        first.persist_local_scan_snapshot(
            [root_a, root_b],
            {"tracks": [track_a, track_b], "directories": [], "metrics": {}},
        )
    finally:
        first.close()

    returning = ProviderManager(data_dir)
    try:
        assert not returning.local_catalog_is_loaded()
        returning.configure_local_roots([root_b])

        catalog = returning.local_catalog()
        assert [track["title"] for track in catalog] == ["B"]
    finally:
        returning.close()


def test_opening_library_does_not_force_synchronous_cache_hydration(
    monkeypatch, tmp_path: Path
):
    try:
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
        from melodex.library_index import LocalLibraryIndex
    except ImportError as exc:
        import pytest

        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    root = tmp_path / "offline-nas"
    (tmp_path / "sources.json").write_text(
        __import__("json").dumps({"local_roots": [str(root)]}), encoding="utf-8"
    )
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])
    track = {
        "provider_id": "local",
        "track_id": str(root / "cached.flac"),
        "local_path": str(root / "cached.flac"),
        "title": "Cached track",
    }
    index.replace_scan(
        [root],
        {
            "tracks": [track],
            "index_tracks": [dict(track)],
            "root_states": [{"path": str(root), "available": True}],
            "metrics": {"tracks_indexed": 1},
            "cancelled": False,
        },
    )

    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_scan", lambda self, reason="scan": None)

    def hold_hydration(self, _roots):
        self._local_cache_hydration_pending = True

    monkeypatch.setattr(
        main_window.MainWindow, "_start_local_cache_hydration", hold_hydration
    )
    window = main_window.MainWindow()
    try:
        window.navigation.ensure_lazy_page_built("library")
        window.current_page = "library"
        window._refresh_library()
        assert not window.providers.local_catalog_is_loaded()
        assert window.library_browser.empty.title_label.text() == "Restoring your music…"
    finally:
        window.close()
        app.processEvents()
