from __future__ import annotations

import json
import time
from pathlib import Path

import melodex.providers.local_files as local_files
from melodex.providers.local_files import LocalFilesProvider


def _metadata_row(path: Path) -> dict[str, object]:
    return {
        "provider_id": "local",
        "track_id": str(path),
        "rel": f"local:{path}",
        "title": path.stem,
        "artist": "Benchmark Artist",
        "album": "Benchmark Album",
        "duration": 180.0,
        "local_path": str(path),
        "source": "local",
    }


def test_scan_metrics_count_work_without_exposing_paths(monkeypatch, tmp_path: Path):
    root = tmp_path / "nas-share"
    root.mkdir()

    def fake_walk(_root):
        yield str(root / "Artist A"), [], ["01.flac", "notes.txt"]
        yield str(root / "Artist B"), [], ["02.mp3"]

    monkeypatch.setattr(local_files.os, "walk", fake_walk)
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata_row),
    )

    provider = LocalFilesProvider()
    provider.roots = [root]

    assert provider.scan() == 2

    metrics = provider.last_scan_metrics
    assert metrics["root_count"] == 1
    assert metrics["roots_checked"] == 1
    assert metrics["roots_missing"] == 0
    assert metrics["directories_seen"] == 2
    assert metrics["files_seen"] == 3
    assert metrics["audio_files_seen"] == 2
    assert metrics["metadata_attempts"] == 2
    assert metrics["tracks_indexed"] == 2
    assert metrics["main_thread"] is True
    assert metrics["total_seconds"] >= metrics["metadata_seconds"]

    # Support diagnostics must never reveal the listener's mount or filenames.
    serialized = json.dumps(metrics)
    assert str(root) not in serialized
    assert "01.flac" not in serialized
    assert "Artist A" not in serialized


def test_scan_metrics_make_slow_metadata_visible(monkeypatch, tmp_path: Path):
    root = tmp_path / "slow-share"
    root.mkdir()

    def fake_walk(_root):
        yield str(root), [], ["a.flac", "b.flac", "c.flac"]

    def slow_metadata(path: Path):
        time.sleep(0.006)
        return _metadata_row(path)

    monkeypatch.setattr(local_files.os, "walk", fake_walk)
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(slow_metadata),
    )

    provider = LocalFilesProvider()
    provider.roots = [root]
    provider.scan()

    metrics = provider.last_scan_metrics
    assert metrics["metadata_attempts"] == 3
    assert metrics["metadata_seconds"] >= 0.015
    assert metrics["total_seconds"] >= metrics["metadata_seconds"]


def test_constructor_scan_records_that_work_runs_on_calling_thread(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "startup-share"
    root.mkdir()

    monkeypatch.setattr(
        local_files.os,
        "walk",
        lambda _root: [(str(root), [], ["startup.flac"])],
    )
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata_row),
    )

    provider = LocalFilesProvider([root])

    assert provider.last_scan_metrics["tracks_indexed"] == 1
    # This captures the current architecture: constructing the provider scans
    # synchronously on the caller. Campaign 2 is expected to change this.
    assert provider.last_scan_metrics["main_thread"] is True
