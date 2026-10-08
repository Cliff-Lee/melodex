from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


class FakeState:
    def __init__(self):
        self.values = {}
        self.plays = []
        self.skips = []
        self.completed = []
        self.feedback = []
        self.keeps = []
        self.taste_adjustments = []
        self.cleared_taste_adjustments = []
        self.moments = []

    def get_bool(self, key, default=False):
        return bool(self.values.get(key, default))

    def set_bool(self, key, value):
        self.values[key] = bool(value)

    def get_text(self, key, default=""):
        return str(self.values.get(key, default))

    def set_text(self, key, value):
        self.values[key] = str(value)

    def record_play(self, track):
        self.plays.append(dict(track))
        return len(self.plays)

    def record_skip(self, track):
        self.skips.append(dict(track))

    def mark_completed(self, history_id):
        self.completed.append(int(history_id))

    def track_signal(self, _track):
        return {}

    def record_feedback(self, track, positive):
        self.feedback.append((dict(track), bool(positive)))

    def record_keep(self, track):
        self.keeps.append(dict(track))

    def record_taste_correction(self, track, direction):
        self.taste_adjustments.append((dict(track), str(direction)))
        return True

    def clear_taste_correction(self, track):
        self.cleared_taste_adjustments.append(dict(track))
        return True

    def recent_tracks(self, _limit):
        return []

    def save_moment(self, track, position_ms, label):
        self.moments.append((dict(track), int(position_ms), str(label)))
        return "moment-1"


class FakeProviders:
    def inspect_resolution(self, _target, _limit):
        return {"candidates": [], "blocked_count": 0, "minimum_score": 0.62}

    def prefer_resolution(self, _target, _candidate):
        return None

    def block_resolution(self, _target, _candidate):
        return None

    def clear_resolution_preference(self, _target):
        return None

    def clear_resolution_blocks(self, _target):
        return None

    def resolve_exact(self, candidate, _target):
        return dict(candidate)

    def resolve(self, target):
        return dict(target)


class FakeFlow:
    analysis_available = True

    def cached_analysis_for(self, _path):
        return None

    def plan_order(self, queue, _path_for, *, start_index, adventurous):
        return {
            "tracks": list(reversed([dict(track) for track in queue])),
            "analysed": len(queue),
            "start_index": start_index,
            "adventurous": adventurous,
        }


class FakeMotion:
    def settle(self, *_args, **_kwargs):
        return None


class FakeMetadata:
    def local_artwork(self, _track):
        return {}


def _feature(tmp_path):
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.playback_feature import PlaybackFeature
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    state = FakeState()
    statuses = []

    def run_async(work, done=None, failed=None, **_kwargs):
        try:
            result = work()
        except Exception as exc:
            if failed is not None:
                failed(str(exc))
            return
        if done is not None:
            done(result)

    feature = PlaybackFeature(
        FakeProviders(),
        state,
        FakeFlow(),
        Path(tmp_path),
        metadata=lambda: FakeMetadata(),
        knowledge=lambda: SimpleNamespace(remember=lambda *_a, **_k: None),
        llm_settings=lambda: SimpleNamespace(
            model="",
            endpoint="",
            provider="ollama",
        ),
        open_llm_settings=lambda: None,
        llm_complete=lambda *_a, **_k: "",
        run_async=run_async,
        invalidate_async=lambda _scope: None,
        is_closing=lambda: False,
        scan_active=lambda: False,
        power_tools_enabled=lambda: False,
        motion=FakeMotion(),
        page_titles={},
    )
    feature.statusMessageRequested.connect(
        lambda message, timeout: statuses.append((message, timeout))
    )
    return app, feature, state, statuses


def _track(title="Track", index=1):
    return {
        "provider_id": "local",
        "track_id": f"t{index}",
        "local_path": f"/music/{title}.mp3",
        "artist": "Artist",
        "album": "Album",
        "title": title,
    }


def test_playback_feature_owns_persistent_surfaces_and_lazy_now_playing(tmp_path):
    app, feature, _state, _statuses = _feature(tmp_path)

    assert feature.current_track() is None
    assert feature.queue_snapshot() == []
    assert feature.queue_index() == -1
    assert feature.player_bar.objectName() == "playerBar"
    assert feature.queue_panel.objectName() == "queuePanel"
    assert feature.queue_keep_button.text() == "Keep"
    assert feature.queue_remove_button.text() == "Remove"
    assert feature.queue_up_button.accessibleName() == "Move earlier"
    assert feature.queue_down_button.accessibleName() == "Move later"
    assert feature.queue_lock_button.text() == "Lock next 3"
    assert feature.queue_undo_button.text() == "Undo route change"
    assert feature.queue_reason_label.objectName() == "queueReasonLabel"
    assert feature.queue_steering.count() == 9
    assert feature.queue_more_like_button.text() == "More like selected track"
    assert feature.now_playing_built is False
    assert not hasattr(feature, "rich_now")
    assert not hasattr(feature, "player")

    feature.build_now_playing()
    app.processEvents()

    assert feature.now_playing_built is True
    assert feature.now_views.tabText(0) == "Now Playing"
    assert feature.now_views.tabText(1) == "Visuals"
    assert "now_playing" in feature.page_titles

    feature.deleteLater()
    app.processEvents()


def test_journey_replan_preserves_pinned_queue_entry(tmp_path):
    app, feature, _state, _statuses = _feature(tmp_path)
    current, kept, old = (_track(name, i) for i, name in enumerate(
        ("Current", "Keep", "Old"), start=1
    ))
    replanned = []
    feature.replaceUpcomingRequested.connect(
        lambda tracks: replanned.append([dict(track) for track in tracks])
    )
    feature.on_queue_changed([current, kept, old], index=0)
    assert feature.living_queue.pin(1) is True

    feature.apply_journey_replan([_track("New A", 4), _track("New B", 5)])

    assert [track["title"] for track in replanned[-1]] == [
        "Keep",
        "New A",
        "New B",
    ]
    assert feature.living_queue.entries[1].pinned is True

    feature.deleteLater()
    app.processEvents()


def test_queue_surface_requests_live_steer_and_more_like(tmp_path):
    app, feature, _state, _statuses = _feature(tmp_path)
    current, upcoming = _track("Current", 1), _track("Upcoming", 2)
    feature.on_queue_changed([current, upcoming], index=0)
    more_like = []
    toward_artist = []
    steering = []
    feature.moreLikeRequested.connect(
        lambda track, index: more_like.append((dict(track), index))
    )
    feature.towardArtistRequested.connect(
        lambda track: toward_artist.append(dict(track))
    )
    feature.steerJourneyRequested.connect(steering.append)

    feature.queue_list.setCurrentRow(1)
    feature._queue_more_like_selected()
    feature._queue_toward_artist_selected()
    feature.queue_steering.setCurrentIndex(
        feature.queue_steering.findData("more_surprising")
    )
    feature._queue_apply_steer()

    assert more_like == [(upcoming, 1)]
    assert toward_artist == [upcoming]
    assert feature.living_queue.entries[1].pinned is False
    assert steering == ["more_surprising"]
    assert feature.queue_steering.currentIndex() == 0

    feature.deleteLater()
    app.processEvents()


def test_lock_and_undo_protect_route_tail_and_restore_generated_tracks(tmp_path):
    app, feature, _state, _statuses = _feature(tmp_path)
    current, kept, old = (_track(name, i) for i, name in enumerate(
        ("Current", "Kept", "Old"), start=1
    ))
    replacements = []
    feature.replaceUpcomingRequested.connect(
        lambda tracks: feature.on_queue_changed([current, *tracks], index=0)
    )
    feature.replaceUpcomingRequested.connect(
        lambda tracks: replacements.append([dict(track) for track in tracks])
    )
    feature.on_queue_changed([current, kept, old], index=0)

    feature.queue_list.setCurrentRow(1)
    feature._queue_toggle_lock()
    feature.apply_journey_replan([_track("New", 4)])
    assert [track["title"] for track in replacements[-1]] == ["Kept", "New"]
    assert feature.living_queue.entries[1].locked is True
    assert feature.queue_undo_button.isEnabled() is True

    feature._queue_undo_replan()
    assert [track["title"] for track in replacements[-1]] == ["Kept", "Old"]
    assert feature.living_queue.entries[1].locked is True
    assert feature.living_queue.can_undo_replan is False

    feature.deleteLater()
    app.processEvents()


def test_selected_queue_track_displays_route_reason(tmp_path):
    app, feature, _state, _statuses = _feature(tmp_path)
    current, upcoming = _track("Current", 1), _track("Similar", 2)
    feature.on_queue_changed([current, upcoming], index=0)
    feature.set_queue_track_reasons(
        {("track_id", "t2"): "More like this · similarity 91%"}
    )

    feature.queue_list.setCurrentRow(1)
    assert feature.queue_reason_label.text() == (
        "Why this track: More like this · similarity 91%"
    )
    assert "Why this track: More like this" in feature.queue_list.item(1).toolTip()

    feature.deleteLater()
    app.processEvents()


def test_selected_queue_track_displays_mind_taste_reason_without_route_mapping(tmp_path):
    app, feature, _state, _statuses = _feature(tmp_path)
    current = _track("Current", 1)
    upcoming = dict(
        _track("Suggested", 2),
        _mind_reason="fresh discovery · matches your listening history with Artist",
    )
    feature.on_queue_changed([current, upcoming], index=0)

    feature.queue_list.setCurrentRow(1)

    expected = "Why this track: " + upcoming["_mind_reason"]
    assert feature.queue_reason_label.text() == expected
    assert expected in feature.queue_list.item(1).toolTip()

    feature.deleteLater()
    app.processEvents()


def test_selected_map_track_carries_taste_reason_into_living_queue(tmp_path):
    app, feature, _state, _statuses = _feature(tmp_path)
    current = _track("Current", 1)
    upcoming = dict(
        _track("Suggested", 2),
        _taste_model_reason="matches your request for more Artist",
    )
    feature.on_queue_changed([current, upcoming], index=0)

    feature.queue_list.setCurrentRow(1)

    expected = "Why this track: " + upcoming["_taste_model_reason"]
    assert feature.queue_reason_label.text() == expected
    assert expected in feature.queue_list.item(1).toolTip()

    feature.deleteLater()
    app.processEvents()


def test_transport_seek_and_queue_actions_are_semantic(tmp_path):
    app, feature, _state, _statuses = _feature(tmp_path)

    previous = []
    play_pause = []
    next_calls = []
    seeks = []
    jumps = []
    feature.previousRequested.connect(lambda: previous.append(True))
    feature.playPauseRequested.connect(lambda: play_pause.append(True))
    feature.nextRequested.connect(lambda: next_calls.append(True))
    feature.seekRequested.connect(seeks.append)
    feature.jumpQueueRequested.connect(jumps.append)

    feature.previousRequested.emit()
    feature.playPauseRequested.emit()
    feature.nextRequested.emit()

    feature.on_position(30_000, 120_000)
    feature.seek.setValue(500)
    feature._seek_released()

    feature.on_queue_changed([_track("One", 1), _track("Two", 2)], 0)
    item = feature.queue_list.item(1)
    feature._queue_jump(item)

    assert previous == [True]
    assert play_pause == [True]
    assert next_calls == [True]
    assert seeks == [60_000]
    assert jumps == [1]
    assert feature.queue_index() == 0
    assert feature.queue_list.item(0).text().startswith("▶ ")

    feature.deleteLater()
    app.processEvents()


def test_seek_slider_keeps_user_target_until_backend_acknowledges(tmp_path):
    app, feature, _state, _statuses = _feature(tmp_path)
    seeks = []
    feature.seekRequested.connect(seeks.append)

    feature.on_position(30_000, 120_000)
    assert feature.seek.value() == 250

    feature._seek_started()
    feature.seek.setValue(750)
    feature.on_position(31_000, 120_000)
    assert feature.seek.value() == 750

    feature._seek_finished(750)
    assert seeks == [90_000]

    # The next player tick still reports the old FLAC position. Before P14b
    # this overwrote the slider immediately and made the seek appear to fail.
    feature.on_position(32_000, 120_000)
    assert feature.seek.value() == 750
    assert feature._seek_interaction.state == "committing"

    # Once the media backend reports the target, normal tracking resumes.
    feature.on_position(89_500, 120_000)
    assert 740 <= feature.seek.value() <= 750
    assert feature._seek_interaction.state == "idle"
    assert feature._seek_interaction.snapshot()["acknowledged"] == 1

    feature.deleteLater()
    app.processEvents()


def test_track_change_cancels_pending_seek_ownership(tmp_path):
    app, feature, _state, _statuses = _feature(tmp_path)

    feature.on_position(10_000, 100_000)
    feature._seek_started()
    feature.seek.setValue(800)
    feature._seek_finished(800)
    assert feature._seek_interaction.state == "committing"

    feature.on_track_changed(_track("Next", 2))

    assert feature._seek_interaction.state == "idle"
    assert feature.seek.value() == 0

    feature.deleteLater()
    app.processEvents()


def test_track_change_updates_owned_state_and_emits_snapshot(tmp_path):
    app, feature, state, _statuses = _feature(tmp_path)
    changed = []
    feature.currentTrackChanged.connect(lambda track: changed.append(dict(track)))

    track = _track("Current", 1)
    feature.on_track_changed(track)
    app.processEvents()

    assert feature.current_track() == track
    assert state.plays == []
    assert changed == [track]
    assert feature.now_title.text() == "Current"
    assert "Artist" in feature.now_meta.text()
    assert feature.current_position_ms() == 0

    # Merely selecting a provisional track is not listening history. The write
    # begins only after FlowPlayer acknowledges the playback request.
    feature.on_playing_changed(True)
    assert state.plays == [track]
    assert feature.current_history_id() == 1

    feature.merge_current_track({"title": "Corrected"})
    assert feature.current_track()["title"] == "Corrected"
    assert feature.now_title.text() == "Corrected"

    feature.deleteLater()
    app.processEvents()


def test_provisional_track_selection_does_not_record_until_play(tmp_path):
    app, feature, state, _statuses = _feature(tmp_path)

    feature.on_track_changed(_track("Ready", 3))

    assert state.plays == []
    assert feature.current_history_id() == 0

    feature.on_playing_changed(True)

    assert len(state.plays) == 1
    assert feature.current_history_id() == 1

    feature.deleteLater()
    app.processEvents()


def test_flow_refinement_requests_new_queue_without_player_access(tmp_path):
    app, feature, _state, statuses = _feature(tmp_path)
    requested = []
    feature.setQueueRequested.connect(
        lambda tracks,start,autoplay,intent:requested.append(
            (list(tracks),int(start),bool(autoplay),str(intent))
        )
    )

    one = _track("One", 1)
    two = _track("Two", 2)
    feature.on_queue_changed([one, two], 0)
    feature.refine_queue()

    assert requested == [([two, one], 0, True, "journey")]
    assert any("Flow ready" in message for message, _ in statuses)
    assert not hasattr(feature, "player")

    feature.deleteLater()
    app.processEvents()


def test_resolver_application_requests_semantic_queue_mutation(tmp_path):
    app, feature, _state, _statuses = _feature(tmp_path)
    replacements = []
    initial_sets = []
    feature.replaceQueueItemRequested.connect(
        lambda index, track, autoplay: replacements.append(
            (int(index), dict(track), bool(autoplay))
        )
    )
    feature.setQueueRequested.connect(
        lambda tracks,start,autoplay,intent:initial_sets.append(
            (list(tracks),int(start),bool(autoplay),str(intent))
        )
    )

    resolved = {**_track("Resolved", 7), "_resolution": {"mode": "preferred"}}

    feature.on_queue_changed([_track("Current", 1)], 0)
    feature._apply_resolver_match(resolved)
    assert replacements == [(0, resolved, True)]

    feature.on_queue_changed([], -1)
    feature._apply_resolver_match(resolved)
    assert initial_sets == [([resolved], 0, True, "manual_queue")]

    feature.deleteLater()
    app.processEvents()


def test_taste_actions_are_owned_and_optimistic(tmp_path):
    app, feature, state, _statuses = _feature(tmp_path)
    track = _track("Loved", 1)
    feature._playback_state.start_track(track, history_id=1, started_at=1.0)

    feature.record_feedback(True)
    assert feature.love_button.text() == "♥ Loved"
    assert feature.love_button.isEnabled() is False
    assert state.feedback == [(track, True)]

    feature._set_taste_action_state(loved=False, kept=False)
    feature.keep_current()
    assert feature.keep_button.text() == "✓ Kept"
    assert feature.keep_button.isEnabled() is False
    assert state.keeps == [track]

    feature.deleteLater()
    app.processEvents()


def test_more_and_less_like_actions_update_and_clear_local_taste(tmp_path):
    app, feature, state, statuses = _feature(tmp_path)
    track = dict(_track("Suggested", 9), genre="Ambient")
    feature.on_track_changed(track)

    action_names = [
        action.text()
        for action in feature.taste_button.menu().actions()
        if not action.isSeparator()
    ]
    feature.more_taste_action.trigger()
    feature.less_taste_action.trigger()
    feature.clear_taste_action.trigger()

    assert action_names == [
        "More like this",
        "Less like this",
        "Clear taste correction",
    ]
    assert feature.taste_button.isEnabled() is True
    assert state.taste_adjustments == [(track, "more"), (track, "less")]
    assert state.cleared_taste_adjustments == [track]
    assert statuses[-1][0] == "Taste correction cleared"

    feature.deleteLater()
    app.processEvents()


def test_position_completion_and_power_visibility_stay_inside_feature(tmp_path):
    app, feature, state, _statuses = _feature(tmp_path)
    feature._playback_state.start_track(_track("Completing", 2), history_id=42, started_at=1.0)

    feature.on_position(99_000, 100_000)
    feature.on_playing_changed(True)
    feature.set_power_tools_visible(True)

    assert state.completed == [42]
    assert feature.current_history_id() == 0
    assert feature.play_button.text() == ""
    assert feature.play_button.accessibleName() == "Pause"
    assert not feature.play_button.icon().isNull()
    assert feature.player_power_actions.isHidden() is False

    feature.deleteLater()
    app.processEvents()
