from __future__ import annotations

import random

from melodex.first_play_policy import light_shuffle


def test_light_shuffle_keeps_early_discoveries_near_the_front() -> None:
    tracks = [
        {"track_id": str(index), "album": f"album-{index // 2}"}
        for index in range(40)
    ]
    shuffled = light_shuffle(tracks, rng=random.Random(12), window_size=5)

    assert {row["track_id"] for row in shuffled} == {
        row["track_id"] for row in tracks
    }
    first_ids = {int(row["track_id"]) for row in shuffled[:5]}
    assert first_ids.issubset(set(range(9)))
    assert [row["track_id"] for row in tracks] == [str(index) for index in range(40)]


def test_light_shuffle_avoids_repeating_album_when_window_allows() -> None:
    tracks = [
        {"track_id": "a1", "album": "A"},
        {"track_id": "a2", "album": "A"},
        {"track_id": "b1", "album": "B"},
        {"track_id": "b2", "album": "B"},
    ]
    shuffled = light_shuffle(tracks, rng=random.Random(4), window_size=4)

    assert all(left["album"] != right["album"] for left, right in zip(shuffled, shuffled[1:]))


def test_light_shuffle_prefers_artist_breadth_for_a_cold_start() -> None:
    tracks = [
        {"track_id": "a1", "artist": "Artist A", "album": "Album A"},
        {"track_id": "a2", "artist": "Artist A", "album": "Album A"},
        {"track_id": "b1", "artist": "Artist B", "album": "Album B"},
        {"track_id": "c1", "artist": "Artist C", "album": "Album C"},
    ]

    shuffled = light_shuffle(tracks, rng=random.Random(4), window_size=4)

    assert len({row["artist"] for row in shuffled[:3]}) == 3
    assert {row["track_id"] for row in shuffled} == {
        row["track_id"] for row in tracks
    }


def test_light_shuffle_does_not_treat_provisional_unknown_tags_as_repeats() -> None:
    tracks = [
        {"track_id": str(index), "artist": "Unknown artist", "album": ""}
        for index in range(6)
    ]

    shuffled = light_shuffle(tracks, rng=random.Random(12), window_size=3)

    assert {row["track_id"] for row in shuffled} == {
        row["track_id"] for row in tracks
    }


def test_light_shuffle_continuation_uses_recent_queue_context() -> None:
    tracks = [
        {"track_id": "a2", "artist": "Artist A", "album": "Album A"},
        {"track_id": "b2", "artist": "Artist B", "album": "Album B"},
        {"track_id": "c1", "artist": "Artist C", "album": "Album C"},
        {"track_id": "d1", "artist": "Artist D", "album": "Album D"},
    ]

    shuffled = light_shuffle(
        tracks,
        rng=random.Random(4),
        window_size=4,
        recent_context=[
            {"artist": "Artist A", "album": "Album A"},
            {"artist": "Artist B", "album": "Album B"},
        ],
    )

    assert shuffled[0]["artist"] in {"Artist C", "Artist D"}
