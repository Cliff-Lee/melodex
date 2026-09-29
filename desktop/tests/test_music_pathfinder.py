from __future__ import annotations

from melodex.music_pathfinder import find_music_path


def _node(ref: str, vector: list[float], x: float = 0.0, y: float = 0.0):
    return {
        "ref": ref,
        "title": ref,
        "artist": "Artist",
        "album": "Album",
        "x": x,
        "y": y,
        "route_vector": vector,
        "energy": 0.5,
        "bpm": 120.0,
        "taste": 0.0,
        "rediscovery": 0.0,
    }


def _model(nodes, edges=None):
    return {
        "nodes": list(nodes),
        "edges": list(edges or []),
        "analysed": len(nodes),
        "input_profiles": len(nodes),
    }


def test_pathfinder_sonic_mode_uses_intermediate_tracks_for_distant_regions():
    nodes = [
        _node(chr(ord("a") + i), [i * 0.55, 0.0])
        for i in range(9)
    ]
    model = _model(nodes)
    result = find_music_path(
        model,
        {"edges": []},
        "a",
        "i",
        mode="sonic",
        max_hops=8,
    )

    assert result["found"] is True
    assert result["path_refs"][0] == "a"
    assert result["path_refs"][-1] == "i"
    assert len(result["path_refs"]) > 2
    assert result["used_sonic_hops"] == len(result["hops"])
    assert result["used_knowledge_hops"] == 0
    assert all("Flow similarity" in hop["reason"] for hop in result["hops"])


def test_pathfinder_balanced_prefers_direct_documented_song_relationship():
    model = _model(
        [
            _node("a", [0.0, 0.0]),
            _node("b", [0.25, 0.0]),
            _node("c", [1.8, 0.0]),
        ]
    )
    knowledge = {
        "edges": [
            {
                "a": "a",
                "b": "c",
                "kind": "song_relation",
                "label": "samples",
                "strength": 1.0,
                "evidence": "context: Song Connections",
            }
        ]
    }

    result = find_music_path(
        model,
        knowledge,
        "a",
        "c",
        mode="balanced",
    )

    assert result["found"] is True
    assert result["path_refs"] == ["a", "c"]
    assert result["used_knowledge_hops"] == 1
    assert "samples" in result["hops"][0]["reason"]
    assert "song_relation" in result["hops"][0]["knowledge_kinds"]


def test_pathfinder_knowledge_first_prefers_factual_chain_over_sonic_shortcut():
    model = _model(
        [
            _node("a", [0.0, 0.0]),
            _node("b", [1.0, 0.0]),
            _node("c", [0.20, 0.0]),
        ]
    )
    knowledge = {
        "edges": [
            {
                "a": "a",
                "b": "b",
                "kind": "production",
                "label": "Producer P · producer",
                "strength": 0.95,
                "evidence": "MusicBrainz recording credits",
            },
            {
                "a": "b",
                "b": "c",
                "kind": "work",
                "label": "Shared Work",
                "strength": 0.95,
                "evidence": "MusicBrainz work relationship",
            },
        ]
    }

    result = find_music_path(
        model,
        knowledge,
        "a",
        "c",
        mode="knowledge",
        max_hops=6,
    )

    assert result["found"] is True
    assert result["path_refs"] == ["a", "b", "c"]
    assert result["used_knowledge_hops"] == 2
    assert "Producer P" in result["hops"][0]["reason"]
    assert "shared work" in result["hops"][1]["reason"].casefold()


def test_pathfinder_knowledge_first_can_use_explicit_sonic_bridge():
    model = _model(
        [
            _node("a", [0.0, 0.0]),
            _node("b", [0.10, 0.0]),
        ]
    )
    result = find_music_path(
        model,
        {"edges": []},
        "a",
        "b",
        mode="knowledge",
    )

    assert result["found"] is True
    assert result["path_refs"] == ["a", "b"]
    assert "sonic bridge" in result["hops"][0]["reason"]
    assert result["used_knowledge_hops"] == 0


def test_pathfinder_rejects_missing_endpoints():
    model = _model([_node("a", [0.0, 0.0])])
    result = find_music_path(model, {"edges": []}, "a", "missing")
    assert result["found"] is False
    assert result["path_refs"] == []
    assert "visible mapped tracks" in result["reason"]


def test_pathfinder_same_start_and_destination_is_zero_hop_route():
    model = _model([_node("a", [0.0, 0.0])])
    result = find_music_path(model, {"edges": []}, "a", "a")
    assert result["found"] is True
    assert result["path_refs"] == ["a"]
    assert result["hops"] == []
    assert result["score"] == 1.0
