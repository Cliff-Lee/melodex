from __future__ import annotations

from pathlib import Path
import time

import melodex.providers.local_files as local_files
from melodex.library_index import LocalLibraryIndex
from melodex.providers.local_files import LocalFilesProvider


def _metadata(path: Path) -> dict[str, object]:
    return {
        "provider_id": "local",
        "track_id": str(path),
        "rel": f"local:{path}",
        "local_path": str(path),
        "title": path.stem,
        "artist": "NAS Test Artist",
        "album": path.parent.name,
        "duration": 1.0,
        "source": "local",
    }


def test_p13f_network_root_is_persisted_without_filesystem_probe(
    monkeypatch,
    tmp_path: Path,
):
    from melodex.provider_manager import ProviderManager

    root = tmp_path / "nas-not-mounted"
    calls = []
    original_stat = Path.stat

    def tracked_stat(path, *args, **kwargs):
        if path == root:
            calls.append(str(path))
            raise AssertionError("source acceptance must not probe the NAS")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", tracked_stat)
    manager = ProviderManager(tmp_path / "data")
    try:
        assert manager.configure_local_roots([root]) == [root]
        assert manager.local_roots() == [root]
        assert calls == []
    finally:
        manager.close()


def test_p11d_transient_scandir_failure_retries_and_completes(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    (root / "one.flac").write_bytes(b"x")

    real_scandir = local_files.os.scandir
    attempts = 0

    def flaky_scandir(path):
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise OSError("temporary SMB hiccup")
        return real_scandir(path)

    monkeypatch.setattr(local_files.os, "scandir", flaky_scandir)
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata),
    )

    snapshot = LocalFilesProvider(scan_on_init=False).scan_snapshot([root])

    assert snapshot["cancelled"] is False
    assert len(snapshot["tracks"]) == 1
    assert snapshot["root_states"] == [
        {
            "path": str(root),
            "available": True,
            "complete": True,
            "walk_errors": 0,
            "io_retries": 2,
        }
    ]
    assert snapshot["metrics"]["io_retries"] == 2
    assert snapshot["metrics"]["incomplete_roots"] == 0


def test_p13f_unavailable_root_does_not_block_another_selected_root(
    monkeypatch,
    tmp_path: Path,
):
    unavailable = tmp_path / "offline-nas"
    healthy = tmp_path / "healthy-music"
    album = healthy / "Artist" / "Album"
    album.mkdir(parents=True)
    (album / "one.flac").write_bytes(b"x")
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata),
    )
    discovered = []

    snapshot = LocalFilesProvider(scan_on_init=False).scan_snapshot(
        [unavailable, healthy],
        on_first_audio_file=discovered.append,
    )

    assert [row["available"] for row in snapshot["root_states"]] == [False, True]
    assert discovered
    assert discovered[0]["local_path"] == str(album / "one.flac")
    assert snapshot["root_states"][1]["complete"] is True


def test_p13f_stalled_subtree_degrades_locally_and_other_music_is_found(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    stalled = root / "00-stalled-archive"
    healthy = root / "01-new-music" / "Album"
    stalled.mkdir(parents=True)
    healthy.mkdir(parents=True)
    (healthy / "one.flac").write_bytes(b"x")
    real_scandir = local_files.os.scandir
    stalled_path = str(stalled)

    def delayed_stalled_scandir(path):
        if str(path) == stalled_path:
            time.sleep(0.08)
            raise OSError("simulated NAS subtree timeout")
        return real_scandir(path)

    monkeypatch.setattr(local_files.os, "scandir", delayed_stalled_scandir)
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata),
    )
    discovered = []

    snapshot = LocalFilesProvider(scan_on_init=False).scan_snapshot(
        [root],
        on_first_audio_file=discovered.append,
    )

    assert discovered
    assert discovered[0]["local_path"] == str(healthy / "one.flac")
    state = snapshot["root_states"][0]
    assert state["available"] is True
    assert state["complete"] is False
    assert state["walk_errors"] >= 1


def test_p11d_exhausted_scandir_retries_preserve_root_as_incomplete(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    (root / "one.flac").write_bytes(b"x")

    def unavailable_scandir(_path):
        raise OSError("NAS timed out")

    monkeypatch.setattr(local_files.os, "scandir", unavailable_scandir)
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata),
    )

    snapshot = LocalFilesProvider(scan_on_init=False).scan_snapshot([root])

    state = snapshot["root_states"][0]
    assert state["available"] is True
    assert state["complete"] is False
    assert state["walk_errors"] == 1
    assert state["io_retries"] == 2
    assert snapshot["tracks"] == []
    assert snapshot["changes"]["incomplete_roots"] == 1
    assert snapshot["metrics"]["incomplete_roots"] == 1
    assert snapshot["metrics"]["io_retries"] == 2


def test_p11d_scandir_skips_stat_for_non_audio_sidecars(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    track = root / "one.flac"
    track.write_bytes(b"x")
    real_stat = track.stat()
    stat_calls: list[str] = []

    class Entry:
        def __init__(self, name: str):
            self.name = name
            self.path = str(root / name)

        def is_dir(self, *, follow_symlinks: bool = False) -> bool:
            assert follow_symlinks is False
            return False

        def stat(self):
            stat_calls.append(self.name)
            if self.name != "one.flac":
                raise AssertionError("non-audio sidecars must not be stat'ed")
            return real_stat

    class Scandir:
        def __init__(self):
            self._entries = [Entry("cover.jpg"), Entry("notes.txt"), Entry("one.flac")]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __iter__(self):
            return iter(self._entries)

    monkeypatch.setattr(local_files.os, "scandir", lambda _path: Scandir())
    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata),
    )

    snapshot = LocalFilesProvider(scan_on_init=False).scan_snapshot([root])

    assert len(snapshot["tracks"]) == 1
    assert stat_calls == ["one.flac"]
    assert snapshot["metrics"]["stat_failures"] == 0


def test_p11d_incomplete_network_rescan_keeps_last_committed_index(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path / "music"
    root.mkdir()
    track = root / "one.flac"
    track.write_bytes(b"x")

    monkeypatch.setattr(
        LocalFilesProvider,
        "_metadata",
        staticmethod(_metadata),
    )
    provider = LocalFilesProvider(scan_on_init=False)
    index = LocalLibraryIndex(tmp_path / "library.sqlite3")

    first = provider.scan_snapshot([root])
    first_persistence = index.replace_scan([root], first)
    assert first_persistence["tracks_persisted"] == 1
    assert len(index.load_tracks([root])) == 1

    monkeypatch.setattr(
        local_files.os,
        "scandir",
        lambda _path: (_ for _ in ()).throw(OSError("SMB share stalled")),
    )
    interrupted = provider.scan_snapshot(
        [root],
        cached_entries=index.load_scan_cache([root]),
        cached_directories=index.load_directory_manifests([root]),
        collect_tracks=False,
    )
    assert interrupted["root_states"][0]["complete"] is False

    persistence = index.replace_scan([root], interrupted)

    assert persistence["roots_persisted"] == 0
    assert persistence["roots_incomplete"] == 1
    preserved = index.load_tracks([root])
    assert len(preserved) == 1
    assert preserved[0]["artist"] == "NAS Test Artist"
