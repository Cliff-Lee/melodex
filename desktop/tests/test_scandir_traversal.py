from __future__ import annotations

from pathlib import Path

import melodex.providers.local_files as local_files
from melodex.providers.local_files import LocalFilesProvider


def _metadata(path: Path) -> dict[str, object]:
    return {
        "provider_id": "local",
        "track_id": str(path),
        "rel": f"local:{path}",
        "local_path": str(path),
        "title": path.stem,
        "artist": "Traversal Artist",
        "album": path.parent.name,
        "duration": 1.0,
        "source": "local",
    }


def test_p10j_real_filesystem_uses_scandir_fast_path(monkeypatch, tmp_path: Path):
    root = tmp_path / "music"
    album = root / "Album"
    album.mkdir(parents=True)
    (album / "01.flac").write_bytes(b"a")
    (album / "02.flac").write_bytes(b"bb")
    (album / "notes.txt").write_text("ignore", encoding="utf-8")

    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata),
    )
    provider = LocalFilesProvider(scan_on_init=False)
    snapshot = provider.scan_snapshot([root])

    assert len(snapshot["tracks"]) == 2
    assert snapshot["metrics"]["scandir_enabled"] is True
    assert snapshot["metrics"]["scandir_directories"] >= 2
    assert snapshot["metrics"]["stat_failures"] == 0


def test_p10j_custom_walk_preserves_legacy_probe_path(monkeypatch, tmp_path: Path):
    root = tmp_path / "music"
    root.mkdir()
    track = root / "one.flac"
    track.write_bytes(b"x")

    monkeypatch.setattr(
        local_files.os,
        "walk",
        lambda _root, onerror=None: [(str(root), [], [track.name])],
    )
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata),
    )

    provider = LocalFilesProvider(scan_on_init=False)
    snapshot = provider.scan_snapshot([root])

    assert len(snapshot["tracks"]) == 1
    assert snapshot["metrics"]["scandir_enabled"] is False
    assert snapshot["metrics"]["scandir_directories"] == 0


def test_p10j_scandir_rescan_keeps_fingerprint_reuse(monkeypatch, tmp_path: Path):
    root = tmp_path / "music"
    root.mkdir()
    track = root / "one.flac"
    track.write_bytes(b"x")

    calls: list[str] = []

    def counted(path: Path):
        calls.append(path.name)
        return _metadata(path)

    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(counted),
    )
    provider = LocalFilesProvider(scan_on_init=False)
    first = provider.scan_snapshot([root])

    cache = {
        provider._override_key(record["track"]["local_path"]): {
            "track": record["track"],
            "size": record["size"],
            "mtime_ns": record["mtime_ns"],
        }
        for record in first["index_records"]
    }
    calls.clear()

    second = provider.scan_snapshot([root], cached_entries=cache)

    assert calls == []
    assert second["changes"]["unchanged"] == 1
    assert second["metrics"]["scandir_enabled"] is True


def test_p14l3a_index_backed_cache_skips_recanonicalization(monkeypatch):
    provider = LocalFilesProvider(scan_on_init=False)
    calls: list[str] = []
    original = provider._override_key

    def counted(path):
        calls.append(str(path))
        return original(path)

    monkeypatch.setattr(provider, "_override_key", counted)
    entries = {"/music/one.flac": {"track": {"title": "One"}}}
    directories = {"/music": {"manifest": "cached", "file_count": 1}}

    fast = provider.scan_snapshot(
        [],
        cached_entries=entries,
        cached_directories=directories,
        cache_keys_canonical=True,
    )

    assert calls == []
    assert fast["metrics"]["cache_keys_canonical"] is True
    assert fast["metrics"]["cache_key_normalizations"] == 0

    calls.clear()
    defensive = provider.scan_snapshot(
        [],
        cached_entries=entries,
        cached_directories=directories,
    )

    # Two calls normalise the supplied cache keys; the third is the existing
    # defensive parent-directory check in the deletion sweep.
    assert len(calls) == 3
    assert defensive["metrics"]["cache_keys_canonical"] is False
    assert defensive["metrics"]["cache_key_normalizations"] == 2


def test_p14l3c_deletion_sweep_normalizes_each_cached_root_once():
    provider = LocalFilesProvider(scan_on_init=False)
    entries = {
        f"/music/{index:02d}.flac": {
            "track": {"title": str(index)},
            "root_path": "/music",
        }
        for index in range(8)
    }

    snapshot = provider.scan_snapshot(
        [],
        cached_entries=entries,
        cache_keys_canonical=True,
    )

    assert snapshot["changes"]["removed"] == 0
    assert snapshot["metrics"]["cached_root_normalizations"] == 1
