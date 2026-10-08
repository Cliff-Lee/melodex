from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_APP = None


def _player():
    import pytest

    try:
        from PySide6.QtWidgets import QApplication
        from melodex.player import FlowPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    global _APP
    _APP = QApplication.instance() or QApplication([])
    player = FlowPlayer(lambda track: dict(track))
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
