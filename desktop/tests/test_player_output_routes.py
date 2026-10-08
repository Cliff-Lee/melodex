from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_player():
    import pytest

    try:
        from PySide6.QtWidgets import QApplication
        from melodex.player import FlowPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    player = FlowPlayer(lambda track: dict(track))
    player._timer.stop()
    return app, player


class _Device:
    def __init__(self, key: str, *, null: bool = False):
        self.key = key
        self._null = null

    def isNull(self) -> bool:
        return self._null

    def __eq__(self, other):
        return isinstance(other, _Device) and self.key == other.key


class _MediaDevices:
    def __init__(self, default_device):
        self.default_device = default_device

    def defaultAudioOutput(self):
        return self.default_device


class _Output:
    def __init__(self, device):
        self._device = device
        self.set_calls = []

    def device(self):
        return self._device

    def setDevice(self, device):
        self._device = device
        self.set_calls.append(device)


class _Player:
    def __init__(self, state, media_status, position=12_345):
        from PySide6.QtMultimedia import QMediaPlayer

        self.state = state
        self.media_status = media_status
        self.position_ms = position
        self.play_calls = 0
        self.pause_calls = 0
        self._playing = QMediaPlayer.PlayingState
        self._paused = QMediaPlayer.PausedState
        self._stopped = QMediaPlayer.StoppedState

    def playbackState(self):
        return self.state

    def mediaStatus(self):
        return self.media_status

    def play(self):
        self.play_calls += 1
        self.state = self._playing

    def pause(self):
        self.pause_calls += 1
        self.state = self._paused

    def stop(self):
        self.state = self._stopped

    def position(self):
        return self.position_ms

    def duration(self):
        return 100_000

    def isSeekable(self):
        return True


def test_output_change_rebinds_both_decks_and_resumes_requested_playback():
    import pytest

    try:
        from PySide6.QtMultimedia import QMediaPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    _app, player = _qt_player()
    old_device = _Device("old")
    new_device = _Device("new")
    old_players, old_outputs = player.players, player.outputs
    try:
        outputs = [_Output(old_device), _Output(old_device)]
        decks = [
            _Player(QMediaPlayer.PausedState, QMediaPlayer.LoadedMedia),
            _Player(QMediaPlayer.PausedState, QMediaPlayer.LoadedMedia),
        ]
        player.players = decks
        player.outputs = outputs
        player._media_devices = _MediaDevices(new_device)
        player.queue = [{"track_id": "same-entry"}]
        player.index = 0
        player.active = 0
        player._playback_should_play = True
        player._crossfading = True
        player._crossfade_deck = 1

        player._reconcile_audio_output_route()

        assert [output.device() for output in outputs] == [new_device, new_device]
        assert [len(output.set_calls) for output in outputs] == [1, 1]
        assert [deck.play_calls for deck in decks] == [1, 1]
        assert [deck.position() for deck in decks] == [12_345, 12_345]
        snapshot = player.diagnostics_snapshot()
        assert snapshot["audio_route_rebinds"] == 1
        assert snapshot["audio_route_resume_requests"] == 2
    finally:
        player.players, player.outputs = old_players, old_outputs
        player.close()


def test_output_change_never_autoplays_an_explicitly_paused_or_stopped_queue():
    import pytest

    try:
        from PySide6.QtMultimedia import QMediaPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    _app, player = _qt_player()
    old_device = _Device("old")
    new_device = _Device("new")
    old_players, old_outputs = player.players, player.outputs
    try:
        outputs = [_Output(old_device), _Output(old_device)]
        paused = _Player(QMediaPlayer.PausedState, QMediaPlayer.LoadedMedia)
        stopped = _Player(QMediaPlayer.StoppedState, QMediaPlayer.LoadedMedia)
        player.players = [paused, stopped]
        player.outputs = outputs
        player._media_devices = _MediaDevices(new_device)
        player.queue = [{"track_id": "same-entry"}]
        player.index = 0
        player.active = 0
        player._playback_should_play = False

        player._reconcile_audio_output_route()

        assert paused.play_calls == 0
        assert stopped.play_calls == 0
        assert paused.pause_calls == 0
        assert stopped.pause_calls == 0
        assert player.diagnostics_snapshot()["audio_route_resume_requests"] == 0

        playing_but_not_requested = _Player(
            QMediaPlayer.PlayingState, QMediaPlayer.LoadedMedia
        )
        player.players = [playing_but_not_requested, stopped]
        player._reconcile_audio_output_route()
        assert playing_but_not_requested.play_calls == 0
        assert playing_but_not_requested.pause_calls == 1
    finally:
        player.players, player.outputs = old_players, old_outputs
        player.close()


def test_returning_to_active_state_rechecks_the_default_output():
    import pytest

    try:
        from PySide6.QtCore import Qt
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app, player = _qt_player()
    old_device = _Device("old")
    new_device = _Device("new")
    old_outputs = player.outputs
    try:
        outputs = [_Output(old_device), _Output(old_device)]
        player.outputs = outputs
        player._media_devices = _MediaDevices(new_device)

        player._on_application_state_changed(Qt.ApplicationState.ApplicationActive)
        app.processEvents()

        assert [output.device() for output in outputs] == [new_device, new_device]
        assert player.diagnostics_snapshot()["audio_route_rebinds"] == 1
    finally:
        player.outputs = old_outputs
        player.close()


def test_missing_default_output_does_not_start_playback():
    import pytest

    try:
        from PySide6.QtMultimedia import QMediaPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    _app, player = _qt_player()
    old_device = _Device("old")
    old_players, old_outputs = player.players, player.outputs
    try:
        outputs = [_Output(old_device), _Output(old_device)]
        deck = _Player(QMediaPlayer.PausedState, QMediaPlayer.LoadedMedia)
        player.players = [deck, deck]
        player.outputs = outputs
        player._media_devices = _MediaDevices(_Device("none", null=True))
        player.queue = [{"track_id": "same-entry"}]
        player.index = 0
        player._playback_should_play = True

        player._reconcile_audio_output_route()

        assert [output.device() for output in outputs] == [old_device, old_device]
        assert deck.play_calls == 0
    finally:
        player.players, player.outputs = old_players, old_outputs
        player.close()

def test_output_change_does_not_restart_end_of_media():
    import pytest

    try:
        from PySide6.QtMultimedia import QMediaPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    _app, player = _qt_player()
    old_device = _Device("old")
    new_device = _Device("new")
    old_players, old_outputs = player.players, player.outputs
    try:
        deck = _Player(QMediaPlayer.StoppedState, QMediaPlayer.EndOfMedia)
        player.players = [deck, deck]
        player.outputs = [_Output(old_device), _Output(old_device)]
        player._media_devices = _MediaDevices(new_device)
        player.queue = [{"track_id": "finished"}]
        player.index = 0
        player._playback_should_play = True

        player._reconcile_audio_output_route()

        assert deck.play_calls == 0
    finally:
        player.players, player.outputs = old_players, old_outputs
        player.close()
