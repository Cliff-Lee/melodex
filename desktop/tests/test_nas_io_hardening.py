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
        "artist": "NAS Test Artist",
        "album": path.parent.name,
        "duration": 1.0,
        "source": "local",
    }


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
