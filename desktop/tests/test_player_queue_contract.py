from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _player():
    from PySide6.QtWidgets import QApplication
    from melodex.player import FlowPlayer

    QApplication.instance() or QApplication([])
    player = FlowPlayer(lambda track: dict(track))
    loaded = []

    def fake_load(index: int, play: bool = True, deck=None):
        player.index = index
        loaded.append((index, bool(play)))

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
