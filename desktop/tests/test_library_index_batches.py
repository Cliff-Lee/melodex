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
    assert len(index.load_tracks([root])) == 1
