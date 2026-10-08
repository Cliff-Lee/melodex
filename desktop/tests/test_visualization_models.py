from datetime import datetime

from melodex.visualization_models import (
    build_constellation,
    build_visual_memory,
    describe_weather,
    lyric_frame,
    tracks_for_memory_mark,
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
    assert first[0].strength > first[1].strength
    first_radius = ((first[0].x - 0.5) ** 2 + ((first[0].y - 0.5) / 0.72) ** 2) ** 0.5
    second_radius = ((first[1].x - 0.5) ** 2 + ((first[1].y - 0.5) / 0.72) ** 2) ** 0.5
    assert first_radius < second_radius
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


def test_untimed_lyrics_are_static_and_never_guess_a_current_line():
    text = "one\ntwo\nthree\nfour"
    lyrics = {"text": text}

    start = lyric_frame(lyrics, 0, 10000)
    later = lyric_frame(lyrics, 7500, 10000)
    for frame in (start, later):
        assert frame.current == ""
        assert frame.previous == ""
        assert frame.following == ""
        assert frame.full_text == text
        assert frame.synced is False


def test_visual_memory_groups_local_history_at_different_scales():
    morning = datetime(2026, 10, 1, 8, 0).timestamp()
    evening = datetime(2026, 10, 1, 20, 0).timestamp()
    rows = [
        {"_played_at": morning, "artist": "A", "title": "One", "album": "Album"},
        {"_played_at": morning + 300, "artist": "A", "title": "Two", "album": "Album"},
        {"_played_at": evening, "artist": "B", "title": "Three", "album": "Other"},
    ]
    sessions = build_visual_memory(rows, "sessions")
    albums = build_visual_memory(rows, "albums")
    weeks = build_visual_memory(rows, "weeks")

    assert len(sessions) == 2
    assert len(albums) == 2
    assert sum(mark.count for mark in sessions) == len(rows)
    assert build_visual_memory(rows, "albums") == albums
    assert all(0 <= mark.x <= 1 and 0.14 <= mark.y <= 0.82 for mark in sessions + albums + weeks)
    assert sessions[0].y < sessions[1].y
    assert sessions[0].daypart == "Morning"
    assert sessions[1].daypart == "Evening"
    assert sessions[0].span > 0
    assert sessions[0].time_label
    assert "One" in sessions[0].representative
    assert not hasattr(sessions[0], "local_path")


def test_visual_memory_keeps_private_ordered_history_refs_for_replay():
    stamp = datetime(2026, 10, 1, 8, 0).timestamp()
    rows = [
        {
            "_history_id": 12,
            "_played_at": stamp,
            "artist": "A",
            "title": "One",
            "local_path": "/music/one.flac",
        },
        {
            "_history_id": 13,
            "_played_at": stamp + 300,
            "artist": "A",
            "title": "Two",
            "local_path": "/music/two.flac",
        },
        {
            "_history_id": 14,
            "_played_at": stamp + 3600,
            "artist": "B",
            "title": "Three",
            "local_path": "/music/three.flac",
        },
    ]
    marks = build_visual_memory(rows, "sessions")
    assert marks[0].history_ids == (12, 13)
    assert marks[1].history_ids == (14,)
    assert not hasattr(marks[0], "local_path")

    queue = tracks_for_memory_mark(
        marks[0],
        {12: rows[0], 13: rows[1], 14: rows[2]},
    )
    assert [track["title"] for track in queue] == ["One", "Two"]
    assert [track["local_path"] for track in queue] == [
        "/music/one.flac",
        "/music/two.flac",
    ]
    assert all("_history_id" not in track and "_played_at" not in track for track in queue)
    assert len(tracks_for_memory_mark(marks[0], {12: rows[0], 13: rows[1]}, limit=1)) == 1
