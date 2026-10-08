from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _player(resolver, scheduler):
    import pytest

    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QMediaPlayer
        from PySide6.QtWidgets import QApplication
        from melodex.player import FlowPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    class FakeDeck:
        def __init__(self, state=QMediaPlayer.StoppedState, duration=0, position=0):
            self.state = state
            self._duration = int(duration)
            self._position = int(position)
            self._source = QUrl()
            self.sources = []
            self.plays = 0
            self.stops = 0

        def duration(self):
            return self._duration

        def position(self):
            return self._position

        def playbackState(self):
            return self.state

        def source(self):
            return self._source

        def setSource(self, source):
            self._source = source
            self.sources.append(source.toString())

        def play(self):
            self.plays += 1
            self.state = QMediaPlayer.PlayingState

        def stop(self):
            self.stops += 1
            self.state = QMediaPlayer.StoppedState

        def isSeekable(self):
            return True

    class FakeOutput:
        def __init__(self):
            self.value = 1.0

        def setVolume(self, value):
            self.value = float(value)

        def volume(self):
            return self.value

    QApplication.instance() or QApplication([])
    flow = FlowPlayer(
        resolver,
        playback_refresh_scheduler=scheduler,
    )
    flow._timer.stop()
    flow.players = [
        FakeDeck(QMediaPlayer.PlayingState, 120_000, 110_000),
        FakeDeck(),
    ]
    flow.outputs = [FakeOutput(), FakeOutput()]
    flow.queue = [
        {"provider_id": "local", "track_id": "a"},
        {"provider_id": "local", "track_id": "b"},
        {"provider_id": "local", "track_id": "c"},
    ]
    flow.index = 0
    flow.active = 0
    flow._playback_should_play = True
    return flow, FakeDeck, QMediaPlayer


class FakeScheduler:
    def __init__(self, *, accepted=True):
        self.accepted = accepted
        self.jobs = []
        self.cancelled = []

    def submit(self, callback, **kwargs):
        self.jobs.append((callback, kwargs))
        return self.accepted

    def cancel_pending(self, key):
        self.cancelled.append(key)
        return 1


def test_prefetch_resolves_on_scheduler_and_manual_next_uses_prepared_deck():
    scheduler = FakeScheduler()
    resolved = []
    flow, _, QMediaPlayer = _player(
        lambda track: resolved.append(dict(track))
        or {**track, "stream_url": "https://media.example/b.mp3"},
        scheduler,
    )
    try:
        flow._request_predictive_prefetch()

        assert len(scheduler.jobs) == 1
        callback, options = scheduler.jobs[0]
        assert options["priority"] == "prefetch"
        assert options["replace_key"] == "predictive-playback-prefetch"
        assert resolved == []
        assert flow._predictive_prefetch_request["index"] == 1

        callback()

        assert len(resolved) == 1
        assert flow._predictive_prefetch["deck"] == 1
        assert flow._predictive_prefetch["ready"] is False
        assert flow.players[1].sources == ["https://media.example/b.mp3"]

        flow._on_media_status(1, QMediaPlayer.LoadedMedia)
        flow.next()

        assert flow.index == 1
        assert flow.active == 1
        assert flow.players[1].sources == ["https://media.example/b.mp3"]
        assert flow.players[1].plays == 1
        assert flow.diagnostics_snapshot()["predictive_prefetch_uses"] == 1
        assert flow.diagnostics_snapshot()["predictive_prefetch_ready_uses"] == 1
        assert flow.diagnostics_snapshot()["predictive_prefetch_requests"] == 1
    finally:
        flow.close()


def test_prefetch_result_is_discarded_after_upcoming_track_changes():
    scheduler = FakeScheduler()
    flow, _, _ = _player(
        lambda track: {**track, "stream_url": "https://media.example/b.mp3"},
        scheduler,
    )
    try:
        flow._request_predictive_prefetch()
        callback, _ = scheduler.jobs[0]

        assert flow.replace_queue_item(
            1, {"provider_id": "local", "track_id": "replacement"}
        )
        callback()

        snapshot = flow.diagnostics_snapshot()
        assert flow._predictive_prefetch is None
        assert flow.index == 0
        assert flow.queue[1]["track_id"] == "replacement"
        assert snapshot["predictive_prefetch_stale_results"] == 1
        assert snapshot["predictive_prefetch_cancelled"] == 1
        assert scheduler.cancelled == ["predictive-playback-prefetch"]
    finally:
        flow.close()


def test_journey_crossfade_reuses_prepared_source():
    scheduler = FakeScheduler()
    resolved = []
    flow, _, _ = _player(
        lambda track: resolved.append(dict(track))
        or {**track, "stream_url": "https://media.example/b.mp3"},
        scheduler,
    )
    try:
        flow._playback_intent = "journey"
        flow._request_predictive_prefetch()
        callback, _ = scheduler.jobs[0]
        callback()
        flow._begin_crossfade()

        assert flow._crossfading is True
        assert flow._crossfade_deck == 1
        assert flow.players[1].sources == ["https://media.example/b.mp3"]
        assert flow.players[1].plays == 1
        assert len(resolved) == 1
        assert flow.diagnostics_snapshot()["predictive_prefetch_uses"] == 1
    finally:
        flow.close()


def test_natural_end_starts_prepared_source_without_resolving_twice():
    scheduler = FakeScheduler()
    resolved = []
    flow, _, QMediaPlayer = _player(
        lambda track: resolved.append(dict(track))
        or {**track, "stream_url": "https://media.example/b.mp3"},
        scheduler,
    )
    try:
        flow._request_predictive_prefetch()
        callback, _ = scheduler.jobs[0]
        callback()
        flow._on_media_status(1, QMediaPlayer.LoadedMedia)

        flow._on_media_status(0, QMediaPlayer.EndOfMedia)

        assert flow.index == 1
        assert flow.active == 1
        assert flow.players[1].sources == ["https://media.example/b.mp3"]
        assert flow.players[1].plays == 1
        assert len(resolved) == 1
        assert flow.diagnostics_snapshot()["natural_ends"] == 1
    finally:
        flow.close()


def test_scheduler_rejection_leaves_current_playback_untouched():
    scheduler = FakeScheduler(accepted=False)
    flow, _, QMediaPlayer = _player(
        lambda track: {**track, "stream_url": "https://media.example/b.mp3"},
        scheduler,
    )
    try:
        flow._request_predictive_prefetch()

        snapshot = flow.diagnostics_snapshot()
        assert flow.index == 0
        assert flow.active == 0
        assert flow.players[0].playbackState() == QMediaPlayer.PlayingState
        assert flow._predictive_prefetch is None
        assert snapshot["predictive_prefetch_submit_rejected"] == 1
    finally:
        flow.close()


def test_discarding_prepared_gateway_source_releases_temporary_resource():
    scheduler = FakeScheduler()
    flow, _, _ = _player(
        lambda track: {
            **track,
            "url": "http://127.0.0.1:8765/audio",
            "headers": {"Authorization": "Bearer transient"},
        },
        scheduler,
    )
    try:
        flow._request_predictive_prefetch()
        callback, _ = scheduler.jobs[0]
        callback()

        assert len(flow.gateway._resources) == 1
        assert flow.remove_queue_item(1)
        assert flow.gateway._resources == {}
    finally:
        flow.close()
