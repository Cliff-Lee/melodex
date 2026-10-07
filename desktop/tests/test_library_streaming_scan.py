from __future__ import annotations

import inspect
from pathlib import Path

import melodex.providers.local_files as local_files
from melodex.provider_manager import ProviderManager
from melodex.providers.local_files import LocalFilesProvider


def _metadata_row(path: Path) -> dict[str, object]:
    return {
        "provider_id": "local",
        "track_id": str(path),
        "rel": f"local:{path}",
        "title": path.stem,
        "artist": "Streaming Artist",
        "album": "Streaming Album",
        "duration": 180.0,
        "local_path": str(path),
        "source": "local",
    }


def test_p10b_metadata_is_processed_before_walk_finishes(monkeypatch, tmp_path: Path):
    import threading

    root = tmp_path / "music"
    root.mkdir()
    first = root / "first" / "one.flac"
    second = root / "second" / "two.flac"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    metadata_calls: list[str] = []
    first_metadata_done = threading.Event()

    def walk(_root, onerror=None):
        yield str(first.parent), [], [first.name]
        # P10b/P10c may let discovery run ahead, but metadata must be able to
        # progress before traversal is allowed to finish.
        assert first_metadata_done.wait(timeout=2)
        yield str(second.parent), [], [second.name]

    monkeypatch.setattr(local_files.os, "walk", walk)

    def metadata(path: Path):
        metadata_calls.append(path.name)
        if path.name == first.name:
            first_metadata_done.set()
        return _metadata_row(path)

    monkeypatch.setattr(LocalFilesProvider, "_metadata", staticmethod(metadata))

    provider = LocalFilesProvider(scan_on_init=False)
    snapshot = provider.scan_snapshot([root])

    assert metadata_calls == ["one.flac", "two.flac"]
    assert len(snapshot["tracks"]) == 2
    assert snapshot["metrics"]["streaming_discovery"] is True
    assert snapshot["metrics"]["discovery_buffer_rows"] == 0


def test_first_directory_and_audio_discovery_are_reported_immediately(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    album = root / "album"

    def walk(_root, onerror=None):
        yield str(album), [], ["first.flac"]

    monkeypatch.setattr(local_files.os, "walk", walk)
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata_row),
    )
    progress: list[dict[str, object]] = []
    provider = LocalFilesProvider(scan_on_init=False)
    provider.scan_snapshot([root], progress=progress.append)

    first_directory = next(row for row in progress if row["directories_seen"] == 1)
    first_audio = next(row for row in progress if row["audio_files_seen"] == 1)
    assert first_directory["phase"] == "discovering"
    assert first_audio["phase"] == "discovering"


def test_first_playable_path_is_emitted_before_recursive_scan_finishes(
    monkeypatch,
    tmp_path: Path,
):
    import threading

    root = tmp_path / "music"
    root.mkdir()
    first = root / "album" / "first.flac"
    later = root / "deep" / "later.flac"
    first.parent.mkdir()
    later.parent.mkdir()
    first.write_bytes(b"first")
    later.write_bytes(b"later")
    continue_walk = threading.Event()
    first_track_ready = threading.Event()
    scan_finished = threading.Event()
    emitted: list[dict[str, object]] = []

    def walk(_root, onerror=None):
        yield str(first.parent), [], [first.name]
        assert continue_walk.wait(timeout=2)
        yield str(later.parent), [], [later.name]

    monkeypatch.setattr(local_files.os, "walk", walk)
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata_row),
    )

    def on_first(track: dict[str, object]) -> None:
        emitted.append(track)
        first_track_ready.set()

    def scan() -> None:
        LocalFilesProvider(scan_on_init=False).scan_snapshot(
            [root],
            on_first_audio_file=on_first,
        )
        scan_finished.set()

    worker = threading.Thread(target=scan)
    worker.start()
    assert first_track_ready.wait(timeout=2)
    assert not scan_finished.is_set()
    assert emitted[0]["local_path"] == str(first)
    assert emitted[0]["provisional"] is True

    continue_walk.set()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert scan_finished.is_set()


def test_initial_provisional_pool_is_capped_at_twenty_tracks(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    names = [f"track-{index:02d}.flac" for index in range(25)]

    monkeypatch.setattr(
        local_files.os,
        "walk",
        lambda _root, onerror=None: [(str(root), [], names)],
    )
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata_row),
    )
    provisional: list[dict[str, object]] = []
    LocalFilesProvider(scan_on_init=False).scan_snapshot(
        [root],
        on_first_audio_file=provisional.append,
    )

    assert len(provisional) == 20
    assert provisional[0]["title"] == "track-00"
    assert provisional[-1]["title"] == "track-19"


def test_p10b_scan_source_has_no_collection_wide_discovered_list():
    source = inspect.getsource(LocalFilesProvider.scan_snapshot)

    assert "discovered: list" not in source
    assert "streaming_discovery" in source


def test_p10b_incomplete_changed_root_discards_streamed_rows(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "nas"
    root.mkdir()
    first_path = root / "first.flac"
    hidden_path = root / "hidden.flac"
    first_path.write_bytes(b"before")
    hidden_path.write_bytes(b"hidden")

    manager = ProviderManager(tmp_path)
    try:
        manager.configure_local_roots([root])
        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(_metadata_row),
        )
        initial = manager.scan_local_roots_snapshot([root])
        manager.persist_local_scan_snapshot([root], initial)

        # Force the first file to require a metadata read, then simulate a NAS
        # traversal error after that streamed work has already happened.
        first_path.write_bytes(b"changed-and-longer")

        def partial_walk(_root, onerror=None):
            yield str(root), [], ["first.flac"]
            if onerror is not None:
                onerror(PermissionError("simulated NAS failure"))

        monkeypatch.setattr(local_files.os, "walk", partial_walk)
        metadata_calls: list[str] = []

        def counted_metadata(path: Path):
            metadata_calls.append(path.name)
            return _metadata_row(path)

        monkeypatch.setattr(
            LocalFilesProvider,
            "_metadata",
            staticmethod(counted_metadata),
        )

        partial = manager.scan_local_roots_snapshot([root])

        assert metadata_calls == ["first.flac"]
        assert partial["changes"]["incomplete_roots"] == 1
        assert partial["changes"]["removed"] == 0
        assert partial["tracks"] == []
        assert "index_tracks" not in partial
        assert partial["index_records"] == []

        manager.persist_local_scan_snapshot([root], partial)
        stored = manager.library_index.load_tracks([root])
        assert {Path(row["local_path"]).name for row in stored} == {
            "first.flac",
            "hidden.flac",
        }
    finally:
        manager.close()
