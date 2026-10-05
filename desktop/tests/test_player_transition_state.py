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
    from PySide6.QtMultimedia import QMediaPlayer

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
    from PySide6.QtMultimedia import QMediaPlayer

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
    from PySide6.QtMultimedia import QMediaPlayer

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


def test_incoming_end_before_commit_aborts_transition_without_changing_track():
    from PySide6.QtMultimedia import QMediaPlayer

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
