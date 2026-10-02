from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_verifier():
    path = Path(__file__).resolve().parents[1] / "tools" / "verify_large_library_readiness.py"
    spec = importlib.util.spec_from_file_location("verify_large_library_readiness", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_large_library_acceptance_passes_expected_invariants(monkeypatch):
    verifier = _load_verifier()

    payloads = {
        "profile_library_scan.py": {"tracks_indexed": 12700, "total_seconds": 2.0},
        "profile_library_index.py": {
            "tracks_loaded": 12700,
            "ready": True,
            "write_seconds": 0.4,
            "read_seconds": 0.2,
        },
        "profile_incremental_rescan.py": {
            "first_scan_seconds": 2.0,
            "unchanged_rescan_seconds": 0.5,
            "rescan_metadata_reads": 0,
            "metadata_reused": 12700,
            "index_rows_rewritten": 0,
        },
        "profile_library_catalog.py": {
            "track_count": 12700,
            "album_widgets": 120,
            "track_widgets": 300,
            "total_seconds": 0.8,
            "initial_with_events_seconds": 1.0,
        },
    }
    monkeypatch.setattr(
        verifier,
        "_run_json",
        lambda script, *args: payloads[script],
    )

    result = verifier.evaluate(12700)

    assert result["ok"] is True
    assert all(row["ok"] for row in result["checks"])


def test_large_library_acceptance_fails_if_unchanged_rescan_rereads_tags(monkeypatch):
    verifier = _load_verifier()

    payloads = {
        "profile_library_scan.py": {"tracks_indexed": 12700},
        "profile_library_index.py": {"tracks_loaded": 12700, "ready": True},
        "profile_incremental_rescan.py": {
            "rescan_metadata_reads": 17,
            "metadata_reused": 12683,
            "index_rows_rewritten": 17,
        },
        "profile_library_catalog.py": {
            "track_count": 12700,
            "album_widgets": 120,
            "track_widgets": 300,
        },
    }
    monkeypatch.setattr(
        verifier,
        "_run_json",
        lambda script, *args: payloads[script],
    )

    result = verifier.evaluate(12700)

    assert result["ok"] is False
    failed = {row["name"] for row in result["checks"] if not row["ok"]}
    assert "unchanged rescan performs zero metadata reads" in failed
    assert "unchanged rescan rewrites zero index rows" in failed


def test_large_library_acceptance_fails_if_ui_widget_window_regresses(monkeypatch):
    verifier = _load_verifier()

    payloads = {
        "profile_library_scan.py": {"tracks_indexed": 12700},
        "profile_library_index.py": {"tracks_loaded": 12700, "ready": True},
        "profile_incremental_rescan.py": {
            "rescan_metadata_reads": 0,
            "metadata_reused": 12700,
            "index_rows_rewritten": 0,
        },
        "profile_library_catalog.py": {
            "track_count": 12700,
            "album_widgets": 1200,
            "track_widgets": 12700,
        },
    }
    monkeypatch.setattr(
        verifier,
        "_run_json",
        lambda script, *args: payloads[script],
    )

    result = verifier.evaluate(12700)

    assert result["ok"] is False
    failed = {row["name"] for row in result["checks"] if not row["ok"]}
    assert "Albums initial render remains bounded" in failed
    assert "Tracks initial render remains bounded" in failed
