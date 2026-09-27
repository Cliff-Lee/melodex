from pathlib import Path

from melodex.metadata import MetadataIdentity, RichMetadataService


def test_discography_does_not_download_covers_eagerly(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    calls = []
    svc._download_artwork = lambda url: calls.append(url) or None
    svc._mb_json = lambda *args, **kwargs: {
        "release-groups": [
            {"id": "rg1", "title": "Alpha", "primary-type": "Album", "first-release-date": "1999-01-01"},
            {"id": "rg2", "title": "Beta", "primary-type": "Album", "first-release-date": "2004-01-01"},
        ]
    }
    rows = svc.discography("artist-1")
    assert calls == []
    assert rows[0]["cover_path"] == ""
    assert rows[0]["cover_url"].endswith("/release-group/rg1/front-250")


def test_cover_hydration_is_separate_and_limited(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    calls = []
    def fake_download(url):
        calls.append(url)
        return tmp_path / f"cover-{len(calls)}.jpg"
    svc._download_artwork = fake_download
    rows = [
        {"id": f"rg{i}", "title": str(i), "cover_url": f"https://example/{i}", "cover_path": ""}
        for i in range(5)
    ]
    out = svc.hydrate_discography_covers(rows, limit=2)
    assert len(calls) == 2
    assert out[0]["cover_path"].endswith("cover-1.jpg")
    assert out[1]["cover_path"].endswith("cover-2.jpg")
    assert out[2]["cover_path"] == ""


def test_identity_stage_does_not_call_artist_or_discography(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    svc.local_lyrics = lambda track: {"text": "hello", "synced": [], "source": "test"}
    svc.identify = lambda track: MetadataIdentity(
        recording_mbid="rec", artist_mbid="artist", title="Starlight", artist="Westlife", album="Wild Dreams", score=.99
    )
    svc.artist_info = lambda mbid: (_ for _ in ()).throw(AssertionError("artist_info must not run in identity stage"))
    svc.discography = lambda mbid: (_ for _ in ()).throw(AssertionError("discography must not run in identity stage"))
    out = svc.enrich_identity({"artist": "Westlife", "title": "Starlight", "album": "Wild Dreams"})
    assert out["identity"]["recording_mbid"] == "rec"
    assert out["identity"]["score"] == .99
    assert out["lyrics"]["text"] == "hello"


def test_staged_helpers_are_independent(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    identity = {
        "recording_mbid": "rec",
        "artist_mbid": "artist",
        "release_mbid": "rel",
        "release_group_mbid": "rg",
        "artist": "Westlife",
        "title": "Starlight",
        "album": "Wild Dreams",
        "score": .99,
    }
    svc.artist_info = lambda mbid: {"name": "Westlife"}
    svc.recording_credits = lambda mbid: [{"role": "performer", "name": "Westlife"}]
    svc.discography = lambda mbid: [{"id": "rg", "title": "Wild Dreams"}]
    assert svc.enrich_artist(identity)["artist"]["name"] == "Westlife"
    assert svc.enrich_credits(identity)["credits"][0]["role"] == "performer"
    assert svc.enrich_discography(identity)["discography"][0]["title"] == "Wild Dreams"
