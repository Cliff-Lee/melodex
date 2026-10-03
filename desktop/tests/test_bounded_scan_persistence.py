from __future__ import annotations

import sqlite3
from pathlib import Path

from melodex.library_index import LocalLibraryIndex, SCHEMA_VERSION


def _track(path: Path, title: str) -> dict[str, object]:
    return {
        "provider_id": "local",
        "track_id": str(path),
        "local_path": str(path),
        "rel": f"local:{path}",
        "title": title,
        "artist": "Bounded",
        "album": path.parent.name,
        "source": "local",
    }


def _snapshot(root: Path, manifests: list[dict[str, object]], preserved=None):
    return {
        "root_states": [{
            "path": str(root),
            "available": True,
            "complete": True,
        }],
        "directory_manifests": manifests,
        "preserve_directories": list(preserved or []),
        "tracks": [],
        "index_records": [],
        "cancelled": False,
    }


def test_p10l_staged_generation_publishes_without_index_records(tmp_path: Path):
    root = tmp_path / "music"
    album = root / "Album"
    album.mkdir(parents=True)
    one = album / "01.flac"
    two = album / "02.flac"
    one.write_bytes(b"a")
    two.write_bytes(b"bb")

    index = LocalLibraryIndex(tmp_path / "index.sqlite3")
    index.sync_roots([root])
    generation = index.begin_scan_generation([root])
    index.stage_scan_records(
        generation,
        [root],
        [
            {
                "track": _track(one, "One"),
                "size": one.stat().st_size,
                "mtime_ns": one.stat().st_mtime_ns,
            },
            {
                "track": _track(two, "Two"),
                "size": two.stat().st_size,
                "mtime_ns": two.stat().st_mtime_ns,
            },
        ],
    )

    snapshot = _snapshot(
        root,
        [{
            "root_path": str(root),
            "path": str(album),
            "manifest": "abc",
            "file_count": 2,
        }],
    )
    result = index.publish_scan_generation(generation, [root], snapshot)

    assert result["cancelled"] is False
    assert result["staged_generation"] is True
    assert result["tracks_persisted"] == 2
    assert {row["title"] for row in index.load_tracks([root])} == {"One", "Two"}


def test_p10l_preserved_directory_survives_empty_stage(tmp_path: Path):
    root = tmp_path / "music"
    album = root / "Album"
    album.mkdir(parents=True)
    track = album / "01.flac"
    track.write_bytes(b"x")

    index = LocalLibraryIndex(tmp_path / "index.sqlite3")
    index.sync_roots([root])

    first = index.begin_scan_generation([root])
    index.stage_scan_records(
        first,
        [root],
        [{
            "track": _track(track, "Keep"),
            "size": track.stat().st_size,
            "mtime_ns": track.stat().st_mtime_ns,
        }],
    )
    manifest = {
        "root_path": str(root),
        "path": str(album),
        "manifest": "same",
        "file_count": 1,
    }
    index.publish_scan_generation(first, [root], _snapshot(root, [manifest]))

    second = index.begin_scan_generation([root])
    preserved = [{
        "root_path": str(root),
        "path": str(album),
        "file_count": 1,
    }]
    result = index.publish_scan_generation(
        second,
        [root],
        _snapshot(root, [manifest], preserved=preserved),
    )

    assert result["tracks_deleted"] == 0
    assert result["tracks_persisted"] == 1
    assert [row["title"] for row in index.load_tracks([root])] == ["Keep"]


def test_p10l_removed_directory_is_deleted_atomically(tmp_path: Path):
    root = tmp_path / "music"
    album = root / "Old Album"
    album.mkdir(parents=True)
    track = album / "01.flac"
    track.write_bytes(b"x")

    index = LocalLibraryIndex(tmp_path / "index.sqlite3")
    index.sync_roots([root])

    first = index.begin_scan_generation([root])
    index.stage_scan_records(
        first,
        [root],
        [{
            "track": _track(track, "Old"),
            "size": track.stat().st_size,
            "mtime_ns": track.stat().st_mtime_ns,
        }],
    )
    index.publish_scan_generation(
        first,
        [root],
        _snapshot(
            root,
            [{
                "root_path": str(root),
                "path": str(album),
                "manifest": "old",
                "file_count": 1,
            }],
        ),
    )

    second = index.begin_scan_generation([root])
    result = index.publish_scan_generation(
        second,
        [root],
        _snapshot(root, []),
    )

    assert result["tracks_deleted"] == 1
    assert index.load_tracks([root]) == []


def test_p10l_schema_v3_adds_relative_path_to_staging(tmp_path: Path):
    database = tmp_path / "index.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute(
            "CREATE TABLE scan_generations ("
            "generation_id TEXT PRIMARY KEY, root_signature TEXT NOT NULL, "
            "started_at TEXT NOT NULL, completed_at TEXT, "
            "status TEXT NOT NULL, staged_count INTEGER NOT NULL DEFAULT 0)"
        )
        db.execute(
            "CREATE TABLE scan_stage_tracks ("
            "generation_id TEXT NOT NULL, local_path TEXT NOT NULL, "
            "root_id TEXT NOT NULL, metadata_json TEXT NOT NULL, "
            "size INTEGER, mtime_ns INTEGER, "
            "PRIMARY KEY (generation_id, local_path))"
        )
        db.execute("PRAGMA user_version = 3")

    LocalLibraryIndex(database)

    with sqlite3.connect(database) as db:
        version = int(db.execute("PRAGMA user_version").fetchone()[0])
        columns = {
            str(row[1])
            for row in db.execute(
                "PRAGMA table_info(scan_stage_tracks)"
            ).fetchall()
        }

    assert SCHEMA_VERSION == 4
    assert version == 4
    assert "relative_path" in columns
