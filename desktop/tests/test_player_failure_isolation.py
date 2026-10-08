from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_APP = None


def _player(*, playback_refresher=None, submit=None, scheduler=None):
    import pytest

    try:
        from PySide6.QtWidgets import QApplication
        from melodex.player import FlowPlayer
    except (ImportError, OSError) as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    global _APP
    _APP = QApplication.instance() or QApplication([])
    player = FlowPlayer(
        lambda track: dict(track),
        playback_refresher=playback_refresher,
        playback_refresh_scheduler=scheduler,
        playback_refresh_submit=submit,
    )
    player._timer.stop()
    return player


def test_incoming_deck_failure_aborts_crossfade_and_keeps_current_track():
    player = _player()
    player.queue = [{"track_id": "current"}, {"track_id": "next"}]
    player.index = 0
    player.active = 0
    player._crossfading = True
    player._transition_ms = 4_500
    player._crossfade_target_index = 1
    player._crossfade_deck = 1
    errors = []
    player.error.connect(errors.append)

    player._on_player_error(1, object(), "unsupported format")

    assert player.index == 0
    assert player.active == 0
    assert player._crossfading is False
    assert player._crossfade_target_index is None
    assert player._crossfade_deck is None
    assert player.outputs[0].volume() == 1.0
    assert player.outputs[1].volume() == 0.0
    assert errors == [
        "Next track could not be prepared; current track continues. "
        "unsupported format"
    ]
    snapshot = player.diagnostics_snapshot()
    assert snapshot["playback_errors"] == 1
    assert snapshot["incoming_deck_errors"] == 1
    assert snapshot["transition_aborts"] == 1
    assert snapshot["transition_state_valid"] is True
    assert "current_track" not in snapshot

    player.close()


def test_error_from_inactive_non_transition_deck_does_not_interrupt_playback():
    player = _player()
    player.queue = [{"track_id": "current"}, {"track_id": "old-next"}]
    player.index = 0
    player.active = 0
    errors = []
    player.error.connect(errors.append)

    player._on_player_error(1, object(), "late stale error")

    assert player.index == 0
    assert player.active == 0
    assert errors == []
    snapshot = player.diagnostics_snapshot()
    assert snapshot["playback_errors"] == 1
    assert snapshot["inactive_deck_errors_ignored"] == 1
    assert snapshot["active_deck_errors"] == 0

    player.close()


def test_error_from_active_deck_is_still_reported():
    player = _player()
    player.queue = [{"track_id": "current"}]
    player.index = 0
    player.active = 0
    errors = []
    player.error.connect(errors.append)

    player._on_player_error(0, object(), "network unavailable")

    assert errors == ["network unavailable"]
    snapshot = player.diagnostics_snapshot()
    assert snapshot["playback_errors"] == 1
    assert snapshot["active_deck_errors"] == 1
    assert snapshot["incoming_deck_errors"] == 0

    player.close()


def _network_error():
    from PySide6.QtMultimedia import QMediaPlayer

    return getattr(QMediaPlayer, "Error", QMediaPlayer).NetworkError


def _run_in_worker(callback):
    import threading

    worker = threading.Thread(target=callback)
    worker.start()
    worker.join(timeout=3)
    assert not worker.is_alive()


def _process_events(app):
    import time

    for _ in range(4):
        app.processEvents()
        time.sleep(0.01)


def test_transient_source_refresh_runs_in_background_and_keeps_queue_until_ready():
    import threading

    ui_thread = threading.get_ident()
    refresh_threads = []
    jobs = []

    def refresh(track):
        refresh_threads.append(threading.get_ident())
        return {**track, "stream_url": "https://stream.example/recovered.mp3"}

    def submit(callback, **_kwargs):
        jobs.append(callback)
        return True

    player = _player(playback_refresher=refresh, submit=submit)
    app = _APP
    assert app is not None
    player.players[0].errorOccurred.disconnect()
    player.players[0].mediaStatusChanged.disconnect()
    player._playback_recovery_delays_ms = (0, 0)
    player.queue = [
        {"track_id": "current", "stream_url": "https://stream.example/expired.mp3"}
    ]
    player.index = 0
    player._playback_should_play = True
    errors = []
    player.error.connect(errors.append)

    player._on_player_error(0, _network_error(), "network unavailable")
    assert refresh_threads == []
    _process_events(app)
    assert len(jobs) == 1

    _run_in_worker(jobs.pop(0))
    _process_events(app)

    assert refresh_threads and refresh_threads[0] != ui_thread
    assert player.index == 0
    assert player.current_track()["stream_url"].endswith("expired.mp3")
    assert player._playback_recovery_candidate is not None
    snapshot = player.diagnostics_snapshot()
    assert snapshot["recovery_attempts"] == 1
    assert snapshot["recovery_successes"] == 0
    assert all("stream.example" not in str(value) for value in snapshot.values())
    assert errors[0] == "Connection interrupted. Trying to resume playback."

    player._complete_playback_recovery(0)
    assert player.current_track()["stream_url"].endswith("recovered.mp3")
    assert player.diagnostics_snapshot()["recovery_successes"] == 1
    player.close()


def test_permanent_source_failures_do_not_schedule_refresh():
    jobs = []

    def submit(callback, **_kwargs):
        jobs.append(callback)
        return True

    player = _player(
        playback_refresher=lambda track: dict(track),
        submit=submit,
    )
    from PySide6.QtMultimedia import QMediaPlayer

    player.queue = [
        {"track_id": "corrupt", "stream_url": "https://stream.example/audio"}
    ]
    player.index = 0
    errors = []

    error_scope = getattr(QMediaPlayer, "Error", QMediaPlayer)
    player.error.connect(errors.append)
    player._on_player_error(0, error_scope.FormatError, "unsupported media")
    player._on_player_error(0, error_scope.AccessDeniedError, "access denied")

    assert jobs == []
    assert len(errors) == 2
    snapshot = player.diagnostics_snapshot()
    assert snapshot["permanent_source_errors"] == 2
    assert snapshot["recovery_attempts"] == 0
    player.close()


def test_recovery_is_bounded_to_two_refresh_attempts():
    jobs = []

    def submit(callback, **_kwargs):
        jobs.append(callback)
        return True

    player = _player(
        playback_refresher=lambda _track: {"track_id": "current"},
        submit=submit,
    )
    app = _APP
    assert app is not None
    player._playback_recovery_delays_ms = (0, 0)
    player.queue = [
        {"track_id": "current", "stream_url": "https://stream.example/old"}
    ]
    player.index = 0
    player._playback_should_play = True
    errors = []
    player.error.connect(errors.append)

    player._on_player_error(0, _network_error(), "network unavailable")
    for expected in (1, 2):
        _process_events(app)
        assert len(jobs) == 1
        _run_in_worker(jobs.pop(0))
        _process_events(app)
        assert player.diagnostics_snapshot()["recovery_attempts"] == expected

    player._on_player_error(0, _network_error(), "still unavailable")
    _process_events(app)
    assert jobs == []
    assert player.diagnostics_snapshot()["recovery_exhausted"] == 1
    assert errors.count(
        "Playback could not be resumed. The track remains in your queue."
    ) == 1
    assert player.current_track()["track_id"] == "current"
    player.close()


def test_stale_refresh_result_cannot_replace_a_new_queue():
    jobs = []

    def submit(callback, **_kwargs):
        jobs.append(callback)
        return True

    player = _player(
        playback_refresher=lambda track: {
            **track,
            "stream_url": "https://stream.example/stale.mp3",
        },
        submit=submit,
    )
    app = _APP
    assert app is not None
    player._playback_recovery_delays_ms = (0, 0)
    player.queue = [
        {"track_id": "old", "stream_url": "https://stream.example/old.mp3"}
    ]
    player.index = 0
    player._playback_should_play = True
    player._on_player_error(0, _network_error(), "network unavailable")
    _process_events(app)
    assert len(jobs) == 1

    player.set_queue(
        [{"track_id": "new", "stream_url": "https://stream.example/new.mp3"}],
        autoplay=False,
    )
    _run_in_worker(jobs.pop(0))
    _process_events(app)

    assert player.current_track()["track_id"] == "new"
    assert player.diagnostics_snapshot()["recovery_stale_results"] == 1
    player.close()


class _FakeScheduler:
    def __init__(self):
        self.jobs = []
        self.cancelled = []

    def submit(self, callback, **_kwargs):
        self.jobs.append(callback)
        return True

    def cancel_pending(self, replace_key):
        self.cancelled.append(replace_key)


def test_local_resource_error_probes_in_background_and_reopens_same_queue_item(tmp_path):
    from PySide6.QtMultimedia import QMediaPlayer

    scheduler = _FakeScheduler()
    player = _player(scheduler=scheduler)
    app = _APP
    assert app is not None
    player._local_reconnect_delays_ms = (0, 0, 0)
    player._playback_should_play = False
    local_path = tmp_path / "returning.wav"
    original = {"track_id": "local", "local_path": str(local_path)}
    reopened = []
    player._set_local_recovery_source = (
        lambda deck, url: reopened.append((deck, url))
    )
    player.queue = [dict(original)]
    player.index = 0
    errors = []
    player.error.connect(errors.append)

    error_scope = getattr(QMediaPlayer, "Error", QMediaPlayer)
    player._on_player_error(0, error_scope.ResourceError, "file unavailable")
    assert scheduler.jobs == []
    assert errors == [
        "Storage is unavailable. Checking again in the background."
    ]
    _process_events(app)
    assert len(scheduler.jobs) == 1

    _run_in_worker(scheduler.jobs.pop(0))
    _process_events(app)
    assert player.diagnostics_snapshot()["local_reconnect_probe_failures"] == 1
    assert player.current_track() == original
    assert len(scheduler.jobs) == 1

    local_path.write_bytes(b"available")
    _run_in_worker(scheduler.jobs.pop(0))
    _process_events(app)

    assert reopened
    assert reopened[0][0] == 0
    assert reopened[0][1].toLocalFile() == str(local_path)
    assert player._playback_recovery_candidate["resume_after_recovery"] is False
    player._complete_playback_recovery(0)
    assert player.current_track() == original
    assert player.diagnostics_snapshot()["local_reconnect_successes"] == 1
    assert player.diagnostics_snapshot()["local_reconnect_attempts"] == 2
    player.close()


def test_local_reconnect_cancels_pending_work_and_fences_late_results(tmp_path):
    from PySide6.QtMultimedia import QMediaPlayer

    scheduler = _FakeScheduler()
    player = _player(scheduler=scheduler)
    app = _APP
    assert app is not None
    player._local_reconnect_delays_ms = (0, 0, 0)
    player.queue = [
        {"track_id": "old", "local_path": str(tmp_path / "missing.wav")}
    ]
    player.index = 0
    error_scope = getattr(QMediaPlayer, "Error", QMediaPlayer)

    player._on_player_error(0, error_scope.ResourceError, "file unavailable")
    _process_events(app)
    assert len(scheduler.jobs) == 1
    job = scheduler.jobs.pop(0)

    player.set_queue([{"track_id": "new"}], autoplay=False)
    assert "playback-recovery" in scheduler.cancelled
    _run_in_worker(job)
    _process_events(app)

    assert player.current_track()["track_id"] == "new"
    assert player._playback_recovery_candidate is None
    assert player.diagnostics_snapshot()["recovery_stale_results"] == 1
    player.close()


def test_buffer_progress_and_stall_diagnostics_are_metadata_free():
    import time

    from PySide6.QtMultimedia import QMediaPlayer

    player = _player()
    notices = []
    player.playbackNotice.connect(lambda message, timeout: notices.append((message, timeout)))
    player._on_buffer_progress(0, 0.42)
    player._last_progress_at = time.monotonic() - 2
    player._monitor_position_progress(
        0, 0, QMediaPlayer.PlayingState
    )
    assert player.diagnostics_snapshot()["buffer_stall_active"] is True
    player._show_buffering_notice()
    player._monitor_position_progress(
        0, 1, QMediaPlayer.PlayingState
    )

    snapshot = player.diagnostics_snapshot()
    assert notices == [("Buffering audio…", 0), ("", 0)]
    assert snapshot["buffer_progress_events"] == 1
    assert snapshot["active_buffer_progress_permille"] == 420
    assert snapshot["buffer_progress_min_permille"] == 420
    assert snapshot["buffer_stall_no_progress_events"] == 1
    assert snapshot["buffer_stall_notices"] == 1
    assert snapshot["buffer_stall_active"] is False
    assert snapshot["buffer_stall_ms_total"] >= 0
    assert all("local_path" not in key for key in snapshot)
    player.close()




def test_local_reconnect_is_bounded_and_keeps_track_queued(tmp_path):
    from PySide6.QtMultimedia import QMediaPlayer

    scheduler = _FakeScheduler()
    player = _player(scheduler=scheduler)
    app = _APP
    assert app is not None
    player._local_reconnect_delays_ms = (0, 0, 0)
    player._playback_should_play = False
    track = {"track_id": "missing", "local_path": str(tmp_path / "missing.wav")}
    player.queue = [dict(track)]
    player.index = 0
    errors = []
    player.error.connect(errors.append)
    error_scope = getattr(QMediaPlayer, "Error", QMediaPlayer)

    player._on_player_error(0, error_scope.ResourceError, "file unavailable")
    for expected in (1, 2, 3):
        _process_events(app)
        assert len(scheduler.jobs) == 1
        _run_in_worker(scheduler.jobs.pop(0))
        _process_events(app)
        assert player.diagnostics_snapshot()["local_reconnect_attempts"] == expected

    assert scheduler.jobs == []
    assert player.current_track() == track
    assert errors[-1] == (
        "Storage is still unavailable. The track remains in your queue."
    )
    snapshot = player.diagnostics_snapshot()
    assert snapshot["local_reconnect_probe_failures"] == 3
    assert snapshot["local_reconnect_exhausted"] == 1
    player.close()
