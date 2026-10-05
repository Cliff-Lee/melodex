from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _player():
    import pytest

    try:
        from PySide6.QtWidgets import QApplication
        from melodex.player import FlowPlayer
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    QApplication.instance() or QApplication([])
    player = FlowPlayer(lambda track: dict(track))
    loaded = []

    def fake_load(
        index: int,
        play: bool = True,
        deck=None,
        *,
        announce_queue: bool = False,
    ):
        player.index = index
        loaded.append((index, bool(play)))
        return True

    player._load_index = fake_load
    return player, loaded


def test_jump_to_uses_public_queue_contract():
    player, loaded = _player()
    player.set_queue([{"track_id": "a"}, {"track_id": "b"}], 0, False)

    assert player.jump_to(1, autoplay=True) is True
    assert player.index == 1
    assert loaded == [(1, True)]
    assert player.jump_to(4) is False

    player.close()


def test_replace_queue_item_emits_and_can_replay():
    player, loaded = _player()
    changes = []
    player.queueChanged.connect(lambda queue: changes.append([dict(x) for x in queue]))
    player.set_queue([{"track_id": "a"}, {"track_id": "b"}], 0, False)
    changes.clear()

    assert player.replace_queue_item(
        0,
        {"track_id": "resolved", "stream_url": "https://example.invalid/a"},
        autoplay=True,
    ) is True

    assert player.queue[0]["track_id"] == "resolved"
    assert changes[-1][0]["track_id"] == "resolved"
    assert loaded == [(0, True)]
    assert player.replace_queue_item(9, {"track_id": "x"}) is False

    player.close()


def test_merge_queue_items_updates_matching_rows_once():
    player, _loaded = _player()
    changes = []
    player.queueChanged.connect(lambda queue: changes.append([dict(x) for x in queue]))
    player.set_queue(
        [
            {"track_id": "a", "local_path": "/music/a.flac", "title": "Old"},
            {"track_id": "b", "local_path": "/music/b.flac", "title": "Other"},
            {"track_id": "c", "local_path": "/music/a.flac", "title": "Old again"},
        ],
        0,
        False,
    )
    changes.clear()

    count = player.merge_queue_items(
        lambda item: item.get("local_path") == "/music/a.flac",
        {"title": "Corrected"},
    )

    assert count == 2
    assert [row["title"] for row in player.queue] == [
        "Corrected",
        "Other",
        "Corrected",
    ]
    assert len(changes) == 1

    player.close()


def test_append_queue_owns_empty_and_nonempty_cases():
    player, _loaded = _player()
    player.append_queue([{"track_id": "a"}], autoplay=False)
    player.append_queue([{"track_id": "b"}], autoplay=False)

    assert [row["track_id"] for row in player.queue_snapshot()] == ["a", "b"]

    player.close()


def test_runtime_diagnostics_are_metadata_free_and_count_transport_actions():
    import json

    player, _loaded = _player()
    player.set_queue(
        [
            {
                "track_id": "private-a",
                "local_path": "/Volumes/PrivateNAS/Secret Artist/a.flac",
                "title": "Secret Song",
            },
            {
                "track_id": "private-b",
                "stream_url": "https://secret.example/token",
                "title": "Another Secret Song",
            },
        ],
        0,
        False,
    )

    player.seek(12_345)
    player.next()
    player.previous()

    snapshot = player.diagnostics_snapshot()
    text = json.dumps(snapshot)

    assert snapshot["queue_length"] == 2
    assert snapshot["queue_index_valid"] is True
    assert snapshot["seek_requests"] == 1
    assert snapshot["manual_next"] == 1
    assert snapshot["manual_previous"] == 1
    assert snapshot["last_seek_requested_ms"] == 12_345
    assert "Secret Song" not in text
    assert "PrivateNAS" not in text
    assert "secret.example" not in text

    player.close()


def test_album_order_diagnostics_are_structural_and_redacted():
    import json

    player, _loaded = _player()
    player.set_queue(
        [
            {
                "track_id": "private-one",
                "local_path": "/Volumes/PrivateNAS/Secret Artist/01.flac",
                "title": "Secret first track",
                "disc_number": "1/2",
                "track_number": "1/10",
            },
            {
                "track_id": "private-two",
                "local_path": "/Volumes/PrivateNAS/Secret Artist/02.flac",
                "title": "Secret second track",
                "disc_number": "1/2",
                "track_number": "2/10",
            },
        ],
        0,
        False,
        intent="album",
    )

    snapshot = player.diagnostics_snapshot()
    album_order = snapshot["album_order"]
    encoded = json.dumps(snapshot)

    assert album_order["track_count"] == 2
    assert album_order["disc_numbered_tracks"] == 2
    assert album_order["track_numbered_tracks"] == 2
    assert album_order["malformed_disc_numbers"] == 0
    assert album_order["malformed_track_numbers"] == 0
    assert album_order["duplicate_positions"] == 0
    assert album_order["ordering_valid"] is True
    assert "Secret" not in encoded
    assert "PrivateNAS" not in encoded
    assert "private-one" not in encoded

    player.close()

def test_audio_processing_snapshot_reports_effective_transition_and_normalization():
    player, _loaded = _player()
    queue = [{"title": "private one"}, {"title": "private two"}]

    player.set_queue(queue, 0, False, intent="album")
    album = player.audio_processing_snapshot()
    assert album == {
        "intent": "album",
        "transition_state": "off",
        "transition_ms": 0,
        "normalization": "off",
    }

    player.set_queue(queue, 0, False, intent="journey")
    planned = player.audio_processing_snapshot()
    assert planned["intent"] == "journey"
    assert planned["transition_state"] == "planned"
    assert planned["transition_ms"] == 4500
    assert planned["normalization"] == "off"

    player._planned_transition_ms = 3200
    player._crossfading = True
    player._transition_ms = 3200
    active = player.audio_processing_snapshot()
    assert active["transition_state"] == "active"
    assert active["transition_ms"] == 3200
    assert active["normalization"] == "off"

    player.set_queue(queue, 0, False, intent="playlist")
    playlist = player.audio_processing_snapshot()
    assert playlist["transition_state"] == "off"
    assert playlist["transition_ms"] == 0
    assert playlist["normalization"] == "off"

    player.close()
