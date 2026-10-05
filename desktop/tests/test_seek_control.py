from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from melodex.seek_interaction import SeekInteraction


def test_seek_interaction_suppresses_stale_player_updates_until_acknowledged():
    now = [10.0]
    interaction = SeekInteraction(clock=lambda: now[0])

    interaction.begin()
    assert interaction.state == "scrubbing"
    assert interaction.follow_player_position(31_000, 120_000) is False

    target = interaction.commit(750, 120_000)
    assert target == 90_000
    assert interaction.state == "committing"

    assert interaction.follow_player_position(32_000, 120_000) is False
    assert interaction.state == "committing"

    assert interaction.follow_player_position(89_500, 120_000) is True
    assert interaction.state == "idle"

    snapshot = interaction.snapshot()
    assert snapshot["commits"] == 1
    assert snapshot["acknowledged"] == 1
    assert snapshot["player_updates_suppressed"] == 2


def test_seek_interaction_times_out_instead_of_sticking_forever():
    now = [20.0]
    interaction = SeekInteraction(commit_timeout_ms=1500, clock=lambda: now[0])

    interaction.begin()
    assert interaction.commit(250, 100_000) == 25_000
    assert interaction.follow_player_position(5_000, 100_000) is False

    now[0] += 1.6
    assert interaction.follow_player_position(6_000, 100_000) is True
    assert interaction.state == "idle"
    assert interaction.snapshot()["timed_out"] == 1


def test_rapid_reseek_replaces_the_pending_target():
    interaction = SeekInteraction()

    interaction.begin()
    assert interaction.commit(800, 100_000) == 80_000
    assert interaction.follow_player_position(12_000, 100_000) is False

    interaction.begin()
    assert interaction.commit(200, 100_000) == 20_000

    # A late acknowledgement for the superseded first seek must not win.
    assert interaction.follow_player_position(80_000, 100_000) is False
    assert interaction.state == "committing"
    assert interaction.target_ms == 20_000

    assert interaction.follow_player_position(20_400, 100_000) is True
    assert interaction.state == "idle"
    snapshot = interaction.snapshot()
    assert snapshot["commits"] == 2
    assert snapshot["acknowledged"] == 1


def test_seek_interaction_cancel_resets_track_transition_state():
    interaction = SeekInteraction()

    interaction.begin()
    interaction.commit(500, 80_000)
    interaction.cancel()

    assert interaction.state == "idle"
    assert interaction.target_ms is None
    assert interaction.snapshot()["cancelled"] == 1


def test_seek_slider_clicks_anywhere_as_direct_seek():
    import pytest

    try:
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        from melodex.seek_control import SeekSlider
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    slider = SeekSlider(Qt.Horizontal)
    slider.setRange(0, 1000)
    slider.resize(400, 30)
    slider.show()
    app.processEvents()

    started = []
    finished = []
    slider.seekStarted.connect(lambda: started.append(True))
    slider.seekFinished.connect(finished.append)

    point = QPoint(300, slider.height() // 2)
    QTest.mouseClick(slider, Qt.LeftButton, Qt.NoModifier, point)
    app.processEvents()

    assert started == [True]
    assert len(finished) == 1
    assert 730 <= finished[0] <= 770
    assert finished[0] == slider.value()

    slider.close()
    slider.deleteLater()
    app.processEvents()
