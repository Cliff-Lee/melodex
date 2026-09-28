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
