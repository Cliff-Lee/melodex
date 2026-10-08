from __future__ import annotations

from types import SimpleNamespace

import pytest


class FakeJourneyState:
    def __init__(self):
        self._recipes = []
        self._runs = []
        self._track_signals = []
        self.events = []

    def track_signals(self, _limit=5000):
        return [dict(row) for row in self._track_signals]

    def recent_tracks(self, _limit=20):
        return []

    def taste_corrections(self, _limit=5000):
        return []

    def sessions(self, _limit=1):
        return []

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


def _workspace(
    *,
    catalog=None,
    current=None,
    local_intel_service=None,
    knowledge_service=None,
):
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
        local_intelligence=lambda: local_intel_service or SimpleNamespace(),
        knowledge=lambda: knowledge_service or SimpleNamespace(),
        metadata=lambda: SimpleNamespace(),
        run_async=run_async,
        current_track=lambda: current_box["track"],
        page_titles={},
    )
    workspace.statusMessageRequested.connect(
        lambda message, timeout: statuses.append((message, timeout))
    )
    return app, workspace, state, statuses, current_box


def test_music_map_payload_uses_metadata_aware_library_rediscovery():
    from melodex.user_state import UserState

    favorite = {
        "provider_id": "local",
        "track_id": "favorite",
        "rel": "local:northbound/night-drive/1",
        "artist": "Northbound",
        "album_artist": "Northbound",
        "album": "Night Drive",
        "title": "Opening Light",
        "track_no": "1/8",
    }
    hidden_gem = {
        "provider_id": "local",
        "track_id": "hidden-gem",
        "rel": "local:northbound/night-drive/8",
        "artist": "Northbound",
        "album_artist": "Northbound",
        "album": "Night Drive",
        "title": "Last Signal",
        "track_no": "8/8",
    }
    catalog = [favorite, hidden_gem]
    analysis = {
        "bpm": 120,
        "energy": 0.5,
        "spectral_centroid": 1400,
        "onset_density": 0.1,
        "intro_mixability": 0.5,
        "outro_mixability": 0.5,
        "key_pc": 3,
        "key_mode": "minor",
        "key_confidence": 0.8,
    }
    profiles = [
        {
            "ref": f"t{index}",
            "title": track["title"],
            "artist": track["artist"],
            "album": track["album"],
            "analysis": dict(analysis),
            "taste": {},
        }
        for index, track in enumerate(catalog)
    ]
    local_intelligence = SimpleNamespace(
        build_snapshot=lambda *_args, **_kwargs: (
            profiles,
            [],
            {f"t{index}": dict(track) for index, track in enumerate(catalog)},
            len(profiles),
        )
    )
    knowledge = SimpleNamespace(snapshot=lambda _ref_map: {})
    app, workspace, state, _statuses, _current = _workspace(
        catalog=catalog,
        local_intel_service=local_intelligence,
        knowledge_service=knowledge,
    )
    state._track_signals = [
        {
            "track_key": UserState.track_key(favorite),
            "artist": "Northbound",
            "plays": 8,
            "completes": 7,
            "loves": 1,
        }
    ]

    payload = workspace._build_music_map_payload()
    nodes = {row["ref"]: row for row in payload["model"]["nodes"]}

    assert nodes["t1"]["rediscovery"] > 0.45
    assert nodes["t1"]["rediscovery_reason"] == "deep cut from an album you enjoyed"
    assert "listening history with Northbound" in nodes["t1"]["taste_reason"]
    workspace.deleteLater()
    app.processEvents()


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
    assert not workspace.music_map_power_panel.isHidden()
    assert not workspace.music_map_journey_panel.isHidden()
    assert workspace.music_map_planner_tabs.currentWidget() is workspace.music_map_journey_panel
    assert not workspace.music_path_steps.isHidden()

    assert len(workspace.music_journey_palette_buttons) == 8
    assert not hasattr(workspace, "music_journey_preset")
    assert not hasattr(workspace, "music_journey_constraint")

    workspace.deleteLater()
    app.processEvents()


def test_composer_preset_and_timeline_edits_keep_workspace_state_in_sync():
    app, workspace, _state, _statuses, _current = _workspace()
    workspace.build_music_map()

    workspace._music_journey_load_preset(["calm", "dark", "energetic"])
    assert [stage["constraint"] for stage in workspace.music_journey_stages_data] == [
        "calm",
        "dark",
        "energetic",
    ]

    workspace.music_active_recipe_id = "saved-recipe"
    workspace.music_journey_stages.move_stage(2, 0)
    assert [stage["constraint"] for stage in workspace.music_journey_stages_data] == [
        "energetic",
        "calm",
        "dark",
    ]
    assert workspace.music_active_recipe_id == ""

    workspace.music_journey_palette_buttons["bright"].click()
    assert workspace.music_journey_stages_data[-1]["constraint"] == "bright"
    assert workspace.music_journey_stages.ordered_stages() == workspace.music_journey_stages_data

    workspace.deleteLater()
    app.processEvents()


def test_dragged_tracks_set_composer_start_and_destination():
    app, workspace, _state, _statuses, _current = _workspace()
    workspace.build_music_map()
    workspace.music_map.ref_map = {
        "start-ref": {"artist": "First Artist", "title": "Opening"},
        "end-ref": {"artist": "Last Artist", "title": "Closer"},
    }

    workspace.music_map.selected_ref = "start-ref"
    workspace.music_journey_start_endpoint.click()
    assert workspace.music_path_start_ref == "start-ref"
    assert workspace._music_path_set_endpoint(
        "destination", {"type": "track", "ref": "end-ref"}
    )
    assert workspace.music_path_start_ref == "start-ref"
    assert workspace.music_path_end_ref == "end-ref"
    assert "First Artist — Opening" in workspace.music_journey_start_endpoint.text()
    assert "Last Artist — Closer" in workspace.music_journey_end_endpoint.text()
    assert workspace.music_map.route_start_ref == "start-ref"
    assert workspace.music_map.route_end_ref == "end-ref"
    assert not workspace._music_path_set_endpoint(
        "start", {"type": "track", "ref": "missing"}
    )

    workspace.deleteLater()
    app.processEvents()


def test_composer_endpoints_and_stages_share_one_horizontal_route_strip():
    app, workspace, _state, _statuses, _current = _workspace()
    workspace.build_music_map()
    workspace.music_map_power_scroll.show()
    workspace.music_map_planner_tabs.setCurrentWidget(workspace.music_map_journey_panel)
    page = workspace.pages["music_map"]
    page.resize(1400, 900)
    page.show()
    app.processEvents()

    start_y = workspace.music_journey_start_endpoint.mapTo(page, workspace.music_journey_start_endpoint.rect().topLeft()).y()
    stages_y = workspace.music_journey_stages.mapTo(page, workspace.music_journey_stages.rect().topLeft()).y()
    end_y = workspace.music_journey_end_endpoint.mapTo(page, workspace.music_journey_end_endpoint.rect().topLeft()).y()
    assert max(start_y, stages_y, end_y) - min(start_y, stages_y, end_y) <= 2
    assert workspace.music_journey_stages.width() > 500

    workspace.deleteLater()
    app.processEvents()


def test_composer_can_build_direct_route_with_no_stages(monkeypatch):
    from melodex import music_journey

    app, workspace, _state, statuses, _current = _workspace()
    workspace.build_music_map()
    workspace.music_path_start_ref = "start-ref"
    workspace.music_path_end_ref = "end-ref"
    calls = []

    def build(_model, _knowledge, start, end, stages, **kwargs):
        calls.append((start, end, stages, kwargs))
        return {
            "found": True,
            "journey": True,
            "path_refs": [start, end],
            "hops": [],
            "stages": [],
            "score": 0.8,
        }

    monkeypatch.setattr(music_journey, "build_music_journey", build)
    workspace._music_journey_build()

    assert calls and calls[0][0:3] == ("start-ref", "end-ref", [])
    assert workspace.music_path_result["journey"] is True
    assert any("0 stages" in message for message, _timeout in statuses)

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
