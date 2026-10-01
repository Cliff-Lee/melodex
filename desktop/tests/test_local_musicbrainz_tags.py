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



def test_local_metadata_override_applies_without_rewriting_file(tmp_path: Path):
    music = tmp_path / "music"
    music.mkdir()
    path = music / "mystery.mp3"
    original_bytes = b"not really audio"
    path.write_bytes(original_bytes)

    provider = LocalFilesProvider(
        [music],
        overrides={
            str(path.resolve()): {
                "artist": "Known Artist",
                "title": "Known Track",
                "album": "Known Album",
                "year": 1999,
            }
        },
    )

    assert len(provider.tracks) == 1
    track = provider.tracks[0]
    assert track["artist"] == "Known Artist"
    assert track["title"] == "Known Track"
    assert track["album"] == "Known Album"
    assert track["year"] == 1999
    assert path.read_bytes() == original_bytes


def test_local_metadata_override_survives_rescan(tmp_path: Path):
    music = tmp_path / "music"
    music.mkdir()
    path = music / "mystery.mp3"
    path.write_bytes(b"not really audio")

    provider = LocalFilesProvider([music])
    updated = provider.set_metadata_override(
        path,
        {"artist": "Corrected Artist", "album": "Corrected Album"},
    )
    assert updated["artist"] == "Corrected Artist"

    provider.scan()
    track = provider.tracks[0]
    assert track["artist"] == "Corrected Artist"
    assert track["album"] == "Corrected Album"
