from itertools import product

from melodex.living_queue import LivingQueue


def _track(name: str) -> dict[str, str]:
    return {"track_id": name, "title": name}


def test_current_track_cannot_be_removed_reordered_or_pinned():
    queue = LivingQueue([_track("current"), _track("next")], current_index=0)

    assert queue.remove(0) is False
    assert queue.move(0, 1) is False
    assert queue.pin(0) is False
    assert [track["track_id"] for track in queue.tracks()] == ["current", "next"]


def test_manual_insert_is_protected_from_route_replacement():
    queue = LivingQueue(
        [_track("current"), _track("old-a"), _track("old-b")], current_index=0
    )
    assert queue.insert(_track("manual"), index=2) is True

    queue.replace_generated_tail([_track("new-a"), _track("new-b")])

    assert [track["track_id"] for track in queue.tracks()] == [
        "current",
        "new-a",
        "manual",
        "new-b",
    ]


def test_pin_and_locked_next_entries_survive_replan_in_original_order():
    queue = LivingQueue(
        [_track(name) for name in ("current", "a", "b", "c", "d")],
        current_index=0,
    )
    assert queue.pin(2) is True
    assert queue.lock_next(1) == 1

    queue.replace_generated_tail([_track("x"), _track("y"), _track("z")])

    assert [track["track_id"] for track in queue.tracks()] == [
        "current",
        "a",
        "b",
        "x",
        "y",
        "z",
    ]


def test_removing_protected_upcoming_track_requires_unpin_or_unlock():
    queue = LivingQueue([_track("current"), _track("next")], current_index=0)
    assert queue.pin(1) is True
    assert queue.remove(1) is False
    assert queue.pin(1, False) is True
    assert queue.remove(1) is True


def test_locked_track_cannot_be_moved_or_displaced_by_reordering():
    queue = LivingQueue(
        [_track("current"), _track("a"), _track("locked"), _track("b")],
        current_index=0,
    )
    assert queue.lock_next(2) == 2
    assert queue.unlock(1) is True
    assert queue.move(1, 3) is False
    assert queue.move(3, 1) is False
    assert [track["track_id"] for track in queue.tracks()] == [
        "current",
        "a",
        "locked",
        "b",
    ]


def test_generated_replacement_deduplicates_current_and_protected_tracks():
    queue = LivingQueue([_track("current"), _track("pinned")], current_index=0)
    queue.pin(1)

    queue.replace_generated_tail(
        [_track("current"), _track("new"), _track("pinned"), _track("new")]
    )

    assert [track["track_id"] for track in queue.tracks()] == [
        "current",
        "pinned",
        "new",
    ]


def test_manual_insert_is_protected_from_automation_but_still_user_editable():
    queue = LivingQueue([_track("current"), _track("generated")], current_index=0)
    assert queue.insert(_track("manual"), index=2) is True
    assert queue.remove(1) is True  # generated track is removable
    assert queue.remove(1) is True  # explicit user removal can remove own insert


def test_unstarted_queue_keeps_no_current_track_during_replacement():
    queue = LivingQueue([_track("old")], current_index=-1)
    assert queue.insert(_track("manual")) is True
    queue.replace_generated_tail([_track("new")])

    assert queue.current_index == -1
    assert [track["track_id"] for track in queue.tracks()] == ["manual", "new"]


def test_initial_route_replacement_deduplicates_candidates():
    queue = LivingQueue([], current_index=-1)

    queue.replace_generated_tail(
        [_track("repeat"), _track("other"), _track("repeat")]
    )

    assert queue.current_index == -1
    assert [track["track_id"] for track in queue.tracks()] == ["repeat", "other"]


def test_all_pin_and_lock_patterns_survive_generated_replacement():
    upcoming = [f"track-{index}" for index in range(4)]
    for protected_pattern in product((False, True), repeat=len(upcoming)):
        queue = LivingQueue(
            [_track(name) for name in ("current", *upcoming)],
            current_index=0,
        )
        protected = []
        for offset, is_protected in enumerate(protected_pattern, start=1):
            if not is_protected:
                continue
            protected.append(upcoming[offset - 1])
            if offset % 2:
                assert queue.pin(offset) is True
            else:
                assert queue.set_locked(offset) is True

        queue.replace_generated_tail(
            [
                _track("current"),
                *[_track(name) for name in upcoming],
                _track("fresh-a"),
                _track("fresh-a"),
                _track("fresh-b"),
            ]
        )

        ids = [track["track_id"] for track in queue.tracks()]
        assert ids[0] == "current"
        assert [name for name in ids if name in protected] == protected
        assert len(ids) == len(set(ids))


def test_sync_retains_queue_intent_for_same_tracks_after_reorder():
    queue = LivingQueue(
        [_track("current"), _track("keep"), _track("move")], current_index=0
    )
    assert queue.pin(1) is True

    queue.sync_from_tracks(
        [_track("current"), _track("move"), _track("keep")], current_index=0
    )

    assert [track["track_id"] for track in queue.tracks()] == [
        "current",
        "move",
        "keep",
    ]
    assert queue.entries[2].pinned is True


def test_appended_manual_track_survives_an_automatic_route_change():
    queue = LivingQueue([_track("current"), _track("old")], current_index=0)
    queue.sync_from_tracks(
        [_track("current"), _track("old"), _track("manual")],
        current_index=0,
        new_origin="manual",
    )

    queue.replace_generated_tail([_track("new-route")])

    assert [track["track_id"] for track in queue.tracks()] == [
        "current",
        "new-route",
        "manual",
    ]
    assert queue.entries[2].origin == "manual"


def test_undo_restores_prior_generated_tail_and_preserves_protected_choice():
    queue = LivingQueue(
        [_track(name) for name in ("current", "old-a", "keep", "old-b")],
        current_index=0,
    )
    assert queue.pin(2) is True
    queue.replace_generated_tail([_track("new-a"), _track("new-b")])
    assert [track["track_id"] for track in queue.tracks()] == [
        "current",
        "new-a",
        "keep",
        "new-b",
    ]
    assert queue.can_undo_replan is True

    assert queue.undo_replan() is True
    assert [track["track_id"] for track in queue.tracks()] == [
        "current",
        "old-a",
        "keep",
        "old-b",
    ]
    assert queue.entries[2].pinned is True
    assert queue.can_undo_replan is False
    assert queue.undo_replan() is False


def test_undo_after_playback_advances_keeps_new_current_track():
    queue = LivingQueue(
        [_track("current"), _track("old"), _track("next")], current_index=0
    )
    queue.replace_generated_tail([_track("replacement")])
    queue.sync_from_tracks(queue.tracks(), current_index=1)

    assert queue.undo_replan() is True
    assert queue.current_index == 1
    assert [track["track_id"] for track in queue.tracks()] == [
        "current",
        "replacement",
        "old",
        "next",
    ]


def test_queue_edit_supersedes_stale_route_undo():
    queue = LivingQueue(
        [_track(name) for name in ("current", "old-a", "old-b")],
        current_index=0,
    )
    queue.replace_generated_tail([_track("new-a"), _track("new-b")])
    assert queue.can_undo_replan is True

    queue.sync_from_tracks(
        [_track("current"), _track("new-b"), _track("new-a")],
        current_index=0,
    )

    assert queue.can_undo_replan is False


def test_undo_restores_intentional_duplicate_tracks_from_prior_tail():
    queue = LivingQueue(
        [_track(name) for name in ("current", "repeat", "repeat")],
        current_index=0,
    )
    queue.replace_generated_tail([_track("new")])

    assert queue.undo_replan() is True
    assert [track["track_id"] for track in queue.tracks()] == [
        "current",
        "repeat",
        "repeat",
    ]
