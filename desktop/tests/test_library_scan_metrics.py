from __future__ import annotations

import json
import time
from pathlib import Path

import melodex.providers.local_files as local_files
from melodex.provider_manager import ProviderManager
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



def test_scan_snapshot_does_not_mutate_live_catalog_until_applied(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "snapshot-share"
    root.mkdir()

    monkeypatch.setattr(
        local_files.os,
        "walk",
        lambda _root: [(str(root), [], ["one.flac", "two.flac"])],
    )
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata_row),
    )

    provider = LocalFilesProvider(scan_on_init=False)
    provider.configure_roots([root])

    snapshot = provider.scan_snapshot()

    assert provider.tracks == []
    assert len(snapshot["tracks"]) == 2
    assert snapshot["metrics"]["tracks_indexed"] == 2

    assert provider.apply_scan_snapshot(snapshot) == 2
    assert len(provider.tracks) == 2


def test_provider_manager_does_not_scan_saved_roots_during_startup(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "saved-nas"
    root.mkdir()
    (tmp_path / "sources.json").write_text(
        json.dumps({"local_roots": [str(root)]}),
        encoding="utf-8",
    )

    def fail_if_scanned(self):
        raise AssertionError("saved roots must not be scanned during ProviderManager startup")

    monkeypatch.setattr(LocalFilesProvider, "scan", fail_if_scanned)

    manager = ProviderManager(tmp_path)
    try:
        assert manager.local_roots() == [root]
        assert manager.local_catalog() == []
    finally:
        manager.close()


def test_background_scan_snapshot_records_worker_thread(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "worker-share"
    root.mkdir()

    monkeypatch.setattr(
        local_files.os,
        "walk",
        lambda _root: [(str(root), [], ["worker.flac"])],
    )
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata_row),
    )

    provider = LocalFilesProvider(scan_on_init=False)
    snapshot_holder = {}

    import threading

    def run():
        snapshot_holder["value"] = provider.scan_snapshot([root])

    worker = threading.Thread(target=run, name="library-scan-test")
    worker.start()
    worker.join(timeout=2)

    assert not worker.is_alive()
    snapshot = snapshot_holder["value"]
    assert snapshot["metrics"]["main_thread"] is False
    assert snapshot["metrics"]["thread_name"] == "library-scan-test"



def test_manager_clearing_metadata_override_does_not_rescan_synchronously(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    track_path = root / "track.flac"
    track_path.write_bytes(b"not real audio")

    manager = ProviderManager(tmp_path)
    try:
        provider = manager.providers["local"]
        assert isinstance(provider, LocalFilesProvider)
        provider.configure_roots([root])
        provider.overrides[provider._override_key(track_path)] = {"artist": "Corrected"}
        manager._local_metadata_overrides[provider._override_key(track_path)] = {
            "artist": "Corrected"
        }

        monkeypatch.setattr(
            provider,
            "scan",
            lambda: (_ for _ in ()).throw(
                AssertionError("metadata reset must not synchronously rescan the library")
            ),
        )

        changed = manager.clear_local_metadata_correction(
            {"local_path": str(track_path)}
        )

        assert changed is True
        assert provider._override_key(track_path) not in provider.overrides
    finally:
        manager.close()
