from pathlib import Path

from melodex.metadata import RichMetadataService, parse_lrc, track_key


def test_lrc_multiple_timestamp_formats():
    rows = parse_lrc("[00:01.50]One\n[1:02.345]Two\n[00:03][00:04]Repeat")
    assert rows[0] == {"time_ms": 1500, "text": "One"}
    assert any(x["time_ms"] == 62345 and x["text"] == "Two" for x in rows)
    assert [x["time_ms"] for x in rows if x["text"] == "Repeat"] == [3000, 4000]


def test_sidecar_lrc_is_local_first(tmp_path: Path):
    audio = tmp_path / "Track.mp3"; audio.write_bytes(b"not audio")
    (tmp_path / "Track.lrc").write_text("[00:01.00]Hello\n[00:02.00]world", "utf-8")
    svc = RichMetadataService(tmp_path / "data")
    out = svc.local_lyrics({"local_path": str(audio)})
    assert out["source"] == "Track.lrc"
    assert out["text"] == "Hello\nworld"
    assert len(out["synced"]) == 2


def test_txt_sidecar_supported(tmp_path: Path):
    audio = tmp_path / "Track.flac"; audio.write_bytes(b"not audio")
    (tmp_path / "Track.txt").write_text("plain\nlyrics", "utf-8")
    svc = RichMetadataService(tmp_path / "data")
    out = svc.local_lyrics({"local_path": str(audio)})
    assert out["text"] == "plain\nlyrics"
    assert out["synced"] == []


def test_track_key_prefers_provider_identity():
    assert track_key({"provider_id":"local","track_id":"abc","artist":"A","title":"B"}) == "local:abc"
    assert track_key({"artist":"A","title":"B","album":"C"}) == "a|b|c"


def test_musicbrainz_match_parsing_without_network(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    svc._mb_json = lambda *args, **kwargs: {
        "recordings": [{
            "id":"rec-1", "title":"LSD",
            "artist-credit":[{"name":"Hallucinogen","artist":{"id":"artist-1","name":"Hallucinogen"}}],
            "releases":[{"id":"rel-1","title":"Twisted","date":"1995-10-16","release-group":{"id":"rg-1"}}]
        }]
    }
    ident = svc.identify({"artist":"Hallucinogen","title":"LSD","album":"Twisted"})
    assert ident.recording_mbid == "rec-1"
    assert ident.artist_mbid == "artist-1"
    assert ident.release_group_mbid == "rg-1"
    assert ident.score > 0.9



def test_local_artwork_prefers_sidecar_without_network(tmp_path: Path):
    album = tmp_path / "Album"
    album.mkdir()
    audio = album / "01 Track.mp3"
    audio.write_bytes(b"not audio")
    cover = album / "Cover.JPG"
    cover.write_bytes(b"fake image bytes")

    svc = RichMetadataService(tmp_path / "data")
    out = svc.local_artwork({"local_path": str(audio)})
    assert out["path"] == str(cover)
    assert out["source"] == "local cover file"
    assert out["source_url"] == ""



def test_local_artwork_checks_parent_of_multidisc_folder(tmp_path: Path):
    album = tmp_path / "Box Set"
    disc = album / "Disc 1"
    disc.mkdir(parents=True)
    audio = disc / "01 Track.mp3"
    audio.write_bytes(b"not audio")
    cover = album / "cover.jpg"
    cover.write_bytes(b"fake image bytes")

    svc = RichMetadataService(tmp_path / "data")
    out = svc.local_artwork({"local_path": str(audio)})
    assert out["path"] == str(cover)
    assert out["source"] == "local cover file"



def test_online_artwork_association_survives_new_metadata_service(tmp_path: Path):
    audio = tmp_path / "Artist" / "Album" / "01 Track.mp3"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"not audio")
    cached = tmp_path / "data" / "metadata-cache" / "artwork" / "remembered.jpg"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"image")
    track = {
        "provider_id": "local",
        "track_id": str(audio),
        "local_path": str(audio),
        "artist": "Artist",
        "album": "Album",
        "year": 2001,
        "title": "Track",
    }

    first = RichMetadataService(tmp_path / "data")
    first.remember_artwork(
        track,
        cached,
        source="Cover Art Archive",
        source_url="https://example.invalid/cover",
    )

    second = RichMetadataService(tmp_path / "data")
    result = second.local_artwork(track)
    assert result["path"] == str(cached)
    assert result["source"] == "Cover Art Archive"


def test_identify_can_match_unknown_artist_from_track_and_album(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    seen = {}

    def fake_mb(path, params, max_age):
        seen["query"] = params["query"]
        return {
            "recordings": [{
                "id": "rec-2",
                "title": "Known Song",
                "artist-credit": [{
                    "name": "Recovered Artist",
                    "artist": {"id": "artist-2", "name": "Recovered Artist"},
                }],
                "releases": [{
                    "id": "rel-2",
                    "title": "Known Album",
                    "date": "2007-01-01",
                    "release-group": {"id": "rg-2"},
                }],
            }]
        }

    svc._mb_json = fake_mb
    ident = svc.identify({
        "artist": "Unknown artist",
        "title": "Known Song",
        "album": "Known Album",
    })
    assert 'artist:"Unknown artist"' not in seen["query"]
    assert 'release:"Known Album"' in seen["query"]
    assert ident.artist == "Recovered Artist"
    assert ident.release_group_mbid == "rg-2"
