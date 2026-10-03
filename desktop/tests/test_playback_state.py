from melodex.playback_state import PlaybackSessionState


def test_playback_snapshot_is_defensive_and_queue_state_is_canonical():
    state = PlaybackSessionState()
    track = {"title": "Original"}
    queued = {"title": "Next"}

    state.start_track(track, history_id=12, started_at=3.5)
    state.update_position(1_500, 90_000)
    state.set_playing(True)
    state.update_queue([queued], 0)

    first = state.snapshot()
    first.current_track["title"] = "Changed by reader"
    first.queue[0]["title"] = "Changed queue copy"
    track["title"] = "Changed source"
    queued["title"] = "Changed source queue"

    second = state.snapshot()
    assert second.current_track == {"title": "Original"}
    assert second.queue == ({"title": "Next"},)
    assert second.position_ms == 1_500
    assert second.duration_ms == 90_000
    assert second.playing is True
    assert second.current_history_id == 12
    assert second.queue_index == 0


def test_track_change_resets_progress_and_completion_clears_history_id():
    state = PlaybackSessionState()
    state.start_track({"title": "One"}, history_id=8, started_at=1.0)
    state.update_position(45_000, 60_000)

    state.start_track({"title": "Two"}, history_id=9, started_at=2.0)
    second = state.snapshot()
    assert second.current_track == {"title": "Two"}
    assert second.position_ms == 0
    assert second.duration_ms == 0
    assert second.current_history_id == 9

    assert state.mark_current_track_completed() == 9
    assert state.snapshot().current_history_id == 0
