from melodex_provider_sdk import Album, Artist, PlaybackResource, Track


def test_track_serializes_with_discriminator():
    track = Track("org.example", "1", "Track", artist="Artist")
    assert track.to_dict()["type"] == "track"
    assert track.to_dict()["provider_track_id"] == "1"


def test_album_and_artist_discriminators():
    assert Album("org.example", "a1", "Album").to_dict()["type"] == "album"
    assert Artist("org.example", "r1", "Artist").to_dict()["type"] == "artist"


def test_playback_resource_defaults():
    resource = PlaybackResource(kind="http", url="https://example.invalid/a.mp3")
    assert resource.seekable is True
    assert resource.cache_policy == "session"
