from __future__ import annotations

from melodex.llm_bridge import llm_track_summary


def test_llm_track_summary_excludes_paths_tokens_urls_and_ids():
    track = {
        "provider_id": "local",
        "track_id": "/Users/example/Music/secret-folder/song.flac",
        "provider_track_id": "/Users/example/Music/secret-folder/song.flac",
        "rel": "local:/Users/example/Music/secret-folder/song.flac",
        "local_path": "/Users/example/Music/secret-folder/song.flac",
        "title": "Example Song",
        "artist": "Example Artist",
        "album": "Example Album",
        "duration": 123.4,
        "url": "https://cdn.example.invalid/private",
        "headers": {"Authorization": "Bearer secret"},
        "cookies": {"session": "secret"},
        "refresh_token": "secret",
        "api_key": "secret",
    }

    summary = llm_track_summary(track)

    assert summary == {
        "provider_id": "local",
        "title": "Example Song",
        "artist": "Example Artist",
        "album": "Example Album",
        "duration": 123.4,
    }
    assert "/Users/" not in repr(summary)
    assert "secret" not in repr(summary)


def test_llm_track_summary_keeps_safe_recent_history_metadata():
    track = {
        "title": "Track",
        "artist": "Artist",
        "_played_at": 123456.0,
        "_completed": True,
        "_history_id": 99,
    }

    assert llm_track_summary(track) == {
        "title": "Track",
        "artist": "Artist",
        "_played_at": 123456.0,
        "_completed": True,
    }
