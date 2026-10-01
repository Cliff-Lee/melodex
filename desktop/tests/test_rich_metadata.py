from pathlib import Path

from melodex.metadata import MetadataIdentity, RichMetadataService, parse_lrc, track_key


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
    svc._commons_artist_image = lambda artist_name, aliases=(): ("", "")
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



def test_user_selected_artist_photo_rejects_unsupported_file_type(tmp_path: Path):
    source = tmp_path / "not-an-image.txt"
    source.write_text("not an image", "utf-8")
    svc = RichMetadataService(tmp_path / "data")
    assert svc.remember_artist_photo_file({"name": "Example Artist"}, source) == {}



def test_lyrics_sidecar_finds_title_and_artist_title_names(tmp_path: Path):
    album = tmp_path / "Album"
    album.mkdir()
    audio = album / "01 - Teardrop.mp3"
    audio.write_bytes(b"not audio")
    (album / "Massive Attack - Teardrop.LRC").write_text(
        "[00:01.00]Love, love is a verb\n[00:03.00]Love is a doing word",
        "utf-8",
    )

    svc = RichMetadataService(tmp_path / "data")
    out = svc.local_lyrics({
        "local_path": str(audio),
        "provider_id": "local",
        "track_id": str(audio),
        "artist": "Massive Attack",
        "title": "Teardrop",
        "album": "Mezzanine",
    })
    assert out["source"] == "Massive Attack - Teardrop.LRC"
    assert out["synced"][0]["time_ms"] == 1000
    assert "Love, love is a verb" in out["text"]


def test_lyrics_sidecar_finds_lyrics_subfolder(tmp_path: Path):
    album = tmp_path / "Album"
    lyrics_dir = album / "Lyrics"
    lyrics_dir.mkdir(parents=True)
    audio = album / "track.flac"
    audio.write_bytes(b"not audio")
    (lyrics_dir / "Track Title.txt").write_text("line one\nline two", "utf-8")

    svc = RichMetadataService(tmp_path / "data")
    out = svc.local_lyrics({
        "local_path": str(audio),
        "artist": "Artist",
        "title": "Track Title",
    })
    assert out["text"] == "line one\nline two"
    assert out["source"] == "Track Title.txt"


def test_pasted_lyrics_persist_without_touching_audio(tmp_path: Path):
    audio = tmp_path / "Song.mp3"
    audio.write_bytes(b"original audio bytes")
    track = {
        "provider_id": "local",
        "track_id": str(audio),
        "local_path": str(audio),
        "artist": "Artist",
        "title": "Song",
        "album": "Album",
    }

    first = RichMetadataService(tmp_path / "data")
    saved = first.remember_lyrics_text(track, "first line\nsecond line")
    assert saved["source"] == "Pasted lyrics"
    assert audio.read_bytes() == b"original audio bytes"

    second = RichMetadataService(tmp_path / "data")
    loaded = second.local_lyrics(track)
    assert loaded["text"] == "first line\nsecond line"
    assert loaded["user_added"] is True
    assert audio.read_bytes() == b"original audio bytes"


def test_imported_lrc_is_copied_and_remains_synchronized(tmp_path: Path):
    source = tmp_path / "downloaded.lrc"
    source.write_text("[00:02.00]Hello\n[00:04.50]again", "utf-8")
    track = {
        "provider_id": "local",
        "track_id": "song-id",
        "artist": "Artist",
        "title": "Song",
    }
    svc = RichMetadataService(tmp_path / "data")
    saved = svc.remember_lyrics_file(track, source)
    assert saved["synced"][0]["time_ms"] == 2000
    cached_path = Path(saved["path"])
    assert cached_path.is_file()
    assert cached_path != source

    source.unlink()
    reopened = RichMetadataService(tmp_path / "data")
    loaded = reopened.local_lyrics(track)
    assert loaded["synced"][1]["time_ms"] == 4500
    assert loaded["source"].startswith("Imported ")



def test_community_lyrics_prefers_exact_lrclib_match_and_persists_bounded_cache(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")

    class Response:
        status_code = 200
        def json(self):
            return {
                "id": 42,
                "trackName": "Example Song",
                "artistName": "Example Artist",
                "albumName": "Example Album",
                "duration": 201.2,
                "plainLyrics": "Line one\nLine two",
                "syncedLyrics": "[00:01.00]Line one\n[00:03.50]Line two",
                "instrumental": False,
            }
        def raise_for_status(self):
            return None

    calls = []
    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    svc.session.get = fake_get
    result = svc.community_lyrics({
        "artist": "Example Artist",
        "title": "Example Song",
        "album": "Example Album",
        "duration": 201.0,
    })

    assert result["source"] == "LRCLIB community lyrics"
    assert result["text"] == "Line one\nLine two"
    assert len(result["synced"]) == 2
    assert result["synced"][0]["time_ms"] == 1000
    assert calls[0][0].endswith("/api/get")

    reopened = RichMetadataService(tmp_path / "data")
    cached = reopened.cached_community_lyrics({
        "artist": "Example Artist",
        "title": "Example Song",
        "album": "Example Album",
        "duration": 201.0,
    })
    assert cached["text"] == "Line one\nLine two"
    assert cached["source"] == "LRCLIB community lyrics"
    assert cached["cache"] == "disk"


def test_community_lyrics_search_rejects_wrong_artist(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")

    class ExactMiss:
        status_code = 404
        def json(self):
            return {}
        def raise_for_status(self):
            return None

    class Search:
        status_code = 200
        def json(self):
            return [{
                "id": 9,
                "trackName": "Example Song",
                "artistName": "Completely Different Artist",
                "albumName": "Example Album",
                "duration": 200.0,
                "plainLyrics": "Wrong lyric",
                "syncedLyrics": None,
                "instrumental": False,
            }]
        def raise_for_status(self):
            return None

    responses = iter([ExactMiss(), Search()])
    svc.session.get = lambda *args, **kwargs: next(responses)
    result = svc.community_lyrics({
        "artist": "Example Artist",
        "title": "Example Song",
        "album": "Example Album",
        "duration": 200.0,
    })
    assert result["text"] == ""


def test_community_lyrics_can_report_instrumental(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")

    class Response:
        status_code = 200
        def json(self):
            return {
                "id": 77,
                "trackName": "Instrumental",
                "artistName": "Example Artist",
                "albumName": "",
                "duration": 180.0,
                "plainLyrics": None,
                "syncedLyrics": None,
                "instrumental": True,
            }
        def raise_for_status(self):
            return None

    svc.session.get = lambda *args, **kwargs: Response()
    result = svc.community_lyrics({
        "artist": "Example Artist",
        "title": "Instrumental",
        "duration": 180.0,
    })
    assert result["instrumental"] is True
    assert result["text"] == ""



def test_community_lyrics_cleans_version_and_feature_metadata_for_fallback(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    calls = []

    class Miss:
        status_code = 404
        def json(self):
            return {}
        def raise_for_status(self):
            return None

    class Hit:
        status_code = 200
        def json(self):
            return {
                "id": 501,
                "trackName": "Example Song",
                "artistName": "Example Artist",
                "albumName": "Example Album",
                "duration": 201.0,
                "plainLyrics": "Recovered lyric",
                "syncedLyrics": None,
                "instrumental": False,
            }
        def raise_for_status(self):
            return None

    responses = iter([Miss(), Hit()])

    def fake_get(url, **kwargs):
        calls.append((url, dict(kwargs.get("params") or {})))
        return next(responses)

    svc.session.get = fake_get
    result = svc.community_lyrics({
        "artist": "Example Artist feat. Guest",
        "title": "Example Song (2011 Remaster)",
        "album": "Example Album",
        "duration": 201.0,
    })

    assert result["status"] == "found"
    assert result["text"] == "Recovered lyric"
    assert result["match"]["method"] == "cleaned_exact"
    assert calls[0][1]["track_name"] == "Example Song (2011 Remaster)"
    assert calls[1][1]["track_name"] == "Example Song"
    assert calls[1][1]["artist_name"] == "Example Artist"
    assert "album_name" not in calls[1][1]


def test_community_lyrics_structured_search_scores_candidates_not_first_result(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    calls = []

    class Miss:
        status_code = 404
        def json(self):
            return {}
        def raise_for_status(self):
            return None

    class Search:
        status_code = 200
        def json(self):
            return [
                {
                    "id": 9,
                    "trackName": "Example Song",
                    "artistName": "Another Artist",
                    "albumName": "Example Album",
                    "duration": 200.0,
                    "plainLyrics": "Wrong lyric",
                    "syncedLyrics": None,
                    "instrumental": False,
                },
                {
                    "id": 10,
                    "trackName": "Example Song",
                    "artistName": "Example Artist",
                    "albumName": "Example Album",
                    "duration": 200.5,
                    "plainLyrics": "Right lyric",
                    "syncedLyrics": None,
                    "instrumental": False,
                },
            ]
        def raise_for_status(self):
            return None

    responses = iter([Miss(), Miss(), Search()])

    def fake_get(url, **kwargs):
        calls.append((url, dict(kwargs.get("params") or {})))
        return next(responses)

    svc.session.get = fake_get
    result = svc.community_lyrics({
        "artist": "Example Artist",
        "title": "Example Song",
        "album": "Example Album",
        "duration": 200.0,
    })

    assert result["text"] == "Right lyric"
    assert result["remote_id"] == "10"
    assert result["match"]["method"] == "structured_search"
    search_url, search_params = calls[-1]
    assert search_url.endswith("/api/search")
    assert search_params["track_name"] == "Example Song"
    assert search_params["artist_name"] == "Example Artist"
    assert search_params["album_name"] == "Example Album"
    assert "q" not in search_params


def test_community_lyrics_reuses_session_result_and_force_refreshes(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    count = {"requests": 0}

    class Hit:
        status_code = 200
        def json(self):
            return {
                "id": 88,
                "trackName": "Cached Song",
                "artistName": "Cached Artist",
                "albumName": "",
                "duration": 180.0,
                "plainLyrics": "One request is enough",
                "syncedLyrics": None,
                "instrumental": False,
            }
        def raise_for_status(self):
            return None

    def fake_get(*args, **kwargs):
        count["requests"] += 1
        return Hit()

    svc.session.get = fake_get
    track = {
        "artist": "Cached Artist",
        "title": "Cached Song",
        "duration": 180.0,
    }

    first = svc.community_lyrics(track)
    second = svc.community_lyrics(track)
    refreshed = svc.community_lyrics(track, force=True)

    assert first["status"] == "found"
    assert "cache" not in first
    assert second["cache"] == "memory"
    assert refreshed["status"] == "found"
    assert count["requests"] == 2


def test_community_lyrics_short_caches_confident_not_found(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    count = {"requests": 0}

    class Miss:
        status_code = 404
        def json(self):
            return {}
        def raise_for_status(self):
            return None

    class EmptySearch:
        status_code = 200
        def json(self):
            return []
        def raise_for_status(self):
            return None

    responses = [Miss(), EmptySearch()]

    def fake_get(*args, **kwargs):
        count["requests"] += 1
        return responses[min(count["requests"] - 1, len(responses) - 1)]

    svc.session.get = fake_get
    track = {"artist": "No Such Artist", "title": "No Such Song"}

    first = svc.community_lyrics(track)
    second = svc.community_lyrics(track)

    assert first["status"] == "not_found"
    assert second["status"] == "not_found"
    assert second["cache"] == "memory"
    assert count["requests"] == 2



def test_artist_search_names_include_aliases_and_unsorted_name():
    names = RichMetadataService._artist_search_names({
        "name": "P!nk",
        "sort_name": "Pink, P!",
        "aliases": ["Pink", {"name": "PINK"}],
    })
    assert names[0] == "P!nk"
    assert "P! Pink" in names
    assert "Pink" in names


def test_wikipedia_artist_search_can_recover_using_musicbrainz_alias(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    seen = []

    def fake_remote(key, url, max_age=0):
        seen.append((key, url))
        if "pink" in url.casefold() and "p%21nk" not in url.casefold():
            return {
                "query": {
                    "search": [{
                        "title": "Pink (singer)",
                        "snippet": "American singer, songwriter and musician",
                    }]
                }
            }
        return {"query": {"search": []}}

    svc._remote_json = fake_remote
    api, title = svc._wikipedia_artist_page_by_name({
        "name": "P!nk",
        "type": "Person",
        "aliases": ["Pink"],
    })
    assert api.endswith("en.wikipedia.org/w/api.php")
    assert title == "Pink (singer)"
    assert len(seen) >= 2


def test_release_group_artwork_candidate_requires_matching_artist(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    svc._mb_json = lambda *args, **kwargs: {
        "release-groups": [
            {
                "id": "wrong-rg",
                "title": "Mezzanine",
                "artist-credit": [{"name": "Different Artist"}],
                "first-release-date": "1998-01-01",
                "primary-type": "Album",
                "secondary-types": [],
            },
            {
                "id": "right-rg",
                "title": "Mezzanine",
                "artist-credit": [{"name": "Massive Attack"}],
                "first-release-date": "1998-04-20",
                "primary-type": "Album",
                "secondary-types": [],
            },
        ]
    }
    candidate = svc._release_group_artwork_candidate(
        {"artist": "Massive Attack", "album": "Mezzanine", "year": 1998},
        MetadataIdentity(artist="Massive Attack", album="Mezzanine"),
    )
    assert candidate["release_group_mbid"] == "right-rg"
    assert candidate["score"] >= 0.9
    assert candidate["evidence"]["artist"] > 0.95


def test_release_group_artwork_candidate_rejects_live_variant_for_studio_album(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    svc._mb_json = lambda *args, **kwargs: {
        "release-groups": [{
            "id": "live-rg",
            "title": "Mezzanine",
            "artist-credit": [{"name": "Massive Attack"}],
            "first-release-date": "1998-04-20",
            "primary-type": "Album",
            "secondary-types": ["Live"],
        }]
    }
    candidate = svc._release_group_artwork_candidate(
        {"artist": "Massive Attack", "album": "Mezzanine", "year": 1998},
        MetadataIdentity(artist="Massive Attack", album="Mezzanine"),
    )
    assert candidate == {}


def test_album_artwork_recovers_via_release_group_search(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"cover")

    svc.local_artwork = lambda track: {"path": "", "source": "", "source_url": ""}
    svc._release_group_artwork_candidate = lambda track, identity: {
        "release_group_mbid": "rg-recovered",
        "title": "Recovered Album",
        "artist": "Recovered Artist",
        "score": 0.93,
        "evidence": {"title": 1.0, "artist": 0.95, "year": 1.0},
    }
    svc._caa_json = lambda path: {
        "images": [{
            "front": True,
            "thumbnails": {"500": "https://example.invalid/recovered.jpg"},
        }]
    }
    svc._download_artwork = lambda url: cover

    result = svc.artwork(
        {"artist": "Recovered Artist", "album": "Recovered Album"},
        MetadataIdentity(artist="Recovered Artist", album="Recovered Album"),
    )
    assert result["path"] == str(cover)
    assert result["source"] == "Cover Art Archive"
    assert result["match"]["method"] == "release_group_search"
    assert result["match"]["confidence"] == 0.93


def test_exact_cover_art_identity_precedes_optional_plugin(tmp_path: Path):
    cover = tmp_path / "caa.jpg"
    cover.write_bytes(b"caa")

    class Broker:
        def entity_ref(self, *args, **kwargs):
            raise AssertionError("plugin should not be consulted after exact CAA hit")

    svc = RichMetadataService(tmp_path / "data", capability_broker=Broker())
    svc.local_artwork = lambda track: {"path": "", "source": "", "source_url": ""}
    svc._caa_json = lambda path: {
        "images": [{
            "front": True,
            "thumbnails": {"500": "https://example.invalid/caa.jpg"},
        }]
    }
    svc._download_artwork = lambda url: cover

    result = svc.artwork(
        {"artist": "Artist", "album": "Album"},
        MetadataIdentity(
            artist="Artist",
            album="Album",
            release_group_mbid="rg-exact",
            score=0.98,
        ),
    )
    assert result["path"] == str(cover)
    assert result["match"]["method"] == "musicbrainz_identity"


def test_low_confidence_artwork_plugin_asset_is_rejected(tmp_path: Path):
    calls = []

    class Broker:
        def entity_ref(self, track, identity=None):
            return {"entity_type": "track"}
        def lookup_artwork(self, subject, roles=None, max_results=8):
            return {
                "assets": [{
                    "url": "https://example.invalid/wrong.jpg",
                    "role": "cover",
                    "confidence": 0.35,
                    "_extension_id": "org.example.weak-art",
                }]
            }

    svc = RichMetadataService(tmp_path / "data", capability_broker=Broker())
    svc.local_artwork = lambda track: {"path": "", "source": "", "source_url": ""}
    svc._download_artwork = lambda url: calls.append(url) or None
    svc._release_group_artwork_candidate = lambda track, identity: {}

    result = svc.artwork(
        {"artist": "Artist", "album": "Album"},
        MetadataIdentity(artist="Artist", album="Album"),
    )
    assert result["path"] == ""
    assert calls == []


def test_low_confidence_artist_photo_plugin_asset_is_rejected(tmp_path: Path):
    calls = []

    class Broker:
        def entity_ref(self, track, identity=None, entity_type="track"):
            return {"entity_type": "artist"}
        def lookup_artwork(self, subject, roles=None, max_results=8):
            return {
                "assets": [{
                    "url": "https://example.invalid/wrong-person.jpg",
                    "role": "portrait",
                    "confidence": 0.2,
                    "_extension_id": "org.example.weak-portrait",
                }]
            }

    svc = RichMetadataService(tmp_path / "data", capability_broker=Broker())
    svc.resolve_artist = lambda name: {"name": name, "links": [], "aliases": []}
    svc._wikipedia_page_image = lambda artist, entity: ("", "")
    svc._commons_artist_image = lambda artist_name, aliases=(): ("", "")
    svc._download_artwork = lambda url: calls.append(url) or None

    result = svc.artist_photo({"name": "Example Artist"})
    assert result["path"] == ""
    assert calls == []


def test_download_artwork_rejects_non_image_response(tmp_path: Path):
    svc = RichMetadataService(tmp_path / "data")

    class Response:
        headers = {"Content-Type": "text/html; charset=utf-8"}
        content = b"<html>" + b"x" * 500 + b"</html>"
        def raise_for_status(self):
            return None

    svc.session.get = lambda *args, **kwargs: Response()
    assert svc._download_artwork("https://example.invalid/not-an-image") is None
    assert not list((tmp_path / "data" / "rich-metadata" / "artwork").glob("web-*"))


def test_legacy_remote_artwork_cache_is_revalidated_but_user_photo_survives(tmp_path: Path):
    data_dir = tmp_path / "data"
    svc = RichMetadataService(data_dir)
    remote = svc.art_cache / "legacy.jpg"
    remote.write_bytes(b"legacy")
    user = svc.art_cache / "user.jpg"
    user.write_bytes(b"user")

    svc._artwork_index = {
        "artist-name:remote artist": {
            "path": str(remote),
            "source": "Wikimedia Commons",
        },
        "artist-name:user artist": {
            "path": str(user),
            "source": "User-selected artist photo",
        },
    }
    assert svc.cached_artist_photo({"name": "Remote Artist"}) == {}
    assert svc.cached_artist_photo({"name": "User Artist"})["path"] == str(user)



def test_lrclib_force_refresh_invalidates_persistent_cache(tmp_path: Path):
    track = {
        "artist": "Example Artist",
        "title": "Example Song",
        "album": "Example Album",
        "duration": 180.0,
    }
    svc = RichMetadataService(tmp_path / "data")
    svc._cache_community_lyrics(
        "example artist|example song|example album|180",
        {
            "text": "old",
            "synced": [],
            "source": "LRCLIB community lyrics",
            "status": "found",
        },
        ttl=3600,
    )
    assert svc.cached_community_lyrics(track)["text"] == "old"

    class Response:
        status_code = 200
        def json(self):
            return {
                "id": 99,
                "trackName": "Example Song",
                "artistName": "Example Artist",
                "albumName": "Example Album",
                "duration": 180.0,
                "plainLyrics": "new",
                "syncedLyrics": "",
                "instrumental": False,
            }
        def raise_for_status(self):
            return None

    svc.session.get = lambda *args, **kwargs: Response()
    refreshed = svc.community_lyrics(track, force=True)
    assert refreshed["text"] == "new"

    reopened = RichMetadataService(tmp_path / "data")
    assert reopened.cached_community_lyrics(track)["text"] == "new"
