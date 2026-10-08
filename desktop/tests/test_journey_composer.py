from __future__ import annotations

import json

import pytest


def _timeline():
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.journey_composer import JourneyStageTimeline
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    return app, JourneyStageTimeline()


def test_timeline_reorders_whole_stage_records_and_emits_order():
    app, timeline = _timeline()
    source = [
        {"type": "constraint", "constraint": "calm", "label": "Calm"},
        {"type": "track", "ref": "track-1", "label": "Anchor track"},
        {"type": "constraint", "constraint": "energetic", "label": "Energetic"},
    ]
    changes = []
    timeline.orderChanged.connect(changes.append)

    timeline.set_stages(source)
    assert timeline.ordered_stages() == source
    assert timeline.move_stage(0, 2) is True
    assert [stage["label"] for stage in timeline.ordered_stages()] == [
        "Anchor track",
        "Energetic",
        "Calm",
    ]
    assert timeline.item(0).text().startswith("1 / 3")
    assert timeline.item(2).text().startswith("3 / 3")
    assert changes[-1] == timeline.ordered_stages()
    assert timeline.ordered_stages()[0]["ref"] == "track-1"

    timeline.deleteLater()
    app.processEvents()


def test_timeline_rejects_invalid_moves_and_explains_empty_shape():
    app, timeline = _timeline()
    timeline.set_stages([])

    assert timeline.count() == 1
    assert timeline.ordered_stages() == []
    assert timeline.move_stage(0, 1) is False
    assert "optional" in timeline.item(0).toolTip().casefold()

    timeline.deleteLater()
    app.processEvents()


def test_delete_key_removes_selected_stage_and_restores_empty_prompt():
    try:
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QKeyEvent
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")
    app, timeline = _timeline()
    timeline.set_stages(
        [{"type": "constraint", "constraint": "calm", "label": "Calm"}]
    )
    timeline.setCurrentRow(0)

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
    timeline.keyPressEvent(event)

    assert event.isAccepted()
    assert timeline.ordered_stages() == []
    assert "drop a direction" in timeline.item(0).text().casefold()

    timeline.deleteLater()
    app.processEvents()


def test_palette_stage_can_be_inserted_before_an_existing_stage():
    app, timeline = _timeline()
    timeline.set_stages(
        [{"type": "constraint", "constraint": "calm", "label": "Calm"}]
    )
    changes = []
    timeline.orderChanged.connect(changes.append)

    assert timeline.insert_stage(
        {"type": "constraint", "constraint": "bright", "label": "Bright"},
        0,
    )
    assert [stage["label"] for stage in timeline.ordered_stages()] == ["Bright", "Calm"]
    assert timeline.insert_stage({}, 0) is False
    assert len(changes) == 1

    timeline.deleteLater()
    app.processEvents()


def test_direction_palette_button_adds_by_click_and_explains_drag():
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.journey_composer import JourneyStagePaletteButton
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    button = JourneyStagePaletteButton(
        "Calm",
        {"type": "constraint", "constraint": "calm", "label": "Calm"},
    )
    clicked = []
    button.clicked.connect(lambda *_args: clicked.append(dict(button.stage)))

    button.click()

    assert clicked == [
        {"type": "constraint", "constraint": "calm", "label": "Calm"}
    ]
    assert "drag into the journey timeline" in button.accessibleDescription().casefold()
    assert "gentler energy" in button.toolTip().casefold()

    button.deleteLater()
    app.processEvents()


def test_music_map_track_drag_payload_is_a_local_exact_waypoint():
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    music_map = MusicMapWidget()
    music_map.ref_map = {
        "map-ref-1": {
            "title": "Night Track",
            "artist": "Example Artist",
            "album": "Local Album",
            "local_path": "/private/music/night-track.flac",
        }
    }

    stage = music_map._journey_stage_for_ref("map-ref-1")

    assert stage == {
        "type": "track",
        "ref": "map-ref-1",
        "label": "Example Artist — Night Track",
    }
    assert music_map._journey_stage_for_ref("missing") == {}
    assert "/private/music" not in str(stage)

    music_map.deleteLater()
    app.processEvents()


def test_music_map_waypoint_payload_drops_into_composer_timeline():
    try:
        from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
        from PySide6.QtGui import QDragEnterEvent, QDropEvent
        from PySide6.QtWidgets import QApplication
        from melodex.journey_composer import JourneyStageTimeline, STAGE_MIME_TYPE
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    music_map = MusicMapWidget()
    music_map.ref_map = {
        "map-ref-1": {"artist": "Example Artist", "title": "Night Track"}
    }
    stage = music_map._journey_stage_for_ref("map-ref-1")
    timeline = JourneyStageTimeline()
    timeline.resize(360, 120)
    timeline.show()
    app.processEvents()

    mime = QMimeData()
    mime.setData(STAGE_MIME_TYPE, json.dumps(stage).encode("utf-8"))
    enter = QDragEnterEvent(
        QPoint(24, 20), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier
    )
    QApplication.sendEvent(timeline.viewport(), enter)
    drop = QDropEvent(
        QPointF(24, 20), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier
    )
    QApplication.sendEvent(timeline.viewport(), drop)

    assert enter.isAccepted()
    assert drop.isAccepted()
    assert timeline.ordered_stages() == [stage]

    timeline.deleteLater()
    music_map.deleteLater()
    app.processEvents()


def test_endpoint_drop_target_accepts_tracks_and_rejects_directions():
    try:
        from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
        from PySide6.QtGui import QDragEnterEvent, QDropEvent
        from PySide6.QtWidgets import QApplication
        from melodex.journey_composer import (
            JourneyEndpointDropTarget,
            STAGE_MIME_TYPE,
        )
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    target = JourneyEndpointDropTarget("start")
    target.resize(360, 60)
    target.show()
    app.processEvents()
    received = []
    target.trackDropped.connect(received.append)

    direction_mime = QMimeData()
    direction_mime.setData(
        STAGE_MIME_TYPE,
        json.dumps({"type": "constraint", "constraint": "calm"}).encode(),
    )
    rejected = QDragEnterEvent(
        QPoint(16, 16), Qt.CopyAction, direction_mime, Qt.LeftButton, Qt.NoModifier
    )
    QApplication.sendEvent(target, rejected)
    assert not rejected.isAccepted()

    stage = {"type": "track", "ref": "map-ref", "label": "Artist — Song"}
    track_mime = QMimeData()
    track_mime.setData(STAGE_MIME_TYPE, json.dumps(stage).encode())
    enter = QDragEnterEvent(
        QPoint(16, 16), Qt.CopyAction, track_mime, Qt.LeftButton, Qt.NoModifier
    )
    QApplication.sendEvent(target, enter)
    drop = QDropEvent(
        QPointF(16, 16), Qt.CopyAction, track_mime, Qt.LeftButton, Qt.NoModifier
    )
    QApplication.sendEvent(target, drop)

    assert enter.isAccepted()
    assert drop.isAccepted()
    assert received == [stage]
    assert "Artist — Song" in target.text()

    target.deleteLater()
    app.processEvents()
