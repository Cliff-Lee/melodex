from __future__ import annotations

import sqlite3
from pathlib import Path

from melodex.library_index import LocalLibraryIndex, SCHEMA_VERSION
from melodex.provider_manager import ProviderManager
from melodex.providers.local_files import LocalFilesProvider


def _metadata(path: Path) -> dict[str, object]:
    return {
        "provider_id": "local",
        "track_id": str(path),
        "rel": f"local:{path}",
        "title": path.stem,
        "artist": "Manifest Artist",
        "album": path.parent.name,
        "duration": 180.0,
        "local_path": str(path),
        "source": "local",
    }


def test_p10f_directory_manifests_round_trip_and_hit_on_unchanged_rescan(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    album_a = root / "Artist" / "Album A"
    album_b = root / "Artist" / "Album B"
    album_a.mkdir(parents=True)
    album_b.mkdir(parents=True)
    (album_a / "01.flac").write_bytes(b"a")
    (album_a / "02.flac").write_bytes(b"bb")
    (album_b / "01.flac").write_bytes(b"ccc")

    manager = ProviderManager(tmp_path / "data")
    try:
        manager.configure_local_roots([root])
        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(_metadata),
        )

        first = manager.scan_local_roots_snapshot([root])
        persisted = manager.persist_local_scan_snapshot([root], first)

        manifests = manager.library_index.load_directory_manifests([root])
        assert persisted["directory_manifests_persisted"] >= 2
        assert str(album_a.resolve()) in manifests
        assert str(album_b.resolve()) in manifests

        second = manager.scan_local_roots_snapshot([root])
        assert second["changes"]["metadata_reads"] == 0
        assert second["metrics"]["directory_manifest_hits"] >= 2
        assert second["metrics"]["directory_manifest_misses"] == 0
    finally:
        manager.close()


def test_p10f_changing_one_file_invalidates_only_its_directory_manifest(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    album_a = root / "Album A"
    album_b = root / "Album B"
    album_a.mkdir(parents=True)
    album_b.mkdir(parents=True)
    changed = album_a / "01.flac"
    stable = album_b / "01.flac"
    changed.write_bytes(b"before")
    stable.write_bytes(b"stable")

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

        changed.write_bytes(b"after-and-longer")
        calls: list[str] = []

        def counted(path: Path):
            calls.append(path.name)
            return _metadata(path)

        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(counted),
        )
        second = manager.scan_local_roots_snapshot([root])

        assert calls == ["01.flac"]
        assert second["changes"]["metadata_reads"] == 1
        assert second["metrics"]["directory_manifest_hits"] >= 1
        assert second["metrics"]["directory_manifest_misses"] >= 1
    finally:
        manager.close()


def test_p10f_manifest_contains_file_size_and_mtime_changes(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    album = root / "Album"
    album.mkdir(parents=True)
    track = album / "one.flac"
    track.write_bytes(b"x")

    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata),
    )
    provider = LocalFilesProvider(scan_on_init=False)

    first = provider.scan_snapshot([root])
    first_manifest = {
        row["path"]: row["manifest"]
        for row in first["directory_manifests"]
    }[str(album)]

    track.write_bytes(b"changed-size")
    second = provider.scan_snapshot([root])
    second_manifest = {
        row["path"]: row["manifest"]
        for row in second["directory_manifests"]
    }[str(album)]

    assert first_manifest != second_manifest


def test_p10f_schema_v1_upgrades_to_v2_without_losing_tracks(tmp_path: Path):
    database = tmp_path / "library-index.sqlite3"
    root = tmp_path / "music"
    root_id = LocalLibraryIndex.root_id(root)

    with sqlite3.connect(database) as db:
        db.execute(
            """
            CREATE TABLE roots (
                root_id TEXT PRIMARY KEY,
                path TEXT NOT NULL UNIQUE,
                last_scan_at TEXT,
                last_track_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        db.execute(
            """
            CREATE TABLE tracks (
                root_id TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                size INTEGER,
                mtime_ns INTEGER,
                PRIMARY KEY (root_id, relative_path)
            )
            """
        )
        db.execute(
            "INSERT INTO roots(root_id, path, last_scan_at, last_track_count) "
            "VALUES(?, ?, 'done', 1)",
            (root_id, str(root)),
        )
        db.execute(
            "INSERT INTO tracks(root_id, relative_path, metadata_json, size, mtime_ns) "
            "VALUES(?, 'one.flac', ?, 1, 2)",
            (
                root_id,
                '{"provider_id":"local","track_id":"'
                + str(root / "one.flac")
                + '","local_path":"'
                + str(root / "one.flac")
                + '","title":"One"}',
            ),
        )
        db.execute("PRAGMA user_version = 1")

    index = LocalLibraryIndex(database)

    with sqlite3.connect(database) as db:
        version = int(db.execute("PRAGMA user_version").fetchone()[0])
        directory_table = db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='directories'"
        ).fetchone()

    assert SCHEMA_VERSION >= 2
    assert version == SCHEMA_VERSION
    assert directory_table is not None
    assert [row["title"] for row in index.load_tracks([root])] == ["One"]
