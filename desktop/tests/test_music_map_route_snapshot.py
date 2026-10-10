from __future__ import annotations

from copy import deepcopy

from melodex.music_map_route_snapshot import snapshot_pathfinder_inputs
from melodex.music_pathfinder import find_music_path


def _fixture():
    model = {
        "nodes": [
            {
                "ref": ref, "route_vector": [i / 4, 0.2, 0.4, 0.9],
                "x": i / 3, "y": -i / 3,
                "large_unused_metadata": {"analysis": ["unused"] * 120},
            }
            for i, ref in enumerate(("a", "b", "c", "d"))
        ],
        "edges": [
            {"a": "a", "b": "b", "similarity": 0.9, "unused": "stripped"},
            {"a": "b", "b": "c", "similarity": 0.81},
            {"a": "c", "b": "d", "similarity": 0.83},
            {"a": "a", "b": "missing", "similarity": 1.0},
        ],
        "big_ui_payload": ["irrelevant"] * 500,
    }
    knowledge = {
        "edges": [
            {
                "a": "a", "b": "d", "kind": "song_relation",
                "label": "Recorded as a version of", "strength": 0.93,
                "evidence": "local metadata",
                "details": {"note": ["preserved evidence"]},
            },
            {
                "a": "b", "b": "c", "kind": "artist",
                "label": "Shared performer", "strength": 0.51,
            },
            {"a": "a", "b": "gone", "kind": "artist", "label": "ignored"},
        ],
        "albums": [{"very_large": list(range(500))}],
    }
    return model, knowledge


def test_snapshot_preserves_routes_and_explanations_across_modes():
    model, knowledge = _fixture()
    trimmed_model, trimmed_knowledge = snapshot_pathfinder_inputs(model, knowledge)
    assert len(trimmed_model["nodes"]) == 4
    assert "big_ui_payload" not in trimmed_model
    assert "large_unused_metadata" not in trimmed_model["nodes"][0]
    assert len(trimmed_model["edges"]) == 3
    assert len(trimmed_knowledge["edges"]) == 2
    assert "albums" not in trimmed_knowledge

    for mode in ("balanced", "sonic", "knowledge"):
        for start, end in (("a", "d"), ("b", "c"), ("c", "a")):
            original = find_music_path(
                model, knowledge, start, end, mode=mode, max_hops=8
            )
            trimmed = find_music_path(
                trimmed_model, trimmed_knowledge,
                start, end, mode=mode, max_hops=8
            )
            assert trimmed == original


def test_snapshot_is_independent_of_later_catalogue_refreshes():
    model, knowledge = _fixture()
    copied_model, copied_knowledge = snapshot_pathfinder_inputs(model, knowledge)
    saved_model, saved_knowledge = deepcopy(copied_model), deepcopy(copied_knowledge)

    model["nodes"][0]["route_vector"][0] = 900
    model["edges"][0]["similarity"] = 0.0
    knowledge["edges"][0]["strength"] = 0.0
    knowledge["edges"][0]["details"]["note"].append("changed")
    model["nodes"].clear()
    knowledge["edges"].clear()

    assert copied_model == saved_model
    assert copied_knowledge == saved_knowledge


def test_empty_and_orphan_edges_produce_no_invented_tracks():
    model = {
        "nodes": [{"ref": "one", "x": 0, "y": 0}],
        "edges": [
            {"a": "one", "b": "two", "similarity": 1.0},
            {"a": "two", "b": "one", "similarity": 1.0},
        ],
    }
    new_model, new_knowledge = snapshot_pathfinder_inputs(
        model, {"edges": [{"a": "other", "b": "one", "kind": "album"}]}
    )
    assert len(new_model["nodes"]) == 1
    assert new_model["edges"] == []
    assert new_knowledge["edges"] == []
    assert not find_music_path(new_model, new_knowledge, "one", "other")["found"]
