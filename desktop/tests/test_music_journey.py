from __future__ import annotations

from melodex.music_journey import build_music_journey, stage_score


def _node(
    ref,
    vector,
    *,
    energy=0.5,
    mode="minor",
    taste=0.0,
    rediscovery=0.0,
    plays=0,
):
    return {
        "ref": ref,
        "title": ref,
        "artist": "Artist",
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


def test_stage_scores_are_interpretable():
    calm = _node("calm", [-1.4, -1.5, -0.2, -1.5, 0, 0, -0.5, 0.2], energy=0.10)
    energetic = _node("energetic", [1.5, 1.5, 0.3, 1.6, 0, 0, 0.3, 0.4], energy=0.95)
    dark = _node("dark", [0.0, -0.2, -2.0, -0.1, 0, 0, -1.5, 0.0], energy=0.36, mode="minor")
    bright = _node("bright", [0.3, 0.3, 2.0, 0.2, 0, 0, 1.5, 0.0], energy=0.60, mode="major")

    calm_score, _ = stage_score(calm, "calm")
    energetic_as_calm, _ = stage_score(energetic, "calm")
    energetic_score, _ = stage_score(energetic, "energetic")
    calm_as_energy, _ = stage_score(calm, "energetic")
    dark_score, _ = stage_score(dark, "dark")
    bright_as_dark, _ = stage_score(bright, "dark")

    assert calm_score > energetic_as_calm
    assert energetic_score > calm_as_energy
    assert dark_score > bright_as_dark


def test_forgotten_stage_uses_rediscovery_signal():
    old = _node("old", [0] * 8, taste=0.8, rediscovery=0.9, plays=8)
    recent = _node("recent", [0] * 8, taste=0.9, rediscovery=0.0, plays=20)
    old_score, reason = stage_score(old, "forgotten")
    recent_score, _ = stage_score(recent, "forgotten")
    assert old_score > recent_score
    assert "rediscovery" in reason


def test_journey_designer_builds_requested_semantic_arc():
    nodes = [
        _node("start", [-2.0, -2.0, 0.4, -2.0, 0, 0, 0.0, 0.0], energy=0.18),
        _node("calm", [-1.6, -1.7, 0.1, -1.7, 0, 0, -0.2, 0.0], energy=0.08),
        _node("dark", [-0.8, -0.7, -2.1, -0.6, 0, 0, -1.7, 0.0], energy=0.36, mode="minor"),
        _node("forgotten", [0.0, 0.0, -0.1, 0.0, 0, 0, -0.2, 0.0], energy=0.45, taste=0.85, rediscovery=0.95, plays=9),
        _node("energetic", [1.3, 1.5, 0.4, 1.6, 0, 0, 0.5, 0.2], energy=0.96, mode="major"),
        _node("end", [2.0, 2.0, 0.6, 2.0, 0, 0, 0.7, 0.3], energy=0.90, mode="major"),
    ]
    result = build_music_journey(
        _model(nodes),
        {"edges": []},
        "start",
        "end",
        ["calm", "dark", "forgotten", "energetic"],
        mode="balanced",
        max_hops_per_segment=8,
    )

    assert result["found"] is True
    assert result["path_refs"][0] == "start"
    assert result["path_refs"][-1] == "end"
    assert [stage["ref"] for stage in result["stages"]] == [
        "calm",
        "dark",
        "forgotten",
        "energetic",
    ]
    assert result["waypoint_refs"] == ["calm", "dark", "forgotten", "energetic"]
    assert all(stage["score"] >= 0.30 for stage in result["stages"])
    assert any(hop.get("journey_stage") == "Forgotten" for hop in result["hops"])


def test_journey_designer_honours_exact_track_waypoint():
    nodes = [
        _node("start", [-1.0] * 8, energy=0.2),
        _node("special", [0.0] * 8, energy=0.5),
        _node("end", [1.0] * 8, energy=0.8),
    ]
    result = build_music_journey(
        _model(nodes),
        {"edges": []},
        "start",
        "end",
        [{"type": "track", "ref": "special", "label": "My waypoint"}],
        mode="sonic",
    )
    assert result["found"] is True
    assert result["waypoint_refs"] == ["special"]
    assert result["stages"][0]["label"] == "My waypoint"
    assert "special" in result["path_refs"]


def test_journey_designer_fails_honestly_when_forgotten_stage_is_absent():
    nodes = [
        _node("start", [-1.0] * 8, energy=0.2),
        _node("middle", [0.0] * 8, energy=0.5, taste=0.9, rediscovery=0.0, plays=15),
        _node("end", [1.0] * 8, energy=0.8),
    ]
    result = build_music_journey(
        _model(nodes),
        {"edges": []},
        "start",
        "end",
        ["forgotten"],
        mode="balanced",
    )
    assert result["found"] is False
    assert result["failed_stage"]["constraint"] == "forgotten"
    assert "Could not find a routable Forgotten waypoint" in result["reason"]
