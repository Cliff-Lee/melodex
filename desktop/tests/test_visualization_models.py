from melodex.visualization_models import (
    build_constellation,
    build_visual_memory,
    describe_weather,
    lyric_frame,
)
from melodex.visualization_profile import build_visual_profile


def test_constellation_is_bounded_deterministic_and_display_only():
    current = {"artist": "North", "title": "Now", "album": "Sky"}
    candidates = [
        {"_visual_token": 7, "_visual_relation": "Up next", "track": {
            "artist": "North", "title": "Next", "album": "Sky", "local_path": "/private/music.mp3"
        }},
        {"_visual_token": 8, "track": {"artist": "South", "title": "Elsewhere", "album": "Land"}},
        {"_visual_token": 9, "track": {"artist": "North", "title": "Now", "album": "Sky"}},
    ]

    first = build_constellation(current, candidates)
    second = build_constellation(current, candidates)

    assert first == second
    assert [node.token for node in first] == [7, 8]
    assert first[0].relation == "Up next"
    assert first[0].artist == "North"
    assert not hasattr(first[0], "local_path")
    assert all(0 <= node.x <= 1 and 0 <= node.y <= 1 for node in first)
    assert len(build_constellation(current, candidates * 20)) <= 24


def test_sonic_weather_describes_cached_features_and_marks_fallback():
    track = {"artist": "A", "title": "B"}
    cached = build_visual_profile(track, {
        "bpm": 128, "energy": 0.82, "spectral_centroid": 2900,
        "onset_density": 0.19,
    })
    fallback = build_visual_profile(track)

    weather = describe_weather(cached)
    identity = describe_weather(fallback)
    assert weather.based_on_flow is True
    assert weather.motion == "rolling"
    assert weather.tone == "bright and open"
    assert weather.density == "dense and active"
    assert "identity-based" in identity.summary.casefold()
    assert identity.based_on_flow is False


def test_lyric_frame_uses_timestamps_when_available():
    lyrics = {"source": "local LRC", "text": "", "synced": [
        {"time_ms": 1000, "text": "First line"},
        {"time_ms": 3000, "text": "Second line"},
        {"time_ms": 5000, "text": "Last line"},
    ]}

    before = lyric_frame(lyrics, 500, 6000)
    active = lyric_frame(lyrics, 3600, 6000)
    assert before.current == ""
    assert before.following == "First line"
    assert active.previous == "First line"
    assert active.current == "Second line"
    assert active.following == "Last line"
    assert active.synced is True
    assert active.source == "local LRC"


def test_untimed_lyrics_are_paced_across_the_track_and_labelled_unsynced():
    lyrics = {"text": "one\ntwo\nthree\nfour"}

    start = lyric_frame(lyrics, 0, 10000)
    later = lyric_frame(lyrics, 7500, 10000)
    assert start.current == "one"
    assert later.current == "four"
    assert later.synced is False


def test_visual_memory_groups_local_history_at_different_scales():
    rows = [
        {"_played_at": 1_700_000_000, "artist": "A", "title": "One", "album": "Album"},
        {"_played_at": 1_700_000_300, "artist": "A", "title": "Two", "album": "Album"},
        {"_played_at": 1_700_100_000, "artist": "B", "title": "Three", "album": "Other"},
    ]
    sessions = build_visual_memory(rows, "sessions")
    albums = build_visual_memory(rows, "albums")
    weeks = build_visual_memory(rows, "weeks")

    assert len(sessions) == 2
    assert len(albums) == 2
    assert sum(mark.count for mark in sessions) == len(rows)
    assert build_visual_memory(rows, "albums") == albums
    assert all(0 <= mark.x <= 1 and 0 <= mark.y <= 1 for mark in sessions + albums + weeks)
    assert not hasattr(sessions[0], "local_path")
