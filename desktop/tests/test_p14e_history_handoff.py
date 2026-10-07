from __future__ import annotations

from pathlib import Path


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


def _tracks(count: int = 12) -> list[dict[str, str]]:
    return [
        {
            "track_id": f"track-{index}",
            "local_path": f"/music/{index}.flac",
            "artist": f"Artist {index % 6}",
            "album": f"Album {index % 6}",
            "title": f"Track {index}",
        }
        for index in range(count)
    ]


class _QueuePlayer:
    def __init__(self):
        self.queue: list[dict[str, str]] = []
        self.index = -1
        self.autoplay = False
        self.intent = "manual_queue"
        self.replacements: list[list[dict[str, str]]] = []

    def set_queue(self, tracks, start, autoplay, *, intent="manual_queue"):
        self.queue = [dict(track) for track in tracks]
        self.index = start if self.queue else -1
        self.autoplay = autoplay
        self.intent = intent

    def replace_upcoming(self, tracks):
        upcoming = [dict(track) for track in tracks]
        self.replacements.append(upcoming)
        self.queue = self.queue[: self.index + 1] + upcoming

    def close(self):
        pass


def _prepare_loaded_library(window, monkeypatch, catalog):
    monkeypatch.setattr(window.providers, "local_catalog_count", lambda: len(catalog))
    monkeypatch.setattr(window.providers, "local_catalog_is_loaded", lambda: True)
    monkeypatch.setattr(window.providers, "local_catalog", lambda: catalog)
    player = _QueuePlayer()
    window.player = player
    scheduled = {}

    def run_async(work, done, failed=None, **kwargs):
        scheduled.update(work=work, done=done, failed=failed, options=kwargs)

    monkeypatch.setattr(window, "_run_async", run_async)
    return player, scheduled


def test_play_something_starts_before_history_planner_runs(monkeypatch, tmp_path):
    app, main_window = _desktop_runtime(tmp_path, monkeypatch)
    window = main_window.MainWindow()
    catalog = _tracks(600)
    player, scheduled = _prepare_loaded_library(window, monkeypatch, catalog)
    try:
        window._home_primary_action()

        assert player.autoplay is True
        assert player.queue
        assert len(player.queue) <= 40
        assert scheduled["options"]["task_name"] == "play-for-me"
        assert scheduled["options"]["priority"] == "foreground"
    finally:
        window.close()
        app.processEvents()


def test_history_handoff_preserves_current_track_and_updates_only_tail(
    monkeypatch, tmp_path
):
    app, main_window = _desktop_runtime(tmp_path, monkeypatch)
    window = main_window.MainWindow()
    catalog = _tracks(12)
    player, scheduled = _prepare_loaded_library(window, monkeypatch, catalog)
    try:
        window._home_primary_action()
        initial = [dict(track) for track in player.queue]
        player.index = min(2, len(initial) - 1)
        prefix = [dict(track) for track in initial[: player.index + 1]]

        scheduled["done"](
            {
                "tracks": catalog,
                "new_to_you": len(catalog),
            }
        )

        assert player.queue[: player.index + 1] == prefix
        assert player.replacements
        assert all(
            track["track_id"] not in {row["track_id"] for row in prefix}
            for track in player.replacements[0]
        )
    finally:
        window.close()
        app.processEvents()


def test_history_handoff_does_not_overwrite_a_listener_queue_edit(
    monkeypatch, tmp_path
):
    app, main_window = _desktop_runtime(tmp_path, monkeypatch)
    window = main_window.MainWindow()
    catalog = _tracks(12)
    player, scheduled = _prepare_loaded_library(window, monkeypatch, catalog)
    try:
        window._home_primary_action()
        player.queue.append(
            {"track_id": "listener-choice", "local_path": "/music/chosen.flac"}
        )

        scheduled["done"]({"tracks": catalog, "new_to_you": len(catalog)})

        assert player.replacements == []
        assert player.queue[-1]["track_id"] == "listener-choice"
    finally:
        window.close()
        app.processEvents()
