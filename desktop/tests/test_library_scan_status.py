from pathlib import Path

from melodex.library_scan_status import (
    format_elapsed,
    idle_scan_session,
    scan_activity_state,
    scan_change_suffix,
    scan_progress_message,
    scan_progress_patch,
    scan_roots_key,
    start_scan_session,
)


def test_scan_roots_key_and_elapsed_formatting():
    assert scan_roots_key([Path("/music/a"), Path("/music/b")]) == (
        "/music/a",
        "/music/b",
    )
    assert format_elapsed(-2) == "0:00"
    assert format_elapsed(65.9) == "1:05"
    assert format_elapsed(3661) == "1:01:01"


def test_scan_sessions_preserve_current_shape():
    assert idle_scan_session() == {
        "status": "idle",
        "running": False,
        "pending_rescan": False,
        "storage_state": "unknown",
    }

    session = start_scan_session("folder added", 2)
    assert session["status"] == "running"
    assert session["reason"] == "folder added"
    assert session["phase"] == "discovering"
    assert session["root_count"] == 2
    assert session["storage_state"] == "checking"
    assert session["io_retries"] == 0


def test_scan_progress_patch_normalises_progress_values():
    patch = scan_progress_patch(
        {
            "phase": "metadata",
            "paused": True,
            "files_seen": 21,
            "audio_files_seen": 18,
            "completed": 7,
            "total": 18,
            "unchanged": 4,
            "added": 3,
        },
        elapsed_seconds=12.3456,
        pending_rescan=True,
    )
    assert patch == {
        "status": "running",
        "running": True,
        "paused": True,
        "pending_rescan": True,
        "elapsed_seconds": 12.346,
        "phase": "metadata",
        "files_seen": 21,
        "audio_files_seen": 18,
        "directories_seen": 0,
        "completed": 7,
        "total": 18,
        "unchanged": 4,
        "resumed": 0,
        "added": 3,
        "changed": 0,
        "removed": 0,
        "stat_failures": 0,
    }


def test_scan_progress_messages_match_existing_user_copy():
    assert scan_progress_message(
        {"phase": "discovering", "audio_files_seen": 1234}
    ) == "Indexing music · discovering files · 1,234 tracks found"

    assert scan_progress_message(
        {"phase": "metadata", "completed": 5, "total": 0, "audio_files_seen": 8}
    ) == "Indexing music · reading metadata as files are found · 5 read · 8 found"

    assert scan_progress_message(
        {
            "phase": "metadata",
            "completed": 0,
            "total": 0,
            "audio_files_seen": 8,
            "unchanged": 7,
        }
    ) == "Indexing music · metadata already up to date · 7 reused"

    assert scan_progress_message(
        {"phase": "metadata", "completed": 5, "total": 10}
    ) == "Indexing music · reading metadata · 5/10"

    assert scan_progress_message({"phase": "saving"}) == (
        "Indexing music · saving local library index…"
    )
    assert scan_progress_message({"phase": "complete"}) is None


def test_scan_activity_state_preserves_progress_and_pause_semantics():
    view = scan_activity_state(
        {"phase": "metadata", "completed": 7, "total": 10},
        elapsed_seconds=65,
        paused=True,
    )
    assert view.stage == "Paused · Reading tags · 7/10"
    assert view.label == (
        "Indexing music · Paused · Reading tags · 7/10 · 1:05 elapsed · "
        "You can keep using Melodex"
    )
    assert (view.progress_min, view.progress_max, view.progress_value) == (0, 10, 7)
    assert view.progress_format == "%v / %m"
    assert view.pause_text == "Resume"


def test_scan_change_suffix_uses_existing_completion_copy():
    assert scan_change_suffix({}) == ""
    assert scan_change_suffix(
        {"unchanged": 1000, "added": 3, "changed": 2, "removed": 1}
    ) == " · 1,000 unchanged · 3 new · 2 updated · 1 removed"
