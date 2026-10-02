from __future__ import annotations

import time
from pathlib import Path

import melodex.providers.local_files as local_files
from melodex.providers.local_files import LocalFilesProvider


def _metadata(path: Path) -> dict[str, object]:
    time.sleep(0.001)
    return {
        "provider_id": "local",
        "track_id": str(path),
        "rel": f"local:{path}",
        "title": path.stem,
        "artist": "Pipeline Artist",
        "album": "Pipeline Album",
        "duration": 180.0,
        "local_path": str(path),
        "source": "local",
    }


def test_p10c_pipeline_queue_is_bounded(monkeypatch, tmp_path: Path):
    root = tmp_path / "music"
    root.mkdir()
    names = [f"track-{index:04d}.flac" for index in range(700)]

    monkeypatch.setattr(
        local_files.os,
        "walk",
        lambda _root, onerror=None: [(str(root), [], names)],
    )
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata),
    )

    # Avoid creating hundreds of files while still exercising the producer's
    # stat/fingerprint path.
    class _Stat:
        st_size = 1
        st_mtime = 1.0
        st_mtime_ns = 1_000_000_000

    monkeypatch.setattr(Path, "stat", lambda self: _Stat())

    provider = LocalFilesProvider(scan_on_init=False)
    snapshot = provider.scan_snapshot([root])

    metrics = snapshot["metrics"]
    assert snapshot["cancelled"] is False
    assert len(snapshot["tracks"]) == 700
    assert metrics["bounded_pipeline"] is True
    assert metrics["pipeline_queue_capacity"] == 256
    assert 0 < metrics["pipeline_max_queue_depth"] <= 256
    # A deliberately slower consumer should eventually force the discovery
    # producer to wait instead of allowing an unbounded backlog.
    assert metrics["pipeline_backpressure_events"] > 0


def test_p10c_progress_reports_queue_without_paths(monkeypatch, tmp_path: Path):
    root = tmp_path / "private-music"
    root.mkdir()

    monkeypatch.setattr(
        local_files.os,
        "walk",
        lambda _root, onerror=None: [(str(root), [], ["one.flac"])],
    )
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(lambda path: {
            "provider_id": "local",
            "track_id": str(path),
            "rel": f"local:{path}",
            "title": path.stem,
            "artist": "Artist",
            "album": "Album",
            "duration": 1.0,
            "local_path": str(path),
            "source": "local",
        }),
    )

    class _Stat:
        st_size = 1
        st_mtime = 1.0
        st_mtime_ns = 1_000_000_000

    monkeypatch.setattr(Path, "stat", lambda self: _Stat())

    events: list[dict[str, object]] = []
    provider = LocalFilesProvider(scan_on_init=False)
    provider.scan_snapshot([root], progress=lambda event: events.append(dict(event)))

    queue_events = [event for event in events if "queue_capacity" in event]
    assert queue_events
    assert all(int(event["queue_depth"]) <= int(event["queue_capacity"]) for event in queue_events)
    assert str(root) not in repr(events)
