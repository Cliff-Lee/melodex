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


def test_track_change_updates_owned_state_and_emits_snapshot(tmp_path):
    app, feature, state, _statuses = _feature(tmp_path)
    changed = []
    feature.currentTrackChanged.connect(lambda track: changed.append(dict(track)))

    track = _track("Current", 1)
    feature.on_track_changed(track)
    app.processEvents()

    assert feature.current_track() == track
    assert state.plays == [track]
    assert changed == [track]
    assert feature.now_title.text() == "Current"
    assert "Artist" in feature.now_meta.text()
    assert feature.current_position_ms() == 0

    feature.merge_current_track({"title": "Corrected"})
    assert feature.current_track()["title"] == "Corrected"
    assert feature.now_title.text() == "Corrected"

    feature.deleteLater()
    app.processEvents()


def test_flow_refinement_requests_new_queue_without_player_access(tmp_path):
    app, feature, _state, statuses = _feature(tmp_path)
    requested = []
    feature.setQueueRequested.connect(
        lambda tracks, start, autoplay: requested.append(
            (list(tracks), int(start), bool(autoplay))
        )
    )

    one = _track("One", 1)
    two = _track("Two", 2)
    feature.on_queue_changed([one, two], 0)
    feature.refine_queue()

    assert requested == [([two, one], 0, True)]
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
        lambda tracks, start, autoplay: initial_sets.append(
            (list(tracks), int(start), bool(autoplay))
        )
    )

    resolved = {**_track("Resolved", 7), "_resolution": {"mode": "preferred"}}

    feature.on_queue_changed([_track("Current", 1)], 0)
    feature._apply_resolver_match(resolved)
    assert replacements == [(0, resolved, True)]

    feature.on_queue_changed([], -1)
    feature._apply_resolver_match(resolved)
    assert initial_sets == [([resolved], 0, True)]

    feature.deleteLater()
    app.processEvents()


def test_taste_actions_are_owned_and_optimistic(tmp_path):
    app, feature, state, _statuses = _feature(tmp_path)
    track = _track("Loved", 1)
    feature._current_track = dict(track)

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


def test_position_completion_and_power_visibility_stay_inside_feature(tmp_path):
    app, feature, state, _statuses = _feature(tmp_path)
    feature._current_history_id = 42

    feature.on_position(99_000, 100_000)
    feature.on_playing_changed(True)
    feature.set_power_tools_visible(True)

    assert state.completed == [42]
    assert feature.current_history_id() == 0
    assert feature.play_button.text() == "❚❚"
    assert feature.player_power_actions.isHidden() is False

    feature.deleteLater()
    app.processEvents()
