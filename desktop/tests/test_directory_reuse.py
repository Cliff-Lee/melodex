from __future__ import annotations

from pathlib import Path

from melodex.provider_manager import ProviderManager
from melodex.providers.local_files import LocalFilesProvider


def _metadata(path: Path) -> dict[str, object]:
    return {
        "provider_id": "local",
        "track_id": str(path),
        "rel": f"local:{path}",
        "local_path": str(path),
        "title": path.stem,
        "artist": "Reuse Artist",
        "album": path.parent.name,
        "duration": 1.0,
        "source": "local",
    }


def test_p10j_unchanged_directories_skip_track_materialization(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    for album_name in ("A", "B"):
        album = root / album_name
        album.mkdir(parents=True)
        for index in range(3):
            (album / f"{index:02d}.flac").write_bytes(b"x" * (index + 1))

    manager = ProviderManager(tmp_path / "data")
    try:
        manager.configure_local_roots([root])
        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(_metadata),
        )

        first = manager.scan_local_roots_snapshot([root])
        first_persist = manager.persist_local_scan_snapshot([root], first)
        assert first_persist["tracks_written"] == 6

        second = manager.scan_local_roots_snapshot([root])

        assert second["changes"]["metadata_reads"] == 0
        assert second["changes"]["unchanged"] == 6
        assert second["metrics"]["directory_reuse_tracks"] == 6
        assert second["metrics"]["file_work_items_materialized"] == 0
        assert second["metrics"]["directory_reuse_materializations_avoided"] == 6
        assert second["index_records"] == []
        assert len(second["preserve_directories"]) >= 2

        second_persist = manager.persist_local_scan_snapshot([root], second)
        assert second_persist["tracks_written"] == 0
        assert second_persist["tracks_deleted"] == 0
        assert second_persist["tracks_reused"] == 6
        assert second_persist["preserved_tracks"] >= 6
        assert len(manager.library_index.load_tracks([root])) == 6
    finally:
        manager.close()


def test_p10j_changed_directory_materializes_only_that_directory(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    album_a = root / "A"
    album_b = root / "B"
    album_a.mkdir(parents=True)
    album_b.mkdir(parents=True)
    for album in (album_a, album_b):
        for index in range(3):
            (album / f"{index:02d}.flac").write_bytes(b"x" * (index + 1))

    manager = ProviderManager(tmp_path / "data")
    try:
        manager.configure_local_roots([root])
        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(_metadata),
        )
        first = manager.scan_local_roots_snapshot([root])
        manager.persist_local_scan_snapshot([root], first)

        changed = album_a / "01.flac"
        changed.write_bytes(b"changed-and-longer")
        calls: list[str] = []

        def counted(path: Path):
            calls.append(str(path.relative_to(root)))
            return _metadata(path)

        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(counted),
        )
        second = manager.scan_local_roots_snapshot([root])

        assert calls == ["A/01.flac"]
        assert second["changes"]["metadata_reads"] == 1
        # Album B is preserved as one unit; Album A is materialized because its
        # manifest changed.
        assert second["metrics"]["directory_reuse_tracks"] >= 3
        assert second["metrics"]["file_work_items_materialized"] == 3
        assert second["metrics"]["directory_reuse_materializations_avoided"] >= 3
        assert len(second["index_records"]) == 3

        persisted = manager.persist_local_scan_snapshot([root], second)
        assert persisted["tracks_written"] == 1
        assert persisted["tracks_deleted"] == 0
        assert persisted["tracks_reused"] == 5
        assert len(manager.library_index.load_tracks([root])) == 6
    finally:
        manager.close()
