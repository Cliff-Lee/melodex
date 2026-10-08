from types import SimpleNamespace

from melodex.living_queue_wiring import connect_living_queue


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in self.callbacks:
            callback(*args)


def _signals(*names):
    return SimpleNamespace(**{name: FakeSignal() for name in names})


def test_living_queue_signals_connect_owners_without_direct_state_access():
    calls = []
    player = SimpleNamespace(
        remove_queue_item=lambda index: calls.append(("remove", index)),
        move_queue_item=lambda source, target: calls.append(("move", source, target)),
        replace_upcoming=lambda tracks: calls.append(("replace", tracks)),
    )
    playback = _signals(
        "removeQueueItemRequested",
        "moveQueueItemRequested",
        "replaceUpcomingRequested",
        "moreLikeRequested",
        "towardArtistRequested",
        "towardRegionRequested",
        "steerJourneyRequested",
    )
    playback.keep_queue_track = lambda index: calls.append(("keep", index))
    playback.apply_journey_replan = lambda tracks: calls.append(("replan", tracks))
    playback.set_queue_track_reasons = lambda reasons: calls.append(("reasons", reasons))

    journey = _signals(
        "protectQueueTrackRequested",
        "replaceUpcomingRequested",
        "queueTrackReasonsRequested",
    )
    journey.request_more_like = lambda track, index: calls.append(("similar", track, index))
    journey.request_toward_artist = lambda track: calls.append(("artist", track))
    journey.request_toward_region = lambda track: calls.append(("region", track))
    journey.request_live_steer = lambda direction: calls.append(("steer", direction))

    connect_living_queue(player, playback, journey)
    playback.removeQueueItemRequested.emit("3")
    playback.moveQueueItemRequested.emit("2", "4")
    playback.moreLikeRequested.emit({"title": "A"}, 1)
    playback.towardArtistRequested.emit({"artist": "B"})
    playback.towardRegionRequested.emit({"title": "C"})
    playback.steerJourneyRequested.emit("calmer")
    playback.replaceUpcomingRequested.emit([{"title": "D"}])
    journey.protectQueueTrackRequested.emit(2)
    journey.replaceUpcomingRequested.emit([{"title": "E"}])
    journey.queueTrackReasonsRequested.emit({("track_id", "1"): "reason"})

    assert calls == [
        ("remove", 3),
        ("move", 2, 4),
        ("similar", {"title": "A"}, 1),
        ("artist", {"artist": "B"}),
        ("region", {"title": "C"}),
        ("steer", "calmer"),
        ("replace", [{"title": "D"}]),
        ("keep", 2),
        ("replan", [{"title": "E"}]),
        ("reasons", {("track_id", "1"): "reason"}),
    ]
