from __future__ import annotations

import sqlite3
from pathlib import Path

from melodex.library_index import LocalLibraryIndex, SCHEMA_VERSION
from melodex.providers.local_files import LocalFilesProvider


def _track(path: Path, title: str = "Track") -> dict[str, object]:
    return {
        "provider_id": "local",
        "track_id": str(path),
        "rel": f"local:{path}",
        "local_path": str(path),
        "title": title,
        "artist": "Resume Artist",
        "album": "Resume Album",
        "duration": 180.0,
        "source": "local",
    }


def test_p10h_interrupted_generation_staging_is_reusable(tmp_path: Path):
    root = tmp_path / "music"
    root.mkdir()
    track = root / "one.flac"
    track.write_bytes(b"new")

    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    generation = index.begin_scan_generation([root])
    stat = track.stat()
    written = index.stage_scan_records(
        generation,
        [root],
        [
            {
                "track": _track(track, "Staged"),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        ],
    )
    assert written == 1

    index.finish_scan_generation(generation, status="cancelled")
    resume = index.load_resume_cache([root])

    key = str(track.resolve())
    assert key in resume
    assert resume[key]["track"]["title"] == "Staged"
    assert resume[key]["resume_staged"] is True
    assert index.scan_generation_summary([root])["status"] == "cancelled"


def test_p10h_new_generation_marks_abandoned_running_scan_interrupted(
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")

    first = index.begin_scan_generation([root])
    second = index.begin_scan_generation([root])

    assert first != second
    with index._connect() as db:
        states = {
            str(row["generation_id"]): str(row["status"])
            for row in db.execute(
                "SELECT generation_id, status FROM scan_generations"
            ).fetchall()
        }

    assert states[first] == "interrupted"
    assert states[second] == "running"


def test_p10h_resumed_metadata_skips_tag_read_only_when_fingerprint_matches(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    track = root / "one.flac"
    track.write_bytes(b"same")

    stat = track.stat()
    staged = {
        str(track.resolve()): {
            "track": _track(track, "Already Read"),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "root_path": str(root),
            "resume_staged": True,
        }
    }

    def must_not_read(path: Path):
        raise AssertionError(f"staged metadata reopened: {path}")

    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(must_not_read),
    )
    provider = LocalFilesProvider(scan_on_init=False)
    snapshot = provider.scan_snapshot([root], cached_entries=staged)

    assert snapshot["changes"]["metadata_reads"] == 0
    assert snapshot["changes"]["resumed"] == 1
    assert snapshot["metrics"]["resumed_files"] == 1
    assert snapshot["tracks"][0]["title"] == "Already Read"


def test_p10h_changed_fingerprint_invalidates_staged_metadata(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    track = root / "one.flac"
    track.write_bytes(b"before")
    before = track.stat()

    staged = {
        str(track.resolve()): {
            "track": _track(track, "Old Staged"),
            "size": before.st_size,
            "mtime_ns": before.st_mtime_ns,
            "root_path": str(root),
            "resume_staged": True,
        }
    }

    track.write_bytes(b"after-and-longer")
    calls: list[str] = []

    def metadata(path: Path):
        calls.append(path.name)
        return _track(path, "Fresh")

    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(metadata),
    )
    provider = LocalFilesProvider(scan_on_init=False)
    snapshot = provider.scan_snapshot([root], cached_entries=staged)

    assert calls == ["one.flac"]
    assert snapshot["changes"]["metadata_reads"] == 1
    assert snapshot["changes"]["resumed"] == 0
    assert snapshot["tracks"][0]["title"] == "Fresh"


def test_p10h_completed_generation_discards_staging_after_live_commit(
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    track = root / "one.flac"
    track.write_bytes(b"x")
    stat = track.stat()

    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    generation = index.begin_scan_generation([root])
    index.stage_scan_records(
        generation,
        [root],
        [{
            "track": _track(track),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }],
    )

    snapshot = {
        "tracks": [_track(track)],
        "index_records": [{
            "track": _track(track),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }],
        "root_states": [{
            "path": str(root),
            "available": True,
            "complete": True,
        }],
        "directory_manifests": [],
        "cancelled": False,
    }
    index.replace_scan([root], snapshot)
    index.finish_scan_generation(generation, status="completed")

    assert index.load_resume_cache([root]) == {}
    assert index.scan_generation_summary([root])["status"] == "completed"
    assert len(index.load_tracks([root])) == 1


def test_p10h_incomplete_scan_never_deletes_live_tracks(
    tmp_path: Path,
):
    root = tmp_path / "nas"
    root.mkdir()
    keep = root / "keep.flac"
    hidden = root / "hidden.flac"
    keep.write_bytes(b"k")
    hidden.write_bytes(b"h")

    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    initial = {
        "tracks": [_track(keep), _track(hidden)],
        "index_records": [
            {
                "track": _track(path),
                "size": path.stat().st_size,
                "mtime_ns": path.stat().st_mtime_ns,
            }
            for path in (keep, hidden)
        ],
        "root_states": [{
            "path": str(root),
            "available": True,
            "complete": True,
        }],
        "directory_manifests": [],
        "cancelled": False,
    }
    index.replace_scan([root], initial)

    partial = {
        "tracks": [_track(keep)],
        "index_records": [{
            "track": _track(keep),
            "size": keep.stat().st_size,
            "mtime_ns": keep.stat().st_mtime_ns,
        }],
        "root_states": [{
            "path": str(root),
            "available": True,
            "complete": False,
        }],
        "directory_manifests": [],
        "cancelled": False,
    }
    index.replace_scan([root], partial)

    names = {Path(row["local_path"]).name for row in index.load_tracks([root])}
    assert names == {"keep.flac", "hidden.flac"}


def test_p10h_schema_v2_upgrades_to_v3(tmp_path: Path):
    database = tmp_path / "library-index.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute(
            "CREATE TABLE roots ("
            "root_id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, "
            "last_scan_at TEXT, last_track_count INTEGER NOT NULL DEFAULT 0)"
        )
        db.execute(
            "CREATE TABLE tracks ("
            "root_id TEXT NOT NULL, relative_path TEXT NOT NULL, "
            "metadata_json TEXT NOT NULL, size INTEGER, mtime_ns INTEGER, "
            "PRIMARY KEY (root_id, relative_path))"
        )
        db.execute(
            "CREATE TABLE directories ("
            "root_id TEXT NOT NULL, relative_dir TEXT NOT NULL, "
            "manifest TEXT NOT NULL, file_count INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (root_id, relative_dir))"
        )
        db.execute("PRAGMA user_version = 2")

    LocalLibraryIndex(database)

    with sqlite3.connect(database) as db:
        version = int(db.execute("PRAGMA user_version").fetchone()[0])
        generation_table = db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='scan_generations'"
        ).fetchone()
        stage_table = db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='scan_stage_tracks'"
        ).fetchone()

    assert SCHEMA_VERSION == 3
    assert version == 3
    assert generation_table is not None
    assert stage_table is not None
