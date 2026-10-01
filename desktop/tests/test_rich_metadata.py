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


def test_resolve_artist_by_name_uses_conservative_musicbrainz_match(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    calls = []

    def fake_mb(path, params, max_age):
        calls.append((path, dict(params)))
        if path == "artist/":
            return {
                "artists": [
                    {"id": "artist-good", "name": "Aesop Rock", "aliases": []},
                    {"id": "artist-bad", "name": "Aesop", "aliases": []},
                ]
            }
        if path == "artist/artist-good":
            return {
                "id": "artist-good",
                "name": "Aesop Rock",
                "sort-name": "Aesop Rock",
                "relations": [],
            }
        return {}

    svc._mb_json = fake_mb
    info = svc.resolve_artist("Aesop Rock")
    assert info["mbid"] == "artist-good"
    assert info["name"] == "Aesop Rock"
    assert info["match_score"] > 0.95
    assert calls[0][0] == "artist/"


def test_artist_photo_falls_back_to_wikipedia_lead_image(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    portrait = tmp_path / "portrait.jpg"
    portrait.write_bytes(b"portrait")

    def fake_remote(key, url, max_age=0):
        if key.startswith("wikidata:"):
            return {
                "entities": {
                    "Q123": {
                        "claims": {},
                        "sitelinks": {
                            "enwiki": {"title": "Bill Withers"}
                        },
                    }
                }
            }
        if key.startswith("wikipedia-pageimage:"):
            return {
                "query": {
                    "pages": [{
                        "title": "Bill Withers",
                        "pageimage": "Bill Withers 1976.jpg",
                    }]
                }
            }
        return {}

    svc._remote_json = fake_remote
    svc._commons_file_info = lambda image_name: {
        "image_url": "https://upload.wikimedia.org/example.jpg",
        "description_url": "https://commons.wikimedia.org/wiki/File:Bill_Withers_1976.jpg",
        "creator": "Photographer",
        "credit": "",
        "explicit_attribution": "",
        "license_name": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "usage_terms": "",
        "copyrighted": "",
        "attribution_required": "true",
    }
    svc._download_artwork = lambda url: portrait

    result = svc.artist_photo({
        "name": "Bill Withers",
        "wikidata_qid": "Q123",
        "links": [],
    })

    assert result["path"] == str(portrait)
    assert result["filename"] == "Bill Withers 1976.jpg"
    assert result["discovery_source"] == "Wikipedia lead image"
    assert result["source"] == "Wikimedia Commons"


def test_artist_photo_filename_rejects_album_and_logo_art():
    assert RichMetadataService._artist_photo_filename_ok("Brian Eno 2015.jpg")
    assert not RichMetadataService._artist_photo_filename_ok("Boards of Canada logo.svg")
    assert not RichMetadataService._artist_photo_filename_ok("Bonobo album cover.jpg")



def test_wikipedia_artist_search_accepts_music_page_for_single_word_stage_name(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")

    def fake_remote(key, url, max_age=0):
        if key.startswith("wikipedia-artist-search:"):
            return {
                "query": {
                    "search": [
                        {
                            "title": "Bonobo (musician)",
                            "snippet": "British musician, producer and DJ",
                        },
                        {
                            "title": "Bonobo",
                            "snippet": "A great ape species",
                        },
                    ]
                }
            }
        return {}

    svc._remote_json = fake_remote
    api, title = svc._wikipedia_artist_page_by_name({
        "name": "Bonobo",
        "type": "Person",
    })
    assert api.endswith("en.wikipedia.org/w/api.php")
    assert title == "Bonobo (musician)"


def test_wikipedia_artist_search_rejects_non_music_single_word_page(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")

    svc._remote_json = lambda key, url, max_age=0: {
        "query": {
            "search": [
                {
                    "title": "Air",
                    "snippet": "The mixture of gases that forms the atmosphere",
                }
            ]
        }
    }
    assert svc._wikipedia_artist_page_by_name({"name": "Air"}) == ("", "")


def test_artist_photo_can_use_artwork_extension_portrait(tmp_path: Path):
    portrait = tmp_path / "plugin-portrait.jpg"
    portrait.write_bytes(b"portrait")

    class Broker:
        def entity_ref(self, track, identity=None, entity_type="track"):
            assert entity_type == "artist"
            return {
                "entity_type": "artist",
                "hints": {"name": track["artist"]},
            }

        def lookup_artwork(self, subject, roles=None, max_results=8):
            assert "portrait" in roles
            return {
                "assets": [
                    {
                        "url": "https://example.invalid/brian-eno.jpg",
                        "role": "portrait",
                        "_extension_id": "org.example.portraits",
                        "provenance": {
                            "source_extension_id": "org.example.portraits",
                            "source_url": "https://example.invalid/artist/brian-eno",
                            "attribution": "Example archive",
                            "license": "CC BY 4.0",
                        },
                    }
                ]
            }

    svc = RichMetadataService(tmp_path / "data", capability_broker=Broker())
    svc.resolve_artist = lambda name: {
        "name": name,
        "mbid": "mbid-eno",
        "links": [],
        "wikidata_qid": "",
    }
    svc._wikipedia_page_image = lambda artist, entity: ("", "")
    svc._commons_artist_image = lambda artist_name: ("", "")
    svc._download_artwork = lambda url: portrait

    result = svc.artist_photo({"name": "Brian Eno"})
    assert result["path"] == str(portrait)
    assert result["source"] == "org.example.portraits"
    assert result["discovery_source"] == "Artwork plugin"



def test_wikipedia_link_falls_back_to_non_english_wikidata_sitelink(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    api, title = svc._wikipedia_link(
        {"name": "Example Artist", "links": []},
        {
            "sitelinks": {
                "dewiki": {"title": "Beispielkünstler"},
                "frwiki": {"title": "Artiste exemple"},
            }
        },
    )
    assert api == "https://de.wikipedia.org/w/api.php"
    assert title == "Beispielkünstler"



def test_user_selected_artist_photo_is_copied_and_remembered(tmp_path: Path):
    source = tmp_path / "artist-photo.jpg"
    source.write_bytes(b"user portrait")

    svc = RichMetadataService(tmp_path / "data")
    result = svc.remember_artist_photo_file({"name": "Brian Eno"}, source)

    cached_path = Path(result["path"])
    assert cached_path.is_file()
    assert cached_path.read_bytes() == b"user portrait"
    assert cached_path != source

    reopened = RichMetadataService(tmp_path / "data")
    cached = reopened.cached_artist_photo({"name": "Brian Eno"})
    assert cached["path"] == str(cached_path)
    assert cached["source"] == "User-selected artist photo"
