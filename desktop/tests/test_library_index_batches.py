from __future__ import annotations

from pathlib import Path

from melodex.library_index import LocalLibraryIndex


def _track(path: Path, index: int) -> dict[str, object]:
    return {
        "provider_id": "local",
        "track_id": str(path),
        "rel": f"local:{path}",
        "local_path": str(path),
        "title": f"Track {index}",
        "artist": "Batch Artist",
        "album": f"Album {index // 20}",
        "duration": 180.0,
        "source": "local",
    }


def _snapshot(root: Path, count: int) -> dict[str, object]:
    records = []
    tracks = []
    for index in range(count):
        path = root / f"track-{index:06d}.flac"
        track = _track(path, index)
        tracks.append(track)
        records.append(
            {
                "track": track,
                "size": index + 1,
                "mtime_ns": 1_000_000_000 + index,
            }
        )
    return {
        "tracks": tracks,
        "index_tracks": tracks,
        "index_records": records,
        "root_states": [
            {"path": str(root), "available": True, "complete": True}
        ],
        "metrics": {"tracks_indexed": count},
        "cancelled": False,
    }


def test_p10d_index_writes_are_bounded_to_configured_batch_size(tmp_path: Path):
    root = tmp_path / "music"
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")

    result = index.replace_scan(
        [root],
        _snapshot(root, 601),
        batch_size=250,
    )

    assert result["tracks_written"] == 601
    assert result["write_batches"] == 3
    assert result["delete_batches"] == 0
    assert result["batch_size"] == 250
    assert result["max_batch_rows"] == 250
    assert len(index.load_tracks([root])) == 601


def test_p10d_unchanged_rows_do_not_create_write_batches(tmp_path: Path):
    root = tmp_path / "music"
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    snapshot = _snapshot(root, 601)

    first = index.replace_scan([root], snapshot, batch_size=250)
    second = index.replace_scan([root], snapshot, batch_size=250)

    assert first["write_batches"] == 3
    assert second["tracks_written"] == 0
    assert second["tracks_reused"] == 601
    assert second["write_batches"] == 0
    assert second["max_batch_rows"] == 0
    assert second["max_existing_fingerprint_rows"] == 601
    assert second["max_incoming_path_rows"] == 601
    assert second["max_removed_path_rows"] == 0


def test_p10d_cancellation_after_batch_rolls_back_entire_transaction(
    tmp_path: Path,
):
    root = tmp_path / "music"
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")

    original = _snapshot(root, 1)
    index.replace_scan([root], original)

    replacement = _snapshot(root, 601)
    checks = {"count": 0}

    def cancel_after_first_write_batch() -> bool:
        checks["count"] += 1
        # start check, root check, then first full write batch checkpoint
        return checks["count"] >= 3

    result = index.replace_scan(
        [root],
        replacement,
        cancelled=cancel_after_first_write_batch,
        batch_size=250,
    )

    assert result["cancelled"] is True
    stored = index.load_tracks([root])
    assert len(stored) == 1
    assert stored[0]["title"] == "Track 0"


def test_p10d_deletions_are_batched_too(tmp_path: Path):
    root = tmp_path / "music"
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.replace_scan([root], _snapshot(root, 601), batch_size=250)

    result = index.replace_scan([root], _snapshot(root, 1), batch_size=250)

    assert result["tracks_deleted"] == 600
    assert result["delete_batches"] == 3
    assert result["max_batch_rows"] == 250
    assert result["max_existing_fingerprint_rows"] == 601
    assert result["max_incoming_path_rows"] == 1
    assert result["max_removed_path_rows"] == 250
    assert len(index.load_tracks([root])) == 1


def test_p14l4b1_existing_fingerprint_query_does_not_fetchall(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    snapshot = _snapshot(root, 8)
    index.replace_scan([root], snapshot)

    original_connect = index._connect
    observed = {"streamed": 0}

    class CursorProxy:
        def __init__(self, cursor, *, guarded: bool):
            self._cursor = cursor
            self._guarded = guarded

        def __iter__(self):
            if self._guarded:
                observed["streamed"] += 1
            return iter(self._cursor)

        def fetchall(self):
            if self._guarded:
                raise AssertionError(
                    "existing fingerprint comparison must stream rows"
                )
            return self._cursor.fetchall()

        def __getattr__(self, name):
            return getattr(self._cursor, name)

    class ConnectionProxy:
        def __init__(self, connection):
            self._connection = connection

        def __enter__(self):
            self._connection.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            return self._connection.__exit__(exc_type, exc, tb)

        def execute(self, query, params=()):
            cursor = self._connection.execute(query, params)
            normalized = " ".join(str(query).split())
            guarded = (
                "SELECT relative_path, size, mtime_ns FROM tracks"
                in normalized
            )
            return CursorProxy(cursor, guarded=guarded)

        def executemany(self, query, params):
            return self._connection.executemany(query, params)

        def rollback(self):
            return self._connection.rollback()

        def __getattr__(self, name):
            return getattr(self._connection, name)

    monkeypatch.setattr(
        index,
        "_connect",
        lambda: ConnectionProxy(original_connect()),
    )

    result = index.replace_scan([root], snapshot)

    assert observed["streamed"] == 1
    assert result["tracks_written"] == 0
    assert result["tracks_reused"] == 8
    assert result["tracks_deleted"] == 0


def test_p14l4b2b_preserved_directory_reuses_rows_without_preserved_set(
    tmp_path: Path,
):
    root = tmp_path / "music"
    album = root / "Album"
    other = root / "Other"
    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")

    tracks = [
        _track(album / "one.flac", 1),
        _track(album / "two.flac", 2),
        _track(other / "three.flac", 3),
    ]
    initial = {
        "tracks": tracks,
        "index_tracks": tracks,
        "index_records": [
            {
                "track": track,
                "size": index + 1,
                "mtime_ns": 1_000 + index,
            }
            for index, track in enumerate(tracks)
        ],
        "root_states": [
            {"path": str(root), "available": True, "complete": True}
        ],
        "metrics": {"tracks_indexed": 3},
        "cancelled": False,
    }
    index.replace_scan([root], initial)

    preserved_only = {
        "tracks": [],
        "index_tracks": [],
        "index_records": [],
        "preserve_directories": [
            {
                "path": str(album),
                "root_path": str(root),
                "file_count": 2,
            }
        ],
        "root_states": [
            {"path": str(root), "available": True, "complete": True}
        ],
        "metrics": {"tracks_indexed": 2},
        "cancelled": False,
    }

    result = index.replace_scan([root], preserved_only)

    assert result["tracks_written"] == 0
    assert result["tracks_reused"] == 2
    assert result["tracks_deleted"] == 1
    assert {row["title"] for row in index.load_tracks([root])} == {
        "Track 1",
        "Track 2",
    }
