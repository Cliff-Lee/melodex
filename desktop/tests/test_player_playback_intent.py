from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _player(*, transition_for=None, transition_submit=None):
    import pytest

    try:
        from PySide6.QtWidgets import QApplication
        from melodex.player import FlowPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    QApplication.instance() or QApplication([])
    player = FlowPlayer(
        lambda track: dict(track),
        transition_for=transition_for,
        transition_submit=transition_submit,
    )
    player._timer.stop()
    return player


def test_album_intent_never_submits_flow_transition_plan():
    calls = []
    jobs = []
    player = _player(
        transition_for=lambda a, b: calls.append((a, b)) or {"duration_ms": 9000},
        transition_submit=lambda job, **_kwargs: jobs.append(job) or True,
    )

    player.set_queue(
        [{"track_id": "a"}, {"track_id": "b"}],
        0,
        False,
        intent="album",
    )

    assert jobs == []
    assert calls == []
    assert player._transition_duration() == 0
    snapshot = player.diagnostics_snapshot()
    assert snapshot["playback_intent"] == "album"
    assert snapshot["journey_transitions_enabled"] is False
    assert snapshot["transition_plan_requests"] == 0
    assert snapshot["planned_transition_target"] == -1

    player.close()


def test_journey_intent_primes_one_background_transition_plan():
    import pytest

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    calls = []
    jobs = []
    player = _player(
        transition_for=lambda a, b: calls.append(
            (a["track_id"], b["track_id"])
        ) or {"duration_ms": 7200},
        transition_submit=lambda job, **_kwargs: jobs.append(job) or True,
    )

    player.set_queue(
        [{"track_id": "a"}, {"track_id": "b"}],
        0,
        False,
        intent="journey",
    )

    assert len(jobs) == 1
    assert calls == []
    jobs.pop()()
    QApplication.processEvents()

    assert calls == [("a", "b")]
    assert player._transition_duration() == 7200
    snapshot = player.diagnostics_snapshot()
    assert snapshot["playback_intent"] == "journey"
    assert snapshot["journey_transitions_enabled"] is True
    assert snapshot["transition_plan_completed"] == 1

    player.close()


def test_invalid_playback_intent_falls_back_to_manual_queue():
    player = _player()

    player.set_queue(
        [{"track_id": "a"}],
        0,
        False,
        intent="definitely-not-an-intent",
    )

    assert player.status()["intent"] == "manual_queue"
    assert player.diagnostics_snapshot()["playback_intent"] == "manual_queue"

    player.close()


def test_album_hot_tick_does_not_start_crossfade_near_eof():
    import pytest

    try:
        from PySide6.QtMultimedia import QMediaPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    class FakePlayer:
        def duration(self):
            return 100_000

        def position(self):
            return 99_000

        def playbackState(self):
            return QMediaPlayer.PlayingState

        def stop(self):
            pass

        def isSeekable(self):
            return True

    player = _player()
    player.queue = [{"track_id": "a"}, {"track_id": "b"}]
    player.index = 0
    player._playback_intent = "album"
    player.players[0] = FakePlayer()
    started = []
    player._begin_crossfade = lambda: started.append(True)

    player._tick()

    assert started == []
    assert player.index == 0
    assert player._crossfading is False

    player.close()


def test_journey_hot_tick_still_enters_transition_window():
    import pytest

    try:
        from PySide6.QtMultimedia import QMediaPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    class FakePlayer:
        def duration(self):
            return 100_000

        def position(self):
            return 99_000

        def playbackState(self):
            return QMediaPlayer.PlayingState

        def stop(self):
            pass

        def isSeekable(self):
            return True

    player = _player()
    player.queue = [{"track_id": "a"}, {"track_id": "b"}]
    player.index = 0
    player._playback_intent = "journey"
    player._planned_transition_target = 1
    player._planned_transition_ms = 5000
    player.players[0] = FakePlayer()
    started = []
    player._begin_crossfade = lambda: started.append(True)

    player._tick()

    assert started == [True]

    player.close()


def test_album_natural_eof_advances_without_changing_intent():
    import pytest

    try:
        from PySide6.QtMultimedia import QMediaPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    player = _player()
    player.set_queue(
        [{"track_id": "a"}, {"track_id": "b"}],
        0,
        False,
        intent="album",
    )
    calls = []

    def fake_load(index, play=True, deck=None, *, announce_queue=False):
        calls.append((int(index), bool(play), deck, bool(announce_queue)))
        player.index = int(index)
        return True

    player._load_index = fake_load
    player._on_media_status(player.active, QMediaPlayer.EndOfMedia)

    assert calls == [(1, True, player.active, True)]
    assert player.index == 1
    assert player.diagnostics_snapshot()["playback_intent"] == "album"
    assert player.diagnostics_snapshot()["crossfade_started"] == 0

    player.close()
