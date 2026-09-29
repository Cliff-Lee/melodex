from __future__ import annotations

from pathlib import Path

import pytest

from melodex.journey_recipe import (
    load_journey_recipe,
    make_journey_recipe,
    materialize_recipe_stages,
    save_journey_recipe,
)


def test_recipe_track_waypoint_is_share_safe(tmp_path: Path):
    ref_map = {
        "t0": {
            "artist": "Artist",
            "title": "Song",
            "album": "Album",
            "local_path": "/private/music/song.flac",
            "provider_id": "local",
            "track_id": "/private/music/song.flac",
            "musicbrainz_recording_id": "mbid-1",
        }
    }
    recipe = make_journey_recipe(
        name="Arc",
        mode="balanced",
        stages=[
            {"type": "constraint", "constraint": "calm", "label": "Calm"},
            {"type": "track", "ref": "t0", "label": "Exact song"},
        ],
        ref_map=ref_map,
    )
    track = recipe["stages"][1]
    assert track["selector"]["musicbrainz_recording_id"] == "mbid-1"
    assert track["selector"]["artist"] == "Artist"
    assert "local_path" not in track["selector"]
    assert "provider_id" not in track["selector"]
    assert "track_id" not in track["selector"]

    path = save_journey_recipe(tmp_path / "arc", recipe)
    assert path.suffix == ".mdxjourney"
    text = path.read_text("utf-8")
    assert "/private/music" not in text
    loaded = load_journey_recipe(path)
    assert loaded == recipe


def test_recipe_materializes_track_waypoint_by_musicbrainz_id():
    recipe = {
        "melodex_journey": 1,
        "name": "Recipe",
        "description": "",
        "routing_mode": "balanced",
        "stages": [
            {
                "type": "track",
                "label": "Waypoint",
                "selector": {
                    "musicbrainz_recording_id": "recording-1",
                    "artist": "Old Artist",
                    "title": "Old Title",
                },
            }
        ],
    }
    ref_map = {
        "new-ref": {
            "artist": "Renamed Artist",
            "title": "Renamed Title",
            "album": "Album",
            "musicbrainz_recording_id": "recording-1",
        }
    }
    result = materialize_recipe_stages(recipe, ref_map)
    assert result["unresolved"] == []
    assert result["stages"][0]["ref"] == "new-ref"


def test_recipe_reports_unresolved_exact_waypoint():
    recipe = make_journey_recipe(
        name="Missing",
        stages=[
            {
                "type": "track",
                "selector": {"artist": "A", "title": "Missing"},
                "label": "Missing",
            }
        ],
    )
    result = materialize_recipe_stages(recipe, {})
    assert result["stages"] == []
    assert result["unresolved"][0]["label"] == "Missing"


def test_recipe_rejects_unknown_semantic_constraint():
    with pytest.raises(ValueError, match="Unsupported journey constraint"):
        make_journey_recipe(
            name="Bad",
            stages=[{"type": "constraint", "constraint": "mysterious"}],
        )
