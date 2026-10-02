from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from melodex.library_index import LocalLibraryIndex
from melodex.provider_manager import ProviderManager
from melodex.providers.local_files import LocalFilesProvider


def _track(path: Path, *, title: str = "Track", artist: str = "Artist") -> dict:
    return {
        "provider_id": "local",
        "track_id": str(path),
        "rel": f"local:{path}",
        "local_path": str(path),
        "title": title,
        "artist": artist,
        "album": "Album",
        "duration": 180.0,
        "source": "local",
    }


def _snapshot(root: Path, tracks: list[dict], *, available: bool = True) -> dict:
    return {
        "tracks": [dict(row) for row in tracks],
        "index_tracks": [dict(row) for row in tracks],
        "root_states": [{"path": str(root), "available": available}],
        "metrics": {"tracks_indexed": len(tracks), "main_thread": False},
        "cancelled": False,
    }


def test_index_round_trip_stores_metadata_not_audio(tmp_path: Path):
    root = tmp_path / "music"
    database = tmp_path / "library-index.sqlite3"
    index = LocalLibraryIndex(database)
    index.sync_roots([root])

    source = _track(root / "Artist" / "Album" / "01.flac", title="One")
    result = index.replace_scan([root], _snapshot(root, [source]))

    assert result["tracks_persisted"] == 1
    assert index.roots_ready([root]) is True
    rows = index.load_tracks([root])
    assert len(rows) == 1
    assert rows[0]["title"] == "One"
    assert rows[0]["local_path"].endswith("01.flac")

    # The SQLite file contains JSON metadata/path references, never FLAC bytes.
    with sqlite3.connect(database) as db:
        stored = db.execute(
            "SELECT metadata_json, size, mtime_ns FROM tracks"
        ).fetchone()
    assert json.loads(stored[0])["title"] == "One"
    assert stored[1] is None
    assert stored[2] is None


def test_successfully_indexed_empty_root_is_ready(tmp_path: Path):
    root = tmp_path / "empty"
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])

    assert index.roots_ready([root]) is False

    index.replace_scan([root], _snapshot(root, []))

    assert index.roots_ready([root]) is True
    assert index.summary([root])["track_count"] == 0


def test_unavailable_root_preserves_previous_cached_tracks(tmp_path: Path):
    root = tmp_path / "nas"
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])
    cached = _track(root / "cached.flac", title="Cached")

    index.replace_scan([root], _snapshot(root, [cached], available=True))
    result = index.replace_scan([root], _snapshot(root, [], available=False))

    assert result["roots_unavailable"] == 1
    assert index.roots_ready([root]) is True
    rows = index.load_tracks([root])
    assert [row["title"] for row in rows] == ["Cached"]


def test_provider_manager_loads_cached_offline_library_without_scanning(
    monkeypatch,
    tmp_path: Path,
):
    root = Path("/Volumes/Definitely-Offline-Synology/Music")
    (tmp_path / "sources.json").write_text(
        json.dumps({"local_roots": [str(root)]}),
        encoding="utf-8",
    )
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])
    cached = _track(root / "Artist" / "Album" / "song.flac", title="Offline Song")
    index.replace_scan([root], _snapshot(root, [cached], available=True))

    def fail_if_scanned(self):
        raise AssertionError("cached startup must not scan the offline NAS")

    monkeypatch.setattr(LocalFilesProvider, "scan", fail_if_scanned)

    manager = ProviderManager(tmp_path)
    try:
        assert manager.local_index_ready() is True
        assert len(manager.local_catalog()) == 1
        assert manager.local_catalog()[0]["title"] == "Offline Song"
    finally:
        manager.close()


def test_cached_metadata_overrides_apply_without_rewriting_index(tmp_path: Path):
    root = tmp_path / "music"
    path = root / "mystery.flac"
    (tmp_path / "sources.json").write_text(
        json.dumps({"local_roots": [str(root)]}),
        encoding="utf-8",
    )
    (tmp_path / "local-metadata-overrides.json").write_text(
        json.dumps(
            {
                str(path): {
                    "artist": "Corrected Artist",
                    "title": "Corrected Title",
                }
            }
        ),
        encoding="utf-8",
    )

    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])
    raw = _track(path, title="File Title", artist="File Artist")
    index.replace_scan([root], _snapshot(root, [raw], available=True))

    manager = ProviderManager(tmp_path)
    try:
        track = manager.local_catalog()[0]
        assert track["artist"] == "Corrected Artist"
        assert track["title"] == "Corrected Title"

        # Persistent cache remains raw file metadata so removing a correction
        # does not permanently bake the override into the library index.
        stored = manager.library_index.load_tracks([root])[0]
        assert stored["artist"] == "File Artist"
        assert stored["title"] == "File Title"
    finally:
        manager.close()


def test_root_identity_is_stable_without_root_existing(tmp_path: Path):
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    root = Path("/Volumes/not-mounted/music")
    first = index.root_id(root)
    second = index.root_id(Path(str(root)))
    assert first == second



def test_manager_rescan_of_offline_root_keeps_cached_live_catalog(tmp_path: Path):
    root = tmp_path / "nas"
    (tmp_path / "sources.json").write_text(
        json.dumps({"local_roots": [str(root)]}),
        encoding="utf-8",
    )
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])
    cached = _track(root / "cached.flac", title="Still Here")
    index.replace_scan([root], _snapshot(root, [cached], available=True))

    manager = ProviderManager(tmp_path)
    try:
        offline = {
            "tracks": [],
            "index_tracks": [],
            "root_states": [{"path": str(root), "available": False}],
            "metrics": {"tracks_indexed": 0, "roots_missing": 1},
            "cancelled": False,
        }
        manager.persist_local_scan_snapshot([root], offline)
        merged = manager.indexed_scan_result([root], offline)
        manager.apply_local_scan_snapshot(merged)

        catalog = manager.local_catalog()
        assert len(catalog) == 1
        assert catalog[0]["title"] == "Still Here"
        assert manager.local_index_ready([root]) is True
    finally:
        manager.close()


def test_successful_rescan_atomically_replaces_cached_root(tmp_path: Path):
    root = tmp_path / "music"
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])

    old = _track(root / "old.flac", title="Old")
    new = _track(root / "new.flac", title="New")
    index.replace_scan([root], _snapshot(root, [old], available=True))
    assert [row["title"] for row in index.load_tracks([root])] == ["Old"]

    index.replace_scan([root], _snapshot(root, [new], available=True))

    assert [row["title"] for row in index.load_tracks([root])] == ["New"]



def test_index_round_trip_preserves_file_fingerprint(tmp_path: Path):
    root = tmp_path / "music"
    path = root / "song.flac"
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])
    track = _track(path, title="Fingerprinted")

    snapshot = _snapshot(root, [track])
    snapshot["index_records"] = [
        {
            "track": dict(track),
            "size": 123456,
            "mtime_ns": 987654321,
        }
    ]
    index.replace_scan([root], snapshot)

    cache = index.load_scan_cache([root])
    entry = cache[str(path.resolve())]
    assert entry["track"]["title"] == "Fingerprinted"
    assert entry["size"] == 123456
    assert entry["mtime_ns"] == 987654321
    assert entry["root_path"] == str(root)


def test_legacy_index_without_fingerprint_is_not_treated_as_unchanged(tmp_path: Path):
    root = tmp_path / "music"
    path = root / "legacy.flac"
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])
    index.replace_scan([root], _snapshot(root, [_track(path, title="Legacy")]))

    cache = index.load_scan_cache([root])
    entry = cache[str(path.resolve())]
    assert entry["size"] is None
    assert entry["mtime_ns"] is None



def test_unchanged_fingerprinted_index_rows_are_not_rewritten(tmp_path: Path):
    root = tmp_path / "music"
    path = root / "song.flac"
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])
    track = _track(path, title="Stable")
    snapshot = _snapshot(root, [track])
    snapshot["index_records"] = [
        {"track": dict(track), "size": 100, "mtime_ns": 200}
    ]

    first = index.replace_scan([root], snapshot)
    second = index.replace_scan([root], snapshot)

    assert first["tracks_written"] == 1
    assert first["tracks_reused"] == 0
    assert second["tracks_written"] == 0
    assert second["tracks_reused"] == 1
    assert second["tracks_deleted"] == 0


def test_changed_fingerprint_updates_only_changed_index_row(tmp_path: Path):
    root = tmp_path / "music"
    first_path = root / "one.flac"
    second_path = root / "two.flac"
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])

    first_track = _track(first_path, title="One")
    second_track = _track(second_path, title="Two")
    initial = _snapshot(root, [first_track, second_track])
    initial["index_records"] = [
        {"track": dict(first_track), "size": 10, "mtime_ns": 100},
        {"track": dict(second_track), "size": 20, "mtime_ns": 200},
    ]
    index.replace_scan([root], initial)

    updated_second = _track(second_path, title="Two updated")
    changed = _snapshot(root, [first_track, updated_second])
    changed["index_records"] = [
        {"track": dict(first_track), "size": 10, "mtime_ns": 100},
        {"track": dict(updated_second), "size": 25, "mtime_ns": 300},
    ]

    result = index.replace_scan([root], changed)

    assert result["tracks_written"] == 1
    assert result["tracks_reused"] == 1
    assert result["tracks_deleted"] == 0
    titles = {row["title"] for row in index.load_tracks([root])}
    assert titles == {"One", "Two updated"}
