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
