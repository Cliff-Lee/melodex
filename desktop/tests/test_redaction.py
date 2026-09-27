from melodex.redaction import redact_for_llm


def test_redacts_playback_credentials_and_urls():
    track = {
        "provider_id": "example",
        "track_id": "123",
        "artist": "Artist",
        "title": "Track",
        "album": "Album",
        "source_page": "https://example.org/item/123",
        "url": "https://cdn.example.org/audio.mp3?token=secret-value",
        "stream_url": "https://signed.example.org/audio?sig=abc",
        "local_path": "/Users/example/Music/private.mp3",
        "headers": {"Authorization": "Bearer very-secret"},
        "cookies": {"session": "private"},
        "refresh_token": "refresh-secret",
        "expires_at": "2030-01-01T00:00:00Z",
        "_playback_allowed_hosts": ["*.example.org"],
        "gateway_required": True,
    }

    safe = redact_for_llm(track)

    assert safe["provider_id"] == "example"
    assert safe["artist"] == "Artist"
    assert safe["title"] == "Track"
    assert safe["source_page"] == "https://example.org/item/123"

    for key in (
        "url",
        "stream_url",
        "local_path",
        "headers",
        "cookies",
        "refresh_token",
        "expires_at",
        "_playback_allowed_hosts",
        "gateway_required",
    ):
        assert key not in safe


def test_redaction_is_recursive():
    payload = {
        "current_track": {
            "title": "One",
            "headers": {"X-Key": "secret"},
        },
        "queue": [
            {
                "title": "Two",
                "stream_url": "https://example.test/signed",
            }
        ],
        "nested": {
            "access_token": "secret",
            "safe": "keep me",
        },
    }

    safe = redact_for_llm(payload)

    assert safe["current_track"] == {"title": "One"}
    assert safe["queue"] == [{"title": "Two"}]
    assert safe["nested"] == {"safe": "keep me"}
