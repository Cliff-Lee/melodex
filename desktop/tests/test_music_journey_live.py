from __future__ import annotations

from melodex.music_journey_live import (
    live_steering_stage,
    remaining_journey_stages,
    replan_live_journey,
)


def _node(
    ref,
    vector,
    *,
    artist="Artist",
    energy=0.5,
    mode="minor",
    taste=0.0,
    rediscovery=0.0,
    plays=0,
):
    return {
        "ref": ref,
        "title": ref,
        "artist": artist,
        "album": "Album",
        "x": 0.0,
        "y": 0.0,
        "route_vector": list(vector),
        "energy": energy,
        "bpm": 120.0,
        "key_pc": 0,
        "key_mode": mode,
        "taste": taste,
        "rediscovery": rediscovery,
        "plays": plays,
    }


def _model(nodes):
    return {
        "nodes": list(nodes),
        "edges": [],
        "analysed": len(nodes),
        "input_profiles": len(nodes),
    }


def _active_route():
    return {
        "found": True,
        "journey": True,
        "path_refs": ["start", "calm", "dark", "forgotten", "energetic", "end"],
        "stages": [
            {"type": "constraint", "constraint": "calm", "label": "Calm", "ref": "calm"},
            {"type": "constraint", "constraint": "dark", "label": "Darker", "ref": "dark"},
            {
                "type": "constraint",
                "constraint": "forgotten",
                "label": "Forgotten",
                "ref": "forgotten",
            },
            {
                "type": "constraint",
                "constraint": "energetic",
                "label": "Energetic",
                "ref": "energetic",
            },
        ],
    }


def test_remaining_live_stages_drop_completed_waypoints():
    remaining = remaining_journey_stages(_active_route(), "dark")
    assert [stage["constraint"] for stage in remaining] == ["forgotten", "energetic"]


def test_live_steering_is_transparent_semantic_stage():
    stage = live_steering_stage("more_energy")
    assert stage is not None
    assert stage["constraint"] == "energetic"
    assert stage["label"] == "More energy next"
    assert stage["_live_steering"] is True


def test_live_replan_preserves_unsatisfied_stages_and_adds_steer():
    nodes = [
        _node("start", [-2.0] * 8, energy=0.15),
        _node("calm", [-1.5] * 8, energy=0.08),
        _node("dark", [-0.8, -0.8, -2.0, -0.5, 0, 0, -1.4, 0], energy=0.35),
        _node("boost", [-0.2, 1.2, 0.0, 1.1, 0, 0, 0, 0], energy=0.85),
        _node("forgotten", [0.2] * 8, energy=0.45, taste=0.85, rediscovery=0.95, plays=8),
        _node("energetic", [1.3] * 8, energy=0.95, mode="major"),
        _node("end", [2.0] * 8, energy=0.88, mode="major"),
    ]
    result = replan_live_journey(
        _model(nodes),
        {"edges": []},
        _active_route(),
        "dark",
        "end",
        mode="balanced",
        steering="more_energy",
    )

    assert result["found"] is True
    assert result["live"] is True
    assert [stage["constraint"] for stage in result["remaining_original_stages"]] == [
        "forgotten",
        "energetic",
    ]
    assert result["stages"][0]["label"] == "More energy next"
    assert "Live steer: More energy next" in result["reason"]


def test_live_replan_excludes_skipped_ref():
    nodes = [
        _node("current", [-1.0] * 8, energy=0.25),
        _node("skipped", [0.0] * 8, energy=0.50, taste=0.9, rediscovery=0.9, plays=9),
        _node("alternate", [0.1] * 8, energy=0.52, taste=0.85, rediscovery=0.88, plays=7),
        _node("end", [1.0] * 8, energy=0.80),
    ]
    active = {
        "found": True,
        "journey": True,
        "path_refs": ["current", "skipped", "end"],
        "stages": [
            {
                "type": "constraint",
                "constraint": "forgotten",
                "label": "Forgotten",
                "ref": "skipped",
            }
        ],
    }
    result = replan_live_journey(
        _model(nodes),
        {"edges": []},
        active,
        "current",
        "end",
        avoid_refs={"skipped"},
    )

    assert result["found"] is True
    assert "skipped" not in result["path_refs"]
    assert result["stages"][0]["ref"] == "alternate"
    assert "skipped" in result["forbidden_refs"]


def test_live_replan_avoid_artist_excludes_artist_from_route():
    nodes = [
        _node("current", [-1.0] * 8, artist="Keep", energy=0.25),
        _node("bad1", [-0.4] * 8, artist="Avoid Me", energy=0.42),
        _node("bad2", [0.0] * 8, artist="Avoid Me", energy=0.55),
        _node("good", [0.25] * 8, artist="Other", energy=0.62),
        _node("end", [1.0] * 8, artist="Destination", energy=0.82),
    ]
    active = {
        "found": True,
        "journey": True,
        "path_refs": ["current", "bad1", "bad2", "end"],
        "stages": [],
    }
    result = replan_live_journey(
        _model(nodes),
        {"edges": []},
        active,
        "current",
        "end",
        mode="sonic",
        avoid_artists={"Avoid Me"},
    )

    assert result["found"] is True
    assert result["path_refs"][0] == "current"
    assert result["path_refs"][-1] == "end"
    assert "bad1" not in result["path_refs"]
    assert "bad2" not in result["path_refs"]
    assert result["avoided_artists"] == ["Avoid Me"]


def test_live_replan_keeps_destination_even_if_artist_is_avoided():
    nodes = [
        _node("current", [-0.5] * 8, artist="Other"),
        _node("bridge", [0.0] * 8, artist="Other"),
        _node("end", [0.5] * 8, artist="Avoid Me"),
    ]
    result = replan_live_journey(
        _model(nodes),
        {"edges": []},
        {"found": True, "journey": True, "path_refs": ["current", "end"], "stages": []},
        "current",
        "end",
        mode="sonic",
        avoid_artists={"Avoid Me"},
    )
    assert result["found"] is True
    assert result["path_refs"][-1] == "end"


def test_quickly_skipped_stage_is_reopened_with_alternative_waypoint():
    nodes = [
        _node("current", [-0.5] * 8, energy=0.35),
        _node("skipped", [0.0] * 8, taste=0.9, rediscovery=0.95, plays=10),
        _node("alternate", [0.1] * 8, taste=0.82, rediscovery=0.88, plays=7),
        _node("end", [0.7] * 8, energy=0.75),
    ]
    active = {
        "found": True,
        "journey": True,
        "path_refs": ["current", "skipped", "end"],
        "stages": [
            {
                "type": "constraint",
                "constraint": "forgotten",
                "label": "Forgotten",
                "ref": "skipped",
            }
        ],
    }
    # Replanning begins after playback has already advanced beyond the skipped
    # waypoint. reopen_stage_refs keeps the semantic intent alive.
    result = replan_live_journey(
        _model(nodes),
        {"edges": []},
        active,
        "end",
        "end",
        avoid_refs={"skipped"},
        reopen_stage_refs={"skipped"},
    )
    # At the fixed destination no further route can be built; use an earlier
    # current point to verify alternative selection.
    result = replan_live_journey(
        _model(nodes),
        {"edges": []},
        active,
        "current",
        "end",
        avoid_refs={"skipped"},
        reopen_stage_refs={"skipped"},
    )
    assert result["found"] is True
    assert result["stages"][0]["constraint"] == "forgotten"
    assert result["stages"][0]["ref"] == "alternate"
    assert "skipped" not in result["path_refs"]
