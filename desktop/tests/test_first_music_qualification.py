from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "desktop" / "tools" / "check_first_music_qualification.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("first_music_qualification", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_qualification_uses_latest_matching_local_source_and_play():
    qualify = _load_module().qualify
    result = qualify(
        {
            "performance": {
                "first_music": {
                    "audio_output_measurement": "first playback-position advance; not hardware loopback",
                    "journeys": {
                        "process_to_shell_ms": 300,
                        "sources": [
                            {
                                "source_id": 4,
                                "source_selected_to_first_track_visible_ms": 420,
                                "source_selected_to_first_playable_track_ms": 800,
                            }
                        ],
                    "plays": [
                        {"play_id": 7, "play_requested_to_audio_output_ms": 350}
                    ],
                },
                "events": [
                    {"event": "play_requested", "play_id": 7, "source_id": 4}
                ],
            }
            }
        },
        "local",
        source_id=4,
        play_id=7,
    )

    assert result["passed"] is True
    assert result["measurements_ms"]["play_requested_to_audio_output_ms"] == 350


def test_qualification_fails_missing_or_over_limit_measurements():
    qualify = _load_module().qualify
    result = qualify(
        {
            "performance": {
                "first_music": {
                    "journeys": {
                        "process_to_shell_ms": 1200,
                        "sources": [
                            {
                                "source_id": 2,
                                "source_selected_to_first_directory_ms": 1200,
                                "source_selected_to_first_track_visible_ms": 2300,
                                "source_selected_to_first_playable_track_ms": 3400,
                            }
                        ],
                        "plays": [
                            {"play_id": 3, "play_requested_to_audio_output_ms": None}
                        ],
                    },
                }
            }
        },
        "nas",
        source_id=2,
        play_id=3,
    )

    assert result["passed"] is False
    assert len(result["violations"]) == 5
    assert any("missing measurement" in item for item in result["violations"])


def test_warm_qualification_requires_cached_library_event():
    qualify = _load_module().qualify
    result = qualify(
        {"performance": {"first_music": {"journeys": {"process_to_shell_ms": 300}}}},
        "warm",
    )

    assert result["passed"] is False
    assert result["violations"] == [
        "missing measurement: process_to_cached_library_ms"
    ]


def test_latest_play_is_joined_to_the_selected_source_attempt():
    qualify = _load_module().qualify
    payload = {
        "performance": {
            "first_music": {
                "journeys": {
                    "process_to_shell_ms": 300,
                    "sources": [
                        {
                            "source_id": 1,
                            "source_selected_to_first_track_visible_ms": 300,
                            "source_selected_to_first_playable_track_ms": 600,
                        },
                        {
                            "source_id": 2,
                            "source_selected_to_first_track_visible_ms": 400,
                            "source_selected_to_first_playable_track_ms": 700,
                        },
                    ],
                    "plays": [
                        {"play_id": 10, "play_requested_to_audio_output_ms": 200},
                        {"play_id": 11, "play_requested_to_audio_output_ms": 490},
                    ],
                },
                "events": [
                    {"event": "play_requested", "play_id": 10, "source_id": 1},
                    {"event": "play_requested", "play_id": 11, "source_id": 2},
                ],
            }
        }
    }

    result = qualify(payload, "local")
    assert result["source_id"] == 2
    assert result["play_id"] == 11
    assert result["measurements_ms"]["source_selected_to_first_track_visible_ms"] == 400
    assert result["measurements_ms"]["play_requested_to_audio_output_ms"] == 490

    first_source = qualify(payload, "local", source_id=1)
    assert first_source["play_id"] == 10
    assert first_source["measurements_ms"]["play_requested_to_audio_output_ms"] == 200

    by_play = qualify(payload, "local", play_id=11)
    assert by_play["source_id"] == 2
    assert by_play["measurements_ms"]["source_selected_to_first_track_visible_ms"] == 400

    mismatched = qualify(payload, "local", source_id=1, play_id=11)
    assert mismatched["play_id"] is None
    assert "missing measurement: play_requested_to_audio_output_ms" in mismatched[
        "violations"
    ]
