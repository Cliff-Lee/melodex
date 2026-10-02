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
            "background_scheduler": {
                "max_workers": 4,
                "foreground_reserve": 1,
                "active_total": 3,
                "active_by_lane": {"disk": 1, "network": 2},
                "active_by_priority": {"visible": 1, "background": 2},
                "pending_total": 5,
                "pending_by_priority": {
                    "foreground": 1,
                    "prefetch": 2,
                    "idle": 2,
                },
                "pending_by_lane": {
                    "default": 1,
                    "prefetch": 2,
                    "idle": 2,
                },
                "lane_limits": {
                    "default": 4,
                    "disk": 2,
                    "network": 2,
                    "analysis": 1,
                    "prefetch": 1,
                    "idle": 1,
                },
                "submitted": 42,
                "completed": 34,
                "cancelled": 0,
                "queue_high_water": 8,
                "max_active_observed": 4,
                "private_label": "Secret Album",
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
    scheduler = payload["performance"]["background_scheduler"]
    assert scheduler["max_workers"] == 4
    assert scheduler["foreground_reserve"] == 1
    assert scheduler["active_total"] == 3
    assert scheduler["pending_total"] == 5
    assert scheduler["active_by_lane"]["network"] == 2
    assert scheduler["active_by_priority"]["background"] == 2
    assert scheduler["pending_by_priority"]["prefetch"] == 2
    assert scheduler["queue_high_water"] == 8
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
    assert "private_label" not in text
    assert "private_path" not in text


def test_write_diagnostics_creates_json_file(tmp_path: Path):
    target = write_diagnostics(tmp_path / "diagnostics.json", FakeManager())
    assert target.is_file()
    payload = json.loads(target.read_text("utf-8"))
    assert payload["schema_version"] == "0.1"
    assert payload["sources"]
    assert payload["extensions"]
