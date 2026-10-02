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
