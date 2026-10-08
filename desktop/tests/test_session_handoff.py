from __future__ import annotations

from melodex.session_handoff import refined_upcoming, track_key


def test_refined_session_preserves_heard_and_current_queue_prefix() -> None:
    queue = [
        {"track_id": "heard"},
        {"track_id": "current"},
        {"track_id": "random-upcoming"},
    ]
    expected = tuple(track_key(track) for track in queue)

    upcoming = refined_upcoming(
        queue,
        1,
        [
            {"track_id": "heard"},
            {"track_id": "current"},
            {"track_id": "personalized-a"},
            {"track_id": "personalized-a"},
            {"track_id": "personalized-b"},
        ],
        expected,
    )

    assert [track["track_id"] for track in upcoming or []] == [
        "personalized-a",
        "personalized-b",
    ]


def test_refined_session_is_discarded_after_a_queue_edit() -> None:
    queue = [{"track_id": "seed-a"}, {"track_id": "listener-choice"}]

    upcoming = refined_upcoming(
        queue,
        0,
        [{"track_id": "personalized"}],
        ("seed-a", "seed-b"),
    )

    assert upcoming is None


def test_refined_session_handles_a_single_track_library() -> None:
    queue = [{"local_path": "/music/only.flac"}]
    expected = (track_key(queue[0]),)

    upcoming = refined_upcoming(queue, 0, [dict(queue[0])], expected)

    assert upcoming == []
