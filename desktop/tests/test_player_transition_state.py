from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _media_player_type():
    import pytest

    try:
        from PySide6.QtMultimedia import QMediaPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")
    return QMediaPlayer


def _player():
    import pytest

    try:
        from PySide6.QtWidgets import QApplication
        from melodex.player import FlowPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    QApplication.instance() or QApplication([])
    player = FlowPlayer(lambda track: dict(track))
    player._timer.stop()
    return player


def test_outgoing_end_of_media_commits_a_started_crossfade_once():
    QMediaPlayer = _media_player_type()
    player = _player()
    player.queue = [{"track_id": "a"}, {"track_id": "b"}]
    player.index = 0
    player.active = 0
    player._crossfading = True
    player._transition_ms = 5000
    player._crossfade_target_index = 1
    player._crossfade_deck = 1

    events = []
    player.queueChanged.connect(lambda _queue: events.append(("queue", player.index)))
    player.trackChanged.connect(
        lambda track: events.append(("track", player.index, track["track_id"]))
    )

    player._on_media_status(0, QMediaPlayer.EndOfMedia)

    assert player.index == 1
    assert player.active == 1
    assert player._crossfading is False
    assert player._crossfade_target_index is None
    assert player._crossfade_deck is None
    assert events == [("queue", 1), ("track", 1, "b")]

    snapshot = player.diagnostics_snapshot()
    assert snapshot["natural_ends"] == 1
    assert snapshot["crossfade_completed"] == 1
    assert snapshot["crossfade_eof_commits"] == 1
    assert snapshot["queue_position_commits"] == 1
    assert snapshot["transition_state_valid"] is True

    # A delayed EndOfMedia from the old deck must not advance the queue again.
    player._on_media_status(0, QMediaPlayer.EndOfMedia)
    assert player.index == 1
    assert events == [("queue", 1), ("track", 1, "b")]
    assert player.diagnostics_snapshot()["natural_ends"] == 1

    player.close()


def test_natural_end_without_crossfade_advances_through_load_contract():
    QMediaPlayer = _media_player_type()
    player = _player()
    player.queue = [{"track_id": "a"}, {"track_id": "b"}]
    player.index = 0
    player.active = 0
    calls = []

    def fake_load(index, play=True, deck=None, *, announce_queue=False):
        calls.append((int(index), bool(play), deck, bool(announce_queue)))
        player.index = int(index)
        return True

    player._load_index = fake_load

    player._on_media_status(0, QMediaPlayer.EndOfMedia)

    assert calls == [(1, True, 0, True)]
    assert player.index == 1
    assert player.diagnostics_snapshot()["natural_ends"] == 1

    player.close()


def test_end_of_final_track_announces_not_playing():
    QMediaPlayer = _media_player_type()
    player = _player()
    player.queue = [{"track_id": "only"}]
    player.index = 0
    player.active = 0
    playing = []
    player.playingChanged.connect(playing.append)

    player._on_media_status(0, QMediaPlayer.EndOfMedia)

    assert playing == [False]
    assert player.index == 0
    assert player.diagnostics_snapshot()["natural_ends"] == 1

    player.close()


def test_crossfade_reconciliation_runs_before_outgoing_playback_state_gate():
    QMediaPlayer = _media_player_type()

    class FakePlayer:
        def __init__(self, duration, position, state):
            self._duration = duration
            self._position = position
            self._state = state
            self.stopped = 0

        def duration(self):
            return self._duration

        def position(self):
            return self._position

        def playbackState(self):
            return self._state

        def stop(self):
            self.stopped += 1

        def isSeekable(self):
            return True

    class FakeOutput:
        def __init__(self):
            self.value = 1.0

        def setVolume(self, value):
            self.value = float(value)

        def volume(self):
            return self.value

    player = _player()
    player.players = [
        FakePlayer(100_000, 99_950, QMediaPlayer.StoppedState),
        FakePlayer(180_000, 3_000, QMediaPlayer.PlayingState),
    ]
    player.outputs = [FakeOutput(), FakeOutput()]
    player.queue = [{"track_id": "a"}, {"track_id": "b"}]
    player.index = 0
    player.active = 0
    player._crossfading = True
    player._transition_ms = 5000
    player._crossfade_target_index = 1
    player._crossfade_deck = 1

    changed = []
    player.trackChanged.connect(lambda track: changed.append(track["track_id"]))

    player._tick()

    assert player.index == 1
    assert player.active == 1
    assert player._crossfading is False
    assert changed == ["b"]
    assert player.diagnostics_snapshot()["crossfade_completed"] == 1

    player.close()


def test_transition_cancel_restores_the_users_volume_not_full_scale():
    player = _player()
    player.queue = [{"track_id": "a"}, {"track_id": "b"}]
    player.index = 0
    player.active = 0
    player.set_volume(0.35)
    player._crossfading = True
    player._transition_ms = 5000
    player._crossfade_target_index = 1
    player._crossfade_deck = 1
    player.outputs[0].setVolume(0.12)
    player.outputs[1].setVolume(0.23)

    player._cancel_transition(stop_incoming=True, count_abort=True)

    assert abs(player.outputs[0].volume() - 0.35) < 0.001
    assert abs(player.outputs[1].volume()) < 0.001
    assert player.diagnostics_snapshot()["transition_aborts"] == 1

    player.close()


def test_seek_cancels_inflight_crossfade_before_repositioning():
    player = _player()
    player.queue = [{"track_id": "a"}, {"track_id": "b"}]
    player.index = 0
    player.active = 0
    player._crossfading = True
    player._transition_ms = 5000
    player._crossfade_target_index = 1
    player._crossfade_deck = 1

    player.seek(12_345)

    assert player._crossfading is False
    assert player.index == 0
    snapshot = player.diagnostics_snapshot()
    assert snapshot["seek_requests"] == 1
    assert snapshot["transition_aborts"] == 1
    assert snapshot["transition_state_valid"] is True

    player.close()


def test_incoming_end_before_commit_aborts_transition_without_changing_track():
    QMediaPlayer = _media_player_type()
    player = _player()
    player.queue = [{"track_id": "a"}, {"track_id": "b"}]
    player.index = 0
    player.active = 0
    player._crossfading = True
    player._transition_ms = 5000
    player._crossfade_target_index = 1
    player._crossfade_deck = 1

    player._on_media_status(1, QMediaPlayer.EndOfMedia)

    assert player.index == 0
    assert player.active == 0
    assert player._crossfading is False
    snapshot = player.diagnostics_snapshot()
    assert snapshot["transition_aborts"] == 1
    assert snapshot["natural_ends"] == 0
    assert snapshot["transition_state_valid"] is True

    player.close()


def test_transition_planner_runs_once_per_pair_not_inside_hot_loop():
    import pytest

    try:
        from PySide6.QtWidgets import QApplication
        from melodex.player import FlowPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    QApplication.instance() or QApplication([])
    calls = []
    jobs = []

    def transition_for(current, upcoming):
        calls.append((current["track_id"], upcoming["track_id"]))
        return {"duration_ms": 7300}

    def submit(job, **_kwargs):
        jobs.append(job)
        return True

    player = FlowPlayer(
        lambda track: dict(track),
        transition_for=transition_for,
        transition_submit=submit,
    )
    player._timer.stop()
    player.queue = [{"track_id": "a"}, {"track_id": "b"}]
    player.index = 0
    player._playback_intent = "journey"

    player._schedule_transition_plan()

    assert len(jobs) == 1
    assert calls == []
    for _ in range(100):
        assert player._transition_duration() == 4500
    assert calls == []

    jobs.pop(0)()
    QApplication.processEvents()

    assert calls == [("a", "b")]
    assert player._transition_duration() == 7300
    for _ in range(100):
        assert player._transition_duration() == 7300
    assert calls == [("a", "b")]

    snapshot = player.diagnostics_snapshot()
    assert snapshot["transition_plan_requests"] == 1
    assert snapshot["transition_plan_completed"] == 1

    player.close()


def test_stale_transition_plan_cannot_replace_new_queue_pair():
    import pytest

    try:
        from PySide6.QtWidgets import QApplication
        from melodex.player import FlowPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    QApplication.instance() or QApplication([])
    jobs = []

    def transition_for(current, upcoming):
        return {
            "duration_ms": 7100
            if upcoming["track_id"] == "b"
            else 2600
        }

    player = FlowPlayer(
        lambda track: dict(track),
        transition_for=transition_for,
        transition_submit=lambda job, **_kwargs: jobs.append(job) or True,
    )
    player._timer.stop()
    player.queue = [{"track_id": "a"}, {"track_id": "b"}]
    player.index = 0
    player._playback_intent = "journey"
    player._schedule_transition_plan()

    player.queue[1] = {"track_id": "c"}
    player._schedule_transition_plan()
    assert len(jobs) == 2

    jobs[0]()
    QApplication.processEvents()
    assert player._transition_duration() == 4500

    jobs[1]()
    QApplication.processEvents()
    assert player._transition_duration() == 2600
    snapshot = player.diagnostics_snapshot()
    assert snapshot["transition_plan_stale"] == 1
    assert snapshot["transition_plan_completed"] == 1

    player.close()


def test_rejected_background_transition_job_uses_bounded_fallback():
    import pytest

    try:
        from PySide6.QtWidgets import QApplication
        from melodex.player import FlowPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    QApplication.instance() or QApplication([])
    calls = []

    player = FlowPlayer(
        lambda track: dict(track),
        transition_for=lambda a, b: calls.append((a, b)) or {"duration_ms": 9900},
        transition_submit=lambda _job, **_kwargs: False,
    )
    player._timer.stop()
    player.queue = [{"track_id": "a"}, {"track_id": "b"}]
    player.index = 0
    player._playback_intent = "journey"

    player._schedule_transition_plan()

    assert calls == []
    assert player._transition_duration() == 4500
    snapshot = player.diagnostics_snapshot()
    assert snapshot["transition_plan_submit_rejected"] == 1

    player.close()
