from __future__ import annotations

from types import SimpleNamespace

import pytest


class FakeJourneyState:
    def __init__(self):
        self._recipes = []
        self._runs = []
        self.events = []

    def journey_recipes(self):
        return list(self._recipes)

    def journey_runs(self, _limit=80):
        return list(self._runs)

    def journey_events(self, _run_id):
        return []

    def save_journey_recipe(self, recipe_id, name, description, payload):
        self._recipes.append(
            {
                "id": recipe_id,
                "name": name,
                "description": description,
                "payload": dict(payload),
            }
        )

    def delete_journey_recipe(self, recipe_id):
        self._recipes = [
            row for row in self._recipes if str(row.get("id") or "") != recipe_id
        ]

    def start_journey_run(self, *args, **kwargs):
        return None

    def add_journey_event(self, run_id, event_type, payload):
        self.events.append((run_id, event_type, dict(payload or {})))

    def finish_journey_run(self, *args, **kwargs):
        return None


class FakeProviders:
    def __init__(self, catalog=None):
        self._catalog = list(catalog or [])
        self.capabilities = None

    def local_catalog(self):
        return [dict(track) for track in self._catalog]


def _workspace(*, catalog=None, current=None):
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.journey_workspace import JourneyWorkspace
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    state = FakeJourneyState()
    providers = FakeProviders(catalog)
    statuses = []
    current_box = {"track": dict(current or {}) if current else None}

    def run_async(work, done=None, failed=None, **_kwargs):
        try:
            result = work()
        except Exception as exc:
            if failed is not None:
                failed(str(exc))
            return
        if done is not None:
            done(result)

    workspace = JourneyWorkspace(
        providers,
        state,
        SimpleNamespace(analysis_available=True),
        local_intelligence=lambda: SimpleNamespace(),
        knowledge=lambda: SimpleNamespace(),
        metadata=lambda: SimpleNamespace(),
        run_async=run_async,
        current_track=lambda: current_box["track"],
        page_titles={},
    )
    workspace.statusMessageRequested.connect(
        lambda message, timeout: statuses.append((message, timeout))
    )
    return app, workspace, state, statuses, current_box


def test_journey_workspace_owns_default_state_and_lazy_music_map():
    app, workspace, _state, _statuses, _current = _workspace()

    assert workspace.music_map_built is False
    assert workspace.music_path_start_ref == ""
    assert workspace.music_path_end_ref == ""
    assert workspace.music_path_result == {}
    assert workspace.music_journey_stages_data == []
    assert workspace.music_live_active is False
    assert workspace.pending_journey_recipe is None
    assert workspace.pending_journey_replay is None
    assert workspace.pages["journeys"] is workspace.archive.page
    assert "journeys" in workspace.page_titles

    workspace.build_music_map()
    app.processEvents()

    assert workspace.music_map_built is True
    assert hasattr(workspace, "music_map")
    assert hasattr(workspace, "music_path_mode")
    assert hasattr(workspace, "music_live_label")
    assert "music_map" in workspace.page_titles

    workspace.deleteLater()
    app.processEvents()



def test_journey_designer_preserves_lazy_map_build():
    app, workspace, _state, _statuses, _current = _workspace()

    pages = []
    workspace.navigationRequested.connect(pages.append)

    workspace.open_designer()

    assert pages == ["music_map"]
    assert workspace.music_map_built is False
    assert workspace._designer_open_pending is True

    workspace.build_music_map()
    app.processEvents()

    assert workspace.music_map_built is True
    assert workspace._designer_open_pending is False
    assert workspace.music_map_power_panel.isVisible()
    assert workspace.music_map_journey_panel.isVisible()
    assert workspace.music_path_steps.isVisible()

    workspace.deleteLater()
    app.processEvents()

def test_journey_workspace_requests_playback_semantically(monkeypatch):
    app, workspace, _state, _statuses, _current = _workspace()
    workspace.build_music_map()

    played = []
    queued = []
    sessions = []
    workspace.playTracksRequested.connect(lambda tracks: played.append(list(tracks)))
    workspace.queueTracksRequested.connect(lambda tracks: queued.append(list(tracks)))
    workspace.sessionFromTrackRequested.connect(lambda track: sessions.append(dict(track)))

    track = {"title": "Mapped", "artist": "Example", "provider_id": "local"}
    workspace._play_music_map_track(track)
    monkeypatch.setattr(workspace, "_music_map_selected", lambda: dict(track))
    workspace._queue_music_map_selected()
    workspace._journey_from_music_map()

    assert played == [[track]]
    assert queued == [[track]]
    assert sessions == [track]
    assert not hasattr(workspace, "player")

    workspace.deleteLater()
    app.processEvents()


def test_journey_live_track_change_and_manual_skip_stay_inside_workspace(monkeypatch):
    app, workspace, _state, _statuses, current_box = _workspace(
        current={"title": "Current", "artist": "Artist"}
    )
    workspace.music_live_active = True
    workspace.music_live_destination_ref = "destination"

    stopped = []
    replans = []
    events = []
    monkeypatch.setattr(
        workspace,
        "_music_ref_for_track",
        lambda track: "destination" if track.get("title") == "Destination" else "previous",
    )
    monkeypatch.setattr(
        workspace,
        "_journey_live_stop",
        lambda message="inactive": stopped.append(message),
    )
    monkeypatch.setattr(
        workspace,
        "_journey_live_event",
        lambda event_type, payload: events.append((event_type, dict(payload or {}))),
    )
    monkeypatch.setattr(
        workspace,
        "_journey_live_replan",
        lambda steering="", **kwargs: replans.append((steering, dict(kwargs))),
    )

    workspace.on_track_changed({"title": "Destination", "artist": "Artist"})
    assert stopped == ["destination reached"]

    workspace.music_live_active = True
    workspace.on_manual_advance(
        {"title": "Previous", "artist": "Artist"},
        {"title": "Next", "artist": "Artist"},
        10_000,
        180_000,
    )

    assert "previous" in workspace.music_live_avoid_refs
    assert events[-1][0] == "manual_skip"
    assert replans[-1][1]["reason"] == "manual skip"
    assert replans[-1][1]["reopen_stage_refs"] == {"previous"}

    current_box["track"] = {"title": "Next", "artist": "Artist"}
    workspace.deleteLater()
    app.processEvents()


def test_journey_archive_requests_recipe_and_replay_through_workspace():
    app, workspace, _state, statuses, _current = _workspace()

    pages = []
    workspace.navigationRequested.connect(pages.append)

    pending = {
        "id": "recipe-1",
        "payload": {
            "name": "Test Journey",
            "routing_mode": "balanced",
            "stages": [{"type": "constraint", "key": "calm"}],
        },
    }
    workspace._queue_recipe_load(pending)

    assert workspace.pending_journey_recipe == pending
    assert pages[-1] == "music_map"
    assert "Refreshing Music Map" in statuses[-1][0]

    snapshot = {"tracks": [{"title": "One"}, {"title": "Two"}]}
    workspace._queue_replay(snapshot, "Final journey replay")

    assert workspace.pending_journey_replay == (snapshot, "Final journey replay")
    assert pages[-1] == "music_map"

    workspace._archive_recipe_activated("recipe-1", pending["payload"])
    assert workspace.music_active_recipe_id == "recipe-1"
    assert workspace.music_active_recipe["name"] == "Test Journey"

    workspace._archive_recipe_deleted("recipe-1")
    assert workspace.music_active_recipe_id == ""
    assert workspace.music_active_recipe == {}

    workspace.deleteLater()
    app.processEvents()


def test_journey_workspace_empty_library_refresh_is_nonblocking_and_explicit():
    app, workspace, _state, statuses, _current = _workspace(catalog=[])
    workspace.build_music_map()

    workspace.refresh_music_map()
    app.processEvents()

    assert any("Add local music to build a Music Map" in message for message, _ in statuses)
    assert workspace.music_path_result == {}

    workspace.deleteLater()
    app.processEvents()


def test_journey_workspace_shutdown_stops_active_live_journey(monkeypatch):
    app, workspace, _state, _statuses, _current = _workspace()
    workspace.music_live_active = True
    stopped = []
    monkeypatch.setattr(
        workspace,
        "_journey_live_stop",
        lambda message="inactive": stopped.append(message),
    )

    workspace.shutdown()

    assert stopped == ["application closed"]

    workspace.deleteLater()
    app.processEvents()
