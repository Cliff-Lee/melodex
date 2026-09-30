from pathlib import Path

from melodex.playlist_io import load_playlist, parse_playlist_text, save_playlist


def test_m3u8_round_trip_metadata_and_direct_url(tmp_path: Path):
    path = tmp_path / "mix.m3u8"
    tracks = [
        {"artist": "A", "title": "One", "album": "Alpha", "duration": 123, "stream_url": "https://example.test/one.mp3", "provider_id": "demo", "track_id": "1"},
        {"artist": "B", "title": "Two", "album": "Beta"},
    ]
    save_playlist(path, tracks, "Mix")
    data = load_playlist(path)
    assert len(data["tracks"]) == 2
    assert data["tracks"][0]["artist"] == "A"
    assert data["tracks"][0]["stream_url"] == "https://example.test/one.mp3"
    assert data["tracks"][1]["artist"] == "B"
    assert data["tracks"][1]["title"] == "Two"
    assert not data["tracks"][1].get("stream_url")


def test_m3u_relative_file_is_resolved_against_playlist_folder(tmp_path: Path):
    music = tmp_path / "music"; music.mkdir()
    f = music / "song.mp3"; f.write_bytes(b"x")
    playlist = tmp_path / "local.m3u"
    playlist.write_text("#EXTM3U\n#EXTINF:10,Artist - Song\nmusic/song.mp3\n", "utf-8")
    data = load_playlist(playlist)
    assert data["tracks"][0]["local_path"] == str(f.resolve())
    assert data["tracks"][0]["artist"] == "Artist"
    assert data["tracks"][0]["title"] == "Song"


def test_xspf_round_trip_metadata_only_track(tmp_path: Path):
    path = tmp_path / "mix.xspf"
    tracks = [{"artist": "Boards of Canada", "title": "Dayvan Cowboy", "album": "The Campfire Headphase", "year": 2005}]
    save_playlist(path, tracks, "Dreaming", "test")
    data = load_playlist(path)
    assert data["name"] == "Dreaming"
    assert data["description"] == "test"
    assert data["tracks"][0]["artist"] == "Boards of Canada"
    assert data["tracks"][0]["title"] == "Dayvan Cowboy"
    assert str(data["tracks"][0]["year"]) == "2005"


def test_universal_resolver_accepts_direct_playlist_url_without_provider(tmp_path: Path):
    from melodex.resolver import UniversalResolver

    class Manager:
        providers = {}
        settings = {}
        def save(self): pass

    resolver = UniversalResolver(Manager())
    out = resolver.resolve({"artist":"A", "title":"One", "stream_url":"https://example.test/one.mp3"})
    assert out["stream_url"] == "https://example.test/one.mp3"
    assert out["_resolution"]["mode"] == "playlist-direct"


def test_parse_ai_playlist_json_inside_markdown_fence_and_surrounding_text():
    text='''Here is your playlist:\n```json
{"melodex_playlist":1,"name":"Late Night","description":"Easy listening","tracks":[
  {"artist":"Air","title":"La femme d'argent","album":"Moon Safari","year":1998},
  {"artist":"Zero 7","title":"Destiny"}
]}
```'''
    data=parse_playlist_text(text)
    assert data["name"] == "Late Night"
    assert data["tracks"][0]["artist"] == "Air"
    assert data["tracks"][0]["album"] == "Moon Safari"
    assert data["tracks"][1]["title"] == "Destiny"


def test_parse_ai_playlist_markdown_table_and_track_aliases():
    text="""| # | Artist | Track | Album | Year |
|---|---|---|---|---|
| 1 | Air | La femme d'argent | Moon Safari | 1998 |
| 2 | Zero 7 | Destiny | When It Falls | 2004 |"""
    data=parse_playlist_text(text)
    assert [(x["artist"],x["title"]) for x in data["tracks"]] == [
        ("Air","La femme d'argent"),("Zero 7","Destiny")
    ]


def test_parse_ai_playlist_csv_and_plain_list():
    csv_data=parse_playlist_text("Artist,Title,Album\nAir,La femme d'argent,Moon Safari\n")
    assert csv_data["tracks"][0]["album"] == "Moon Safari"
    plain=parse_playlist_text("1. Air — La femme d'argent\n2. Zero 7 - Destiny")
    assert [(x["artist"],x["title"]) for x in plain["tracks"]] == [
        ("Air","La femme d'argent"),("Zero 7","Destiny")
    ]


def test_parse_m3u_pasted_text_preserves_direct_stream_url():
    data=parse_playlist_text("#EXTM3U\n#EXTINF:-1,Artist — Radio Song\nhttps://example.test/song.mp3")
    assert data["tracks"][0]["artist"] == "Artist"
    assert data["tracks"][0]["stream_url"] == "https://example.test/song.mp3"
