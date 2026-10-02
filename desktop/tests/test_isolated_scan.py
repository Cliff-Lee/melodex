from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

from melodex.isolated_scan import IsolatedLibraryScanRunner
from melodex.library_index import LocalLibraryIndex
from melodex.library_scan import ScanControl


def test_isolated_scan_worker_round_trip(tmp_path: Path):
    root = tmp_path / "music"
    root.mkdir()
    track = root / "example.flac"
    # Invalid audio is fine for this protocol test: LocalFilesProvider falls
    # back to filename metadata when Mutagen cannot parse the file.
    track.write_bytes(b"not a real flac")

    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])
    progress = []

    runner = IsolatedLibraryScanRunner(
        index.path,
        cancel_grace_seconds=0.25,
    )
    snapshot = runner.run(
        [root],
        progress=lambda payload: progress.append(dict(payload)),
    )

    assert snapshot["cancelled"] is False
    assert len(snapshot["tracks"]) == 1
    assert Path(snapshot["tracks"][0]["local_path"]).name == "example.flac"
    assert snapshot["changes"]["added"] == 1
    assert snapshot["changes"]["metadata_reads"] == 1
    phases = [row.get("phase") for row in progress]
    assert phases[0] == "discovering"
    assert "metadata" in phases
    assert phases[-1] == "complete"


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO requires POSIX")
def test_isolated_scan_can_hard_cancel_blocked_file_open(tmp_path: Path):
    root = tmp_path / "nas"
    root.mkdir()
    blocked = root / "blocked.flac"
    os.mkfifo(blocked)

    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])
    control = ScanControl()
    metadata_phase = threading.Event()
    holder = {}

    def progress(payload):
        if (
            str(payload.get("phase") or "") == "metadata"
            and int(payload.get("total") or 0) == 1
        ):
            metadata_phase.set()

    runner = IsolatedLibraryScanRunner(
        index.path,
        cancel_grace_seconds=0.20,
    )

    def work():
        try:
            holder["snapshot"] = runner.run(
                [root],
                progress=progress,
                control=control,
            )
        except BaseException as exc:
            holder["error"] = exc

    thread = threading.Thread(target=work, name="isolated-scan-test")
    thread.start()

    # The worker emits the metadata phase before opening the FIFO. Once this is
    # observed it is about to block inside the OS-level file open, which cannot
    # be interrupted cooperatively from Python.
    assert metadata_phase.wait(timeout=5), holder

    cancelled_at = time.monotonic()
    control.cancel()
    thread.join(timeout=3)
    elapsed = time.monotonic() - cancelled_at

    assert not thread.is_alive()
    assert "error" not in holder
    snapshot = holder["snapshot"]
    assert snapshot["cancelled"] is True
    assert snapshot["hard_cancelled"] is True
    assert snapshot["tracks"] == []
    assert elapsed < 2.0


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO requires POSIX")
def test_hard_cancel_never_changes_persistent_index(tmp_path: Path):
    root = tmp_path / "nas"
    root.mkdir()
    cached_path = root / "cached.flac"
    blocked_path = root / "blocked.flac"
    os.mkfifo(blocked_path)

    index = LocalLibraryIndex(tmp_path / "library-index.sqlite3")
    index.sync_roots([root])
    cached = {
        "provider_id": "local",
        "track_id": str(cached_path),
        "local_path": str(cached_path),
        "rel": f"local:{cached_path}",
        "title": "Cached Track",
        "artist": "Cached Artist",
        "album": "Cached Album",
        "source": "local",
    }
    index.replace_scan(
        [root],
        {
            "tracks": [cached],
            "index_tracks": [dict(cached)],
            "root_states": [{"path": str(root), "available": True}],
            "metrics": {"tracks_indexed": 1},
            "cancelled": False,
        },
    )

    control = ScanControl()
    metadata_phase = threading.Event()
    holder = {}
    runner = IsolatedLibraryScanRunner(
        index.path,
        cancel_grace_seconds=0.20,
    )

    def work():
        holder["snapshot"] = runner.run(
            [root],
            progress=lambda payload: (
                metadata_phase.set()
                if str(payload.get("phase") or "") == "metadata"
                else None
            ),
            control=control,
        )

    thread = threading.Thread(target=work)
    thread.start()
    assert metadata_phase.wait(timeout=5)
    control.cancel()
    thread.join(timeout=3)

    assert not thread.is_alive()
    assert holder["snapshot"]["cancelled"] is True

    # The parent only persists successful snapshots. Killing the scan process
    # cannot modify or partially replace the existing SQLite catalog.
    rows = index.load_tracks([root])
    assert len(rows) == 1
    assert rows[0]["title"] == "Cached Track"



def test_isolated_scan_error_redaction_hides_private_paths(tmp_path: Path):
    root = tmp_path / "Private Music" / "Collection"
    index_path = tmp_path / "Application Support" / "library-index.sqlite3"
    runner = IsolatedLibraryScanRunner(index_path)

    detail = (
        f"failed while opening {root / 'Artist' / 'secret.flac'} "
        f"using {index_path}"
    )
    safe = runner._safe_error_detail(detail, [root])

    assert str(root) not in safe
    assert str(index_path) not in safe
    assert "<music-root>" in safe
    assert "<library-index>" in safe
