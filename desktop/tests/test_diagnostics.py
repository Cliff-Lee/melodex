from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from melodex.diagnostics import build_diagnostics, write_diagnostics


class FakePluginConfig:
    def status(self, plugin_id, declarations):
        return {
            "declared": True,
            "configured": {"api_token": True},
            "ready": True,
            "missing_required": [],
            "secret_storage": "system-keyring",
        }


class FakeManager:
    def __init__(self):
        self.settings = {
            "jamendo_client_id": "jamendo-secret-value",
            "local_roots": ["/Users/example/Music"],
            "user_streams": [
                {"name": "Private radio", "url": "https://secret.example/stream"}
            ],
        }
        self.plugin_config = FakePluginConfig()
        self.providers = {
            "local": SimpleNamespace(
                info=SimpleNamespace(
                    id="local",
                    name="Local Files",
                    version="1",
                    capabilities=["search", "playback"],
                    permissions={},
                    configuration=[],
                ),
                last_scan_metrics={
                    "thread_name": "MainThread",
                    "main_thread": True,
                    "root_count": 1,
                    "directories_seen": 508,
                    "files_seen": 13208,
                    "audio_files_seen": 12700,
                    "metadata_attempts": 12700,
                    "metadata_seconds": 92.5,
                    "non_metadata_seconds": 11.0,
                    "total_seconds": 103.5,
                    "tracks_indexed": 12700,
                    "unchanged_files": 12690,
                    "added_files": 3,
                    "changed_files": 5,
                    "removed_files": 2,
                    "stat_failures": 0,
                    "metadata_reused": 12690,
                    "incomplete_roots": 1,
                    "private_path": "/Volumes/SecretNAS/Music",
                },
            ),
            "jamendo": SimpleNamespace(
                info=SimpleNamespace(
                    id="jamendo",
                    name="Jamendo",
                    version="1",
                    capabilities=["search", "playback"],
                    permissions={},
                    configuration=[],
                )
            ),
            "streams": SimpleNamespace(
                info=SimpleNamespace(
                    id="streams",
                    name="User Streams",
                    version="1",
                    capabilities=["playback"],
                    permissions={},
                    configuration=[],
                )
            ),
            "org.example.provider": SimpleNamespace(
                info=SimpleNamespace(
                    id="org.example.provider",
                    name="Example",
                    version="1.2.3",
                    capabilities=["search", "playback"],
                    permissions={"network_hosts": ["api.example.org"]},
                    configuration=[
                        {"key": "api_token", "label": "API token", "type": "secret"}
                    ],
                )
            ),
        }

    def provider_order(self):
        return ["local", "jamendo", "streams", "org.example.provider"]

    def local_catalog(self):
        return [{"title": "private local track"}]

    def user_streams(self):
        return [{"name": "Private radio", "url": "https://secret.example/stream"}]

    def local_index_summary(self):
        return {
            "root_count": 1,
            "ready_roots": 1,
            "track_count": 12700,
            "all_ready": True,
            "private_path": "/Volumes/SecretNAS/Music",
        }

    def installation_record(self, plugin_id):
        return {
            "id": plugin_id,
            "name": "Example",
            "version": "1.2.3",
            "kind": "provider",
            "installed_at": "2026-09-29T00:00:00+00:00",
            "method": "registry",
            "package_name": "example.mdxprovider",
            "package_size": 123,
            "package_sha256": "a" * 64,
            "registry_verified": True,
            "registry_status": "community",
            "publisher": "Example Publisher",
            "package_url": "https://should-not-appear.example/package",
            "registry_sha256": "a" * 64,
            "source_repository": "https://example.org/source",
        }

    def extensions(self):
        return [
            {
                "id": "org.example.extension",
                "name": "Example Extension",
                "version": "0.1.0",
                "capabilities": ["metadata"],
                "permissions": {"network_hosts": ["meta.example.org"]},
                "enabled": True,
                "preferred_for": ["metadata"],
                "health": {
                    "status": "error",
                    "calls": 2,
                    "successes": 1,
                    "failures": 1,
                    "consecutive_failures": 1,
                    "last_error": "call_error",
                    "process_running": False,
                },
                "configuration_status": {
                    "declared": True,
                    "configured": {"token": True},
                    "ready": True,
                    "missing_required": [],
                    "secret_storage": "system-keyring",
                },
            }
        ]


def test_diagnostics_excludes_secret_values_and_private_paths():
    payload = build_diagnostics(FakeManager())
    text = json.dumps(payload)
    assert "jamendo-secret-value" not in text
    assert "/Users/example/Music" not in text
    assert "https://secret.example/stream" not in text
    assert "private local track" not in text
    assert "https://should-not-appear.example/package" not in text
    assert "/Volumes/SecretNAS/Music" not in text
    assert payload["sources"][1]["configured"] is True
    assert payload["sources"][2]["stream_count"] == 1
    assert payload["sources"][3]["configuration_status"]["ready"] is True
    assert payload["extensions"][0]["health"]["last_error"] == "call_error"
    assert payload["performance"]["local_scan"]["tracks_indexed"] == 12700
    assert payload["performance"]["local_scan"]["metadata_reused"] == 12690
    assert payload["performance"]["local_scan"]["changed_files"] == 5
    assert payload["performance"]["local_scan"]["removed_files"] == 2
    assert payload["performance"]["local_scan"]["incomplete_roots"] == 1
    assert payload["performance"]["local_scan"]["main_thread"] is True
    assert payload["library_index"] == {
        "root_count": 1,
        "ready_roots": 1,
        "track_count": 12700,
        "all_ready": True,
    }


def test_diagnostics_filters_ui_performance_fields():
    payload = build_diagnostics(
        FakeManager(),
        ui_metrics={
            "library_catalog": {
                "thread_name": "MainThread",
                "main_thread": True,
                "track_count": 12700,
                "album_count": 954,
                "input_album_count": 954,
                "albums_truncated": 0,
                "tracks_truncated": 0,
                "album_limit": 4000,
                "artist_count": 612,
                "reset_seconds": 0.1,
                "copy_catalog_seconds": 0.02,
                "album_model_seconds": 0.3,
                "artist_model_seconds": 0.2,
                "initial_layout_seconds": 4.5,
                "artwork_request_seconds": 0.1,
                "total_seconds": 5.22,
                "private_path": "/Volumes/AnotherSecret/Music",
            },
            "library_filter": {
                "query_length": 12,
                "view": "albums",
                "visible_album_count": 1,
                "visible_artist_count": 1,
                "visible_track_count": 10,
                "album_filter_seconds": 0.004,
                "artist_filter_seconds": 0.006,
                "track_filter_sort_seconds": 0.081,
                "layout_seconds": 0.012,
                "total_seconds": 0.103,
                "query": "Private Album Name",
                "private_path": "/Volumes/AnotherSecret/Music",
            },
            "library_view": {
                "view": "tracks",
                "shell_seconds": 0.002,
                "filter_seconds": 0.095,
                "total_seconds": 0.101,
                "rendered_album_count": 120,
                "rendered_artist_count": 0,
                "rendered_track_count": 300,
                "private_path": "/Users/example/Music",
            },
            "track_virtualization": {
                "model_row_count": 12700,
                "window_start": 420,
                "window_stop": 441,
                "hydrated_row_count": 21,
                "created_rows": 7,
                "removed_rows": 7,
                "hydrate_seconds": 0.041,
                "private_track": "Secret Song",
                "private_path": "/Users/example/Music/Secret.flac",
            },
            "artwork_priority": {
                "kind": "albums",
                "tier": "visible",
                "scroll_value": 480,
                "direction": 1,
                "visible_candidates": 18,
                "near_candidates": 20,
                "distant_candidates": 82,
                "requested_now": 12,
                "requested_total": 24,
                "private_album": "Secret Album",
                "private_path": "/Users/example/Music/Secret.flac",
            },
            "album_wall_runtime": {
                "viewport_changes": 381,
                "visible_art_scans": 92,
                "visible_art_batches": 41,
                "visible_art_items_requested": 618,
                "artwork_apply_batches": 39,
                "artwork_items_applied": 602,
                "visible_art_scan_last_ms": 2.1,
                "visible_art_scan_max_ms": 19.7,
                "artwork_apply_last_ms": 8.4,
                "artwork_apply_max_ms": 87.2,
                "tile_count": 954,
                "art_requested_count": 618,
                "online_requested_count": 0,
                "private_album": "Secret Album",
                "private_path": "/Users/example/Music/Secret.flac",
            },
            "playback_runtime": {
                "ticks": 9012,
                "track_commits": 8,
                "seek_requests": 4,
                "manual_next": 2,
                "manual_previous": 1,
                "crossfade_started": 3,
                "crossfade_completed": 2,
                "crossfade_eof_commits": 1,
                "natural_ends": 4,
                "transition_aborts": 1,
                "queue_position_commits": 6,
                "transition_plan_requests": 7,
                "transition_plan_completed": 5,
                "transition_plan_stale": 1,
                "transition_plan_failures": 1,
                "transition_plan_submit_rejected": 0,
                "planned_transition_target": 4,
                "planned_transition_ms": 5200,
                "queue_length": 12,
                "queue_index": 3,
                "queue_index_valid": True,
                "active_deck": 1,
                "crossfading": False,
                "transition_ms": 5200,
                "transition_target_index": None,
                "transition_deck": None,
                "transition_state_valid": True,
                "playback_intent": "journey",
                "journey_transitions_enabled": True,
                "playing": True,
                "position_ms": 45678,
                "duration_ms": 231000,
                "seekable": True,
                "last_seek_requested_ms": 45000,
                "current_track": "Secret Song",
                "private_path": "/Users/example/Music/Secret.flac",
            },
            "background_scheduler": {
                "max_workers": 4,
                "reserved_foreground_slots": 1,
                "active_total": 3,
                "peak_active": 4,
                "submitted": 42,
                "completed": 37,
                "failed": 1,
                "cancelled_pending": 5,
                "async_invalidations": 7,
                "stale_results_dropped": 2,
                "pending_total": 2,
                "active_by_priority": {
                    "foreground": 0,
                    "visible": 1,
                    "prefetch": 1,
                    "background": 1,
                    "idle": 0,
                },
                "pending_by_priority": {
                    "foreground": 0,
                    "visible": 0,
                    "prefetch": 0,
                    "background": 1,
                    "idle": 1,
                },
                "private_task_name": "Secret Song",
            },
            "local_scan_session": {
                "status": "complete",
                "reason": "rescan",
                "phase": "complete",
                "running": False,
                "paused": False,
                "pending_rescan": False,
                "elapsed_seconds": 41.25,
                "files_seen": 13000,
                "audio_files_seen": 12700,
                "directories_seen": 612,
                "completed": 12700,
                "total": 12700,
                "unchanged": 12690,
                "resumed": 0,
                "added": 4,
                "changed": 6,
                "removed": 0,
                "stat_failures": 1,
                "storage_state": "unavailable",
                "root_count": 1,
                "roots_unavailable": 1,
                "roots_incomplete": 0,
                "io_retries": 2,
                "error_type": "",
                "current": "Private Artist",
                "private_path": "/Volumes/AnotherSecret/Music",
                "raw_error": "PermissionError: /Volumes/AnotherSecret/Music",
            },
            "responsiveness": {
                "interval_ms": 50,
                "long_task_threshold_ms": 50,
                "ci_threshold_ms": 250,
                "serious_threshold_ms": 500,
                "blocker_threshold_ms": 1000,
                "total_stalls": 2,
                "long_tasks": 1,
                "ci_violations": 1,
                "serious_stalls": 0,
                "release_blockers": 0,
                "max_delay_ms": 620.0,
                "recent_stalls": [
                    {
                        "recorded_at": "2026-10-02T00:00:00+00:00",
                        "severity": "ci_violation",
                        "delay_ms": 620.0,
                        "gap_ms": 670.0,
                        "action": "sources:selection",
                        "private_path": "/Users/example/Music",
                    }
                ],
                "private_path": "/Volumes/AnotherSecret/Music",
            },
        },
    )
    text = json.dumps(payload)
    metrics = payload["performance"]["library_catalog"]
    assert metrics["track_count"] == 12700
    assert metrics["initial_layout_seconds"] == 4.5
    assert metrics["input_album_count"] == 954
    assert metrics["albums_truncated"] == 0
    filter_metrics = payload["performance"]["library_filter"]
    assert filter_metrics["query_length"] == 12
    assert filter_metrics["track_filter_sort_seconds"] == 0.081
    view_metrics = payload["performance"]["library_view"]
    assert view_metrics["view"] == "tracks"
    assert view_metrics["rendered_track_count"] == 300
    virtual = payload["performance"]["track_virtualization"]
    assert virtual["model_row_count"] == 12700
    assert virtual["hydrated_row_count"] == 21
    assert virtual["hydrate_seconds"] == 0.041
    artwork = payload["performance"]["artwork_priority"]
    assert artwork["kind"] == "albums"
    assert artwork["requested_now"] == 12
    assert artwork["distant_candidates"] == 82
    wall_runtime = payload["performance"]["album_wall_runtime"]
    assert wall_runtime["viewport_changes"] == 381
    assert wall_runtime["artwork_apply_max_ms"] == 87.2
    assert wall_runtime["tile_count"] == 954
    playback = payload["performance"]["playback_runtime"]
    assert playback["ticks"] == 9012
    assert playback["seek_requests"] == 4
    assert playback["queue_index_valid"] is True
    assert playback["active_deck"] == 1
    assert playback["crossfade_eof_commits"] == 1
    assert playback["natural_ends"] == 4
    assert playback["transition_aborts"] == 1
    assert playback["queue_position_commits"] == 6
    assert playback["transition_plan_requests"] == 7
    assert playback["transition_plan_completed"] == 5
    assert playback["transition_plan_stale"] == 1
    assert playback["transition_plan_failures"] == 1
    assert playback["transition_plan_submit_rejected"] == 0
    assert playback["planned_transition_target"] == 4
    assert playback["planned_transition_ms"] == 5200
    assert playback["transition_state_valid"] is True
    assert playback["playback_intent"] == "journey"
    assert playback["journey_transitions_enabled"] is True
    assert playback["transition_target_index"] is None
    assert playback["transition_deck"] is None
    assert "current_track" not in playback
    scheduler = payload["performance"]["background_scheduler"]
    assert scheduler["max_workers"] == 4
    assert scheduler["reserved_foreground_slots"] == 1
    assert scheduler["cancelled_pending"] == 5
    assert scheduler["async_invalidations"] == 7
    assert scheduler["stale_results_dropped"] == 2
    assert scheduler["active_by_priority"]["background"] == 1
    assert scheduler["pending_by_priority"]["idle"] == 1
    scan_session = payload["performance"]["local_scan_session"]
    assert scan_session["status"] == "complete"
    assert scan_session["storage_state"] == "unavailable"
    assert scan_session["roots_unavailable"] == 1
    assert scan_session["io_retries"] == 2
    assert "current" not in scan_session
    assert "raw_error" not in scan_session
    responsiveness = payload["performance"]["ui_responsiveness"]
    assert responsiveness["total_stalls"] == 2
    assert responsiveness["max_delay_ms"] == 620.0
    assert responsiveness["recent_stalls"][0]["action"] == "sources:selection"
    assert "/Volumes/AnotherSecret/Music" not in text
    assert "/Users/example/Music" not in text
    assert "Private Album Name" not in text
    assert "Secret Song" not in text
    assert "Secret Album" not in text
    assert '"query"' not in text
    assert "private_track" not in text
    assert "private_album" not in text
    assert "private_task_name" not in text
    assert '"current_track"' not in text
    assert "private_path" not in text


def test_write_diagnostics_creates_json_file(tmp_path: Path):
    target = write_diagnostics(tmp_path / "diagnostics.json", FakeManager())
    assert target.is_file()
    payload = json.loads(target.read_text("utf-8"))
    assert payload["schema_version"] == "0.2"
    assert payload["sources"]
    assert payload["extensions"]
    assert isinstance(payload["system"]["packaged"], bool)
