from __future__ import annotations

import sys
import types
from pathlib import Path

from melodex.providers.local_files import LocalFilesProvider


class _Info:
    length = 245.0


class _Audio:
    info = _Info()
    tags = {
        "title": ["Tagged Song"],
        "artist": ["Tagged Artist"],
        "album": ["Tagged Album"],
        "musicbrainz_recordingid": ["recording-id"],
        "musicbrainz_artistid": ["artist-id"],
        "musicbrainz_albumid": ["release-id"],
        "musicbrainz_releasegroupid": ["release-group-id"],
    }


def test_local_metadata_preserves_easy_musicbrainz_ids(monkeypatch, tmp_path: Path):
    fake = types.ModuleType("mutagen")
    fake.File = lambda path, easy=True: _Audio()
    monkeypatch.setitem(sys.modules, "mutagen", fake)

    path = tmp_path / "song.flac"
    path.write_bytes(b"not real audio; File() is stubbed")

    track = LocalFilesProvider._metadata(path)

    assert track["title"] == "Tagged Song"
    assert track["artist"] == "Tagged Artist"
    assert track["album"] == "Tagged Album"
    assert track["musicbrainz_recording_id"] == "recording-id"
    assert track["musicbrainz_artist_id"] == "artist-id"
    assert track["musicbrainz_release_id"] == "release-id"
    assert track["musicbrainz_release_group_id"] == "release-group-id"
