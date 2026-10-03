from __future__ import annotations

from pathlib import Path

import melodex.providers.local_files as local_files
from melodex.providers.local_files import LocalFilesProvider


def _metadata(path: Path) -> dict[str, object]:
    return {
        "provider_id": "local",
        "track_id": str(path),
        "rel": f"local:{path}",
        "title": path.stem,
        "artist": "Single Snapshot Artist",
        "album": "Single Snapshot Album",
        "duration": 180.0,
        "local_path": str(path),
        "source": "local",
    }


def test_p10e_persistence_only_scan_keeps_one_collection_copy(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    for index in range(3):
        (root / f"track-{index}.flac").write_bytes(b"x")

    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata),
    )

    provider = LocalFilesProvider(scan_on_init=False)
    snapshot = provider.scan_snapshot([root], collect_tracks=False)

    assert snapshot["cancelled"] is False
    assert snapshot["tracks"] == []
    assert len(snapshot["index_records"]) == 3
    assert "index_tracks" not in snapshot
    assert snapshot["metrics"]["tracks_indexed"] == 3
    assert snapshot["metrics"]["collect_tracks"] is False
    assert snapshot["metrics"]["snapshot_track_copies"] == 1


def test_p10e_default_scan_keeps_compatibility_catalog(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    (root / "one.flac").write_bytes(b"x")

    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata),
    )

    provider = LocalFilesProvider(scan_on_init=False)
    snapshot = provider.scan_snapshot([root])

    assert len(snapshot["tracks"]) == 1
    assert len(snapshot["index_records"]) == 1
    assert "index_tracks" not in snapshot
    assert snapshot["metrics"]["tracks_indexed"] == 1
    assert snapshot["metrics"]["collect_tracks"] is True
    assert snapshot["metrics"]["snapshot_track_copies"] == 2


def test_p10e_incomplete_root_rolls_back_persistence_only_count(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "nas"
    root.mkdir()
    (root / "one.flac").write_bytes(b"x")

    def partial_walk(_root, onerror=None):
        yield str(root), [], ["one.flac"]
        if onerror is not None:
            onerror(PermissionError("simulated partial NAS"))

    monkeypatch.setattr(local_files.os, "walk", partial_walk)
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata),
    )

    provider = LocalFilesProvider(scan_on_init=False)
    snapshot = provider.scan_snapshot([root], collect_tracks=False)

    assert snapshot["tracks"] == []
    assert snapshot["index_records"] == []
    assert snapshot["metrics"]["tracks_indexed"] == 0
    assert snapshot["changes"]["incomplete_roots"] == 1
