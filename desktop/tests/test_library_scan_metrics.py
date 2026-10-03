from __future__ import annotations

import json
import time
from pathlib import Path

import melodex.providers.local_files as local_files
from melodex.library_scan import ScanControl
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
    assert metrics["metadata_work_seconds"] >= 0.015
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



def test_scan_progress_has_discovery_metadata_and_complete_phases(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "progress-share"
    root.mkdir()

    monkeypatch.setattr(
        local_files.os,
        "walk",
        lambda _root: [
            (str(root / "Artist"), [], ["one.flac", "two.flac", "notes.txt"])
        ],
    )
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata_row),
    )

    provider = LocalFilesProvider(scan_on_init=False)
    events = []
    snapshot = provider.scan_snapshot([root], progress=lambda row: events.append(dict(row)))

    phases = [row["phase"] for row in events]
    assert phases[0] == "discovering"
    assert "metadata" in phases
    assert phases[-1] == "complete"
    assert events[-1]["completed"] == 2
    assert events[-1]["total"] == 2
    assert snapshot["cancelled"] is False
    serialized = json.dumps(events)
    assert str(root) not in serialized


def test_cancelled_scan_never_returns_partial_catalog(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "cancel-share"
    root.mkdir()
    control = ScanControl()
    calls = []

    monkeypatch.setattr(
        local_files.os,
        "walk",
        lambda _root: [(str(root), [], ["one.flac", "two.flac", "three.flac"])],
    )

    def metadata_then_cancel(path: Path):
        calls.append(path.name)
        if len(calls) == 1:
            control.cancel()
        return _metadata_row(path)

    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(metadata_then_cancel),
    )

    provider = LocalFilesProvider(scan_on_init=False)
    snapshot = provider.scan_snapshot([root], control=control)

    assert snapshot["cancelled"] is True
    assert snapshot["tracks"] == []
    # One file was parsed, but cancellation is atomic: no partial track is
    # considered indexed/applied.
    assert snapshot["metrics"]["metadata_attempts"] == 1
    assert snapshot["metrics"]["tracks_indexed"] == 0
    assert calls == ["one.flac"]
    assert provider.tracks == []


def test_paused_scan_waits_until_resumed(
    monkeypatch,
    tmp_path: Path,
):
    import threading

    root = tmp_path / "pause-share"
    root.mkdir()
    control = ScanControl()
    control.pause()
    metadata_calls = []
    holder = {}

    monkeypatch.setattr(
        local_files.os,
        "walk",
        lambda _root: [(str(root), [], ["one.flac"])],
    )

    def metadata(path: Path):
        metadata_calls.append(path.name)
        return _metadata_row(path)

    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(metadata),
    )

    provider = LocalFilesProvider(scan_on_init=False)

    worker = threading.Thread(
        target=lambda: holder.setdefault(
            "snapshot",
            provider.scan_snapshot([root], control=control),
        )
    )
    worker.start()
    time.sleep(0.05)

    assert worker.is_alive()
    assert metadata_calls == []

    control.resume()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert holder["snapshot"]["cancelled"] is False
    assert len(holder["snapshot"]["tracks"]) == 1



def test_unchanged_rescan_reuses_cached_metadata_without_tag_reads(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    paths = [root / "one.flac", root / "two.flac", root / "three.flac"]
    for index, path in enumerate(paths):
        path.write_bytes((b"x" * (index + 1)) or b"x")

    manager = ProviderManager(tmp_path)
    try:
        manager.configure_local_roots([root])
        first_calls = []

        def first_metadata(path: Path):
            first_calls.append(path.name)
            return _metadata_row(path)

        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(first_metadata),
        )
        first = manager.scan_local_roots_snapshot([root])
        assert len(first_calls) == 3
        manager.persist_local_scan_snapshot([root], first)

        def metadata_must_not_run(path: Path):
            raise AssertionError(f"unchanged file reopened for tags: {path.name}")

        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(metadata_must_not_run),
        )
        second = manager.scan_local_roots_snapshot([root])

        assert second["cancelled"] is False
        assert second["changes"]["unchanged"] == 3
        assert second["changes"]["added"] == 0
        assert second["changes"]["changed"] == 0
        assert second["changes"]["removed"] == 0
        assert second["changes"]["metadata_reads"] == 0
        assert second["metrics"]["metadata_attempts"] == 0
        assert second["index_records"] == []
        assert second["metrics"]["directory_reuse_tracks"] == 3
        assert len(second["preserve_directories"]) >= 1
    finally:
        manager.close()


def test_incremental_rescan_reads_only_changed_file(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    stable = root / "stable.flac"
    changed = root / "changed.flac"
    stable.write_bytes(b"stable")
    changed.write_bytes(b"before")

    manager = ProviderManager(tmp_path)
    try:
        manager.configure_local_roots([root])
        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(_metadata_row),
        )
        first = manager.scan_local_roots_snapshot([root])
        manager.persist_local_scan_snapshot([root], first)

        # Change both size and mtime so the fingerprint definitely differs on
        # filesystems with coarse timestamp precision.
        changed.write_bytes(b"after-and-longer")
        calls = []

        def counted_metadata(path: Path):
            calls.append(path.name)
            return _metadata_row(path)

        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(counted_metadata),
        )
        second = manager.scan_local_roots_snapshot([root])

        assert calls == ["changed.flac"]
        assert second["changes"]["unchanged"] == 1
        assert second["changes"]["changed"] == 1
        assert second["changes"]["added"] == 0
        assert second["changes"]["metadata_reads"] == 1
    finally:
        manager.close()


def test_incremental_rescan_detects_added_and_removed_files(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    keep = root / "keep.flac"
    remove = root / "remove.flac"
    keep.write_bytes(b"keep")
    remove.write_bytes(b"remove")

    manager = ProviderManager(tmp_path)
    try:
        manager.configure_local_roots([root])
        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(_metadata_row),
        )
        first = manager.scan_local_roots_snapshot([root])
        manager.persist_local_scan_snapshot([root], first)

        remove.unlink()
        added = root / "added.flac"
        added.write_bytes(b"added")

        calls = []

        def counted_metadata(path: Path):
            calls.append(path.name)
            return _metadata_row(path)

        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(counted_metadata),
        )
        second = manager.scan_local_roots_snapshot([root])

        assert calls == ["added.flac"]
        assert second["changes"]["unchanged"] == 1
        assert second["changes"]["added"] == 1
        assert second["changes"]["removed"] == 1
        assert second["changes"]["metadata_reads"] == 1

        manager.persist_local_scan_snapshot([root], second)
        merged = manager.indexed_scan_result([root], second)
        titles = {
            Path(track["local_path"]).name
            for track in merged["tracks"]
        }
        assert titles == {"keep.flac", "added.flac"}
    finally:
        manager.close()


def test_old_index_without_fingerprints_is_refreshed_once(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    path = root / "legacy.flac"
    path.write_bytes(b"legacy")

    manager = ProviderManager(tmp_path)
    try:
        manager.configure_local_roots([root])
        # Simulate a Campaign-4 cache: metadata exists, fingerprints do not.
        raw = _metadata_row(path)
        legacy = {
            "tracks": [dict(raw)],
            "index_tracks": [dict(raw)],
            "root_states": [{"path": str(root), "available": True}],
            "metrics": {"tracks_indexed": 1},
            "cancelled": False,
        }
        manager.persist_local_scan_snapshot([root], legacy)

        calls = []
        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(lambda p: calls.append(p.name) or _metadata_row(p)),
        )
        refresh = manager.scan_local_roots_snapshot([root])
        assert calls == ["legacy.flac"]
        assert refresh["changes"]["changed"] == 1
        manager.persist_local_scan_snapshot([root], refresh)

        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(
                lambda p: (_ for _ in ()).throw(
                    AssertionError("fingerprinted file should now be reused")
                )
            ),
        )
        again = manager.scan_local_roots_snapshot([root])
        assert again["changes"]["unchanged"] == 1
        assert again["changes"]["metadata_reads"] == 0
    finally:
        manager.close()



def test_partial_directory_walk_preserves_cached_root(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "nas"
    root.mkdir()
    first_path = root / "first.flac"
    hidden_path = root / "hidden.flac"
    first_path.write_bytes(b"first")
    hidden_path.write_bytes(b"hidden")

    manager = ProviderManager(tmp_path)
    try:
        manager.configure_local_roots([root])
        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(_metadata_row),
        )
        initial = manager.scan_local_roots_snapshot([root])
        manager.persist_local_scan_snapshot([root], initial)
        assert len(manager.library_index.load_tracks([root])) == 2

        def partial_walk(_root, onerror=None):
            yield str(root), [], ["first.flac"]
            if onerror is not None:
                onerror(PermissionError("simulated unreadable NAS subfolder"))

        monkeypatch.setattr(local_files.os, "walk", partial_walk)
        metadata_calls = []
        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(
                lambda p: metadata_calls.append(p.name) or _metadata_row(p)
            ),
        )

        partial = manager.scan_local_roots_snapshot([root])

        assert partial["changes"]["incomplete_roots"] == 1
        assert partial["changes"]["removed"] == 0
        assert partial["index_records"] == []
        assert metadata_calls == []

        persisted = manager.persist_local_scan_snapshot([root], partial)
        assert persisted["roots_incomplete"] == 1
        merged = manager.indexed_scan_result([root], partial)
        names = {
            Path(track["local_path"]).name
            for track in merged["tracks"]
        }
        assert names == {"first.flac", "hidden.flac"}
    finally:
        manager.close()
