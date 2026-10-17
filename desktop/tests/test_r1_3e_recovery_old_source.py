"""R1-3E: an old media-status event must not discard a new recovery candidate."""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_old_source_media_event_does_not_discard_current_remote_recovery():
    import pytest

    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QApplication
        from melodex.player import FlowPlayer
    except (ImportError, OSError) as exc:
        pytest.skip(f"Qt desktop runtime unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    player = FlowPlayer(lambda track: dict(track))
    player._timer.stop()
    real_deck = player.players[0]
    expected = QUrl("http://127.0.0.1:9000/play/new-token")
    old = QUrl("http://127.0.0.1:9000/play/old-token")

    class FakeDeck:
        def __init__(self):
            self.current_source = old
            self.play_count = 0
            self.seek_target = -1

        def source(self):
            return self.current_source

        def setPosition(self, position):
            self.seek_target = position

        def play(self):
            self.play_count += 1

        def stop(self):
            pass

        def setSource(self, source):
            self.current_source = source

        def position(self):
            return 0

    fake = FakeDeck()
    player.players[0] = fake
    player.queue = [{"track_id": "same", "title": "Earlier metadata"}]
    player.index = 0
    player.active = 0
    generation = player._playback_recovery_generation
    candidate = {
        "generation": generation,
        "index": 0,
        "deck": 0,
        "attempt": 1,
        "mode": "remote",
        "track": {"track_id": "same", "title": "Refreshed metadata"},
        "url": expected,
        "position_ms": 1200,
        "resume_after_recovery": True,
    }
    player._playback_recovery_candidate = candidate
    try:
        # The old media source reports LoadedMedia after a new candidate was
        # installed, but before QMediaPlayer.source() switches to that source.
        player._complete_playback_recovery(0)
        assert player._playback_recovery_candidate is candidate
        assert player._runtime_metrics["recovery_successes"] == 0
        assert fake.play_count == 0
        assert fake.seek_target == -1

        # Later the real target URL becomes active and LoadedMedia arrives.
        fake.current_source = expected
        player._complete_playback_recovery(0)
        assert player._playback_recovery_candidate is None
        assert player._runtime_metrics["recovery_successes"] == 1
        assert fake.play_count == 1
        assert fake.seek_target == 1200
        assert player.current_track()["title"] == "Refreshed metadata"
    finally:
        player.players[0] = real_deck
        player.close()
        player.deleteLater()
        app.processEvents()
