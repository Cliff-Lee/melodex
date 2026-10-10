from __future__ import annotations

import os
from pathlib import Path


def _album_model(count: int = 80) -> dict:
    albums = []
    for i in range(count):
        track = {
            "provider_id": "local",
            "track_id": f"/music/{i}.mp3",
            "local_path": f"/music/{i}.mp3",
            "artist": f"Artist {i:03d}",
            "album": f"Album {i:03d}",
            "title": "Track",
        }
        albums.append({
            "key": f"k{i}",
            "artist": track["artist"],
            "title": track["album"],
            "year": 1980 + i % 40,
            "genres": [],
            "track_count": 1,
            "tracks": [track],
            "representative_track": track,
            "analysed_tracks": 1,
            "sound_x": ((i % 10) / 5.0) - 1.0,
            "sound_y": ((i // 10) / 4.0) - 1.0,
            "fallback_x": ((i % 10) / 5.0) - 1.0,
            "fallback_y": ((i // 10) / 4.0) - 1.0,
            "familiarity": (i % 10) / 10.0,
            "rediscovery": 0.0,
            "plays": i,
            "time_x": 0.0,
            "time_y": 0.0,
            "familiarity_x": 0.0,
            "familiarity_y": 0.0,
            "cover_path": "",
        })
    return {
        "albums": albums,
        "album_count": count,
        "analysed_albums": count,
    }


def test_album_wall_starts_at_readable_scale_and_overview_is_explicit():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        from melodex.album_wall import AlbumWallWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    widget = AlbumWallWidget()
    widget.resize(1000, 700)
    widget.show()
    widget.set_model(_album_model(80), {})
    app.processEvents()

    initial = float(widget.view.transform().m11())
    assert 0.90 <= initial <= 1.05

    widget.view.centerOn(240, 180)
    widget.view.scale(1.15, 1.15)
    old_center = widget.view.mapToScene(widget.view.viewport().rect().center())
    old_scale = float(widget.view.transform().m11())
    widget.set_model(_album_model(80), {})
    app.processEvents()
    new_center = widget.view.mapToScene(widget.view.viewport().rect().center())
    assert abs(float(widget.view.transform().m11()) - old_scale) < 0.01
    assert abs(new_center.x() - old_center.x()) < 3
    assert abs(new_center.y() - old_center.y()) < 3
    assert (
        widget.view.horizontalScrollBarPolicy()
        == Qt.ScrollBarAlwaysOff
    )
    assert widget.view.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert "double-click" in widget.status.text()

    widget.fit_wall()
    app.processEvents()
    overview = float(widget.view.transform().m11())
    assert overview < initial

    widget.actual_size()
    app.processEvents()
    assert abs(float(widget.view.transform().m11()) - 1.0) < 0.02

    widget.close()
    app.processEvents()


def test_music_map_defaults_to_selection_focused_relationships():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    widget = MusicMapWidget()
    widget.resize(1100, 760)
    widget.show()

    nodes = [
        {
            "ref": "a",
            "artist": "A",
            "title": "One",
            "x": -0.7,
            "y": 0.0,
            "taste": 0.5,
            "rediscovery": 0.1,
            "rediscovery_reason": "deep cut from an album you enjoyed",
        },
        {"ref": "b", "artist": "B", "title": "Two", "x": 0.0, "y": 0.2, "taste": 0.4, "rediscovery": 0.2},
        {"ref": "c", "artist": "C", "title": "Three", "x": 0.7, "y": -0.1, "taste": 0.3, "rediscovery": 0.3},
    ]
    model = {
        "nodes": nodes,
        "edges": [
            {"a": "a", "b": "b", "similarity": 0.91},
            {"a": "b", "b": "c", "similarity": 0.82},
        ],
        "analysed": 3,
        "input_profiles": 3,
    }
    ref_map = {
        "a": {"track_id": "a", "artist": "A", "title": "One"},
        "b": {"track_id": "b", "artist": "B", "title": "Two"},
        "c": {"track_id": "c", "artist": "C", "title": "Three"},
    }
    widget.set_map(model, ref_map)
    app.processEvents()

    assert widget.edge_mode.currentData() == "focused"
    assert widget.edge_mode.isHidden()
    assert widget.zoom_in_button.accessibleName() == "Zoom into Music Map"
    assert widget.zoom_out_button.accessibleName() == "Zoom out of Music Map"
    assert widget.zoom_in_button.toolTip().startswith("Zoom in")
    assert widget.zoom_out_button.toolTip().startswith("Zoom out")
    assert len(widget.edge_items) == 0
    assert "deep cut from an album you enjoyed" in widget.node_items["a"].toolTip()
    widget.connections_button.click()
    app.processEvents()
    assert widget.edge_mode.isVisible()
    assert widget.node_items["a"].boundingRect().width() == 86.0
    assert widget.node_items["a"].boundingRect().height() == 86.0
    assert widget.view.minimumHeight() >= 340

    widget.view.centerOn(500, 400)
    widget.view.scale(1.2, 1.2)
    before_center = widget.view.mapToScene(widget.view.viewport().rect().center())
    before_scale = float(widget.view.transform().m11())
    widget.set_map(model, ref_map)
    app.processEvents()
    after_center = widget.view.mapToScene(widget.view.viewport().rect().center())
    assert abs(float(widget.view.transform().m11()) - before_scale) < 0.01
    assert abs(after_center.x() - before_center.x()) < 3
    assert abs(after_center.y() - before_center.y()) < 3

    widget._select_ref("a")
    app.processEvents()
    assert len(widget.edge_items) == 1
    assert "deep cut from an album you enjoyed" in widget.status.text()

    all_links = widget.edge_mode.findData("sonic")
    assert all_links >= 0
    widget.edge_mode.setCurrentIndex(all_links)
    app.processEvents()
    assert len(widget.edge_items) == 2

    widget.close()
    app.processEvents()


def test_dense_music_maps_use_small_cover_points_for_overview():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    widget = MusicMapWidget()
    nodes = [
        {"ref": str(i), "artist": f"Artist {i}", "album": f"Album {i}", "title": f"Track {i}", "x": (i % 40) / 20 - 1, "y": (i % 30) / 15 - 1}
        for i in range(600)
    ]
    refs = {str(i): {"track_id": str(i), "artist": f"Artist {i}", "album": f"Album {i}", "title": f"Track {i}"} for i in range(600)}
    widget.set_map({"nodes": nodes, "edges": [], "analysed": 600}, refs)
    assert widget.node_items["0"].boundingRect().width() == 28.0
    assert widget.node_items["0"].boundingRect().height() == 28.0
    widget.close()
    app.processEvents()


def test_music_map_album_art_nodes_expand_into_hover_detail_cards():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    widget = MusicMapWidget()
    nodes = [{
        "ref": "a",
        "artist": "Artist A",
        "album": "Album A",
        "title": "Track A",
        "x": 0.0,
        "y": 0.0,
        "bpm": 120,
        "energy": 0.75,
        "taste": 0.4,
    }]
    refs = {"a": {"track_id": "a", "artist": "Artist A", "album": "Album A", "title": "Track A"}}
    requested = []
    widget.artworkRequested.connect(requested.append)
    widget.set_map({"nodes": nodes, "edges": [], "analysed": 1}, refs)
    assert requested and requested[0][0]["track"]["album"] == "Album A"

    image = QImage(64, 64, QImage.Format_ARGB32)
    image.fill(QColor("#cc4477"))
    assert widget.set_artwork({
        "a": {"generation": widget._art_generation, "image": image},
    }) is None
    item = widget.node_items["a"]
    assert not item._artwork.isNull()
    center = item.mapToScene(item.boundingRect().center())
    item._hovered = True
    item._resize_on_hover(True)
    assert item.boundingRect().width() == 296.0
    assert item.boundingRect().height() == 148.0
    expanded_center = item.mapToScene(item.boundingRect().center())
    assert abs(center.x() - expanded_center.x()) < 0.01
    assert abs(center.y() - expanded_center.y()) < 0.01

    widget.close()
    app.processEvents()


def test_album_wall_pan_and_zoom_survive_repeated_resizes():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.album_wall import AlbumWallWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    widget = AlbumWallWidget()
    widget.resize(1000, 700)
    widget.show()
    widget.set_model(_album_model(80), {})
    app.processEvents()

    widget.view.centerOn(900, 500)
    widget.view.scale(1.15, 1.15)
    app.processEvents()
    center = widget.view.mapToScene(widget.view.viewport().rect().center())
    scale = float(widget.view.transform().m11())

    for size in ((820, 560), (1180, 780), (940, 660), (760, 520)):
        widget.resize(*size)
        app.processEvents()
        center_after = widget.view.mapToScene(widget.view.viewport().rect().center())
        assert abs(center_after.x() - center.x()) < 4
        assert abs(center_after.y() - center.y()) < 4
        assert abs(float(widget.view.transform().m11()) - scale) < 0.01

    widget.close()
    app.processEvents()


def test_music_map_pan_and_zoom_survive_repeated_resizes():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    widget = MusicMapWidget()
    widget.resize(1100, 760)
    widget.show()
    nodes = [
        {"ref": f"r{i}", "artist": f"Artist {i}", "title": f"Track {i}",
         "x": (i % 5) / 2 - 1, "y": (i // 5) / 2 - 1}
        for i in range(20)
    ]
    refs = {
        row["ref"]: {"track_id": row["ref"], "artist": row["artist"], "title": row["title"]}
        for row in nodes
    }
    widget.set_map({"nodes": nodes, "edges": [], "analysed": 20}, refs)
    app.processEvents()

    widget.view.centerOn(700, 410)
    widget.view.scale(1.2, 1.2)
    app.processEvents()
    center = widget.view.mapToScene(widget.view.viewport().rect().center())
    scale = float(widget.view.transform().m11())

    for size in ((820, 560), (1220, 800), (960, 640), (760, 520)):
        widget.resize(*size)
        app.processEvents()
        center_after = widget.view.mapToScene(widget.view.viewport().rect().center())
        assert abs(center_after.x() - center.x()) < 4
        assert abs(center_after.y() - center.y()) < 4
        assert abs(float(widget.view.transform().m11()) - scale) < 0.01

    widget.close()
    app.processEvents()


def test_main_window_resize_stays_stable_and_restores_geometry(monkeypatch, tmp_path: Path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    class Settings:
        values = {}

        def __init__(self, *_args):
            pass

        def value(self, key):
            return self.values.get(key)

        def setValue(self, key, value):
            self.values[key] = value

    monkeypatch.setattr(main_window, "QSettings", Settings)
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)

    app = QApplication.instance() or QApplication([])
    screen = app.primaryScreen()
    available = screen.availableGeometry()
    window = main_window.MainWindow()
    window.show()
    app.processEvents()

    sizes = (
        (int(available.width() * 0.72), int(available.height() * 0.72)),
        (int(available.width() * 0.92), int(available.height() * 0.88)),
        (int(available.width() * 0.78), int(available.height() * 0.76)),
    )
    for width, height in sizes:
        window.resize(width, height)
        app.processEvents()
        target_y = max(
            available.top() + 12,
            available.bottom() - window.height() - 12,
        )
        window.move(available.left() + 12, target_y)
        app.processEvents()
        QTest.qWait(80)
        stable_geometry = window.geometry()
        QTest.qWait(80)
        assert window.geometry() == stable_geometry
        assert window.width() <= available.width()
        assert window.height() <= available.height()
        assert window.frameGeometry().bottom() < available.bottom()

    saved_geometry = window.geometry()
    window.close()
    app.processEvents()

    restored = main_window.MainWindow()
    assert restored.geometry() == saved_geometry
    restored.close()
    app.processEvents()


def test_spatial_pages_use_progressive_disclosure(monkeypatch, tmp_path: Path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)

    window = main_window.MainWindow()
    available = app.primaryScreen().availableGeometry()
    assert window.width() <= available.width()
    assert window.height() <= available.height()
    window.show()
    app.processEvents()

    window.open_page("album_wall")
    app.processEvents()
    QTest.qWait(window._page_refresh_delay_ms + 10)
    app.processEvents()
    assert window.album_wall_power_panel.isHidden()

    window.power_toggle.setChecked(True)
    app.processEvents()
    assert window.album_wall_power_panel.isHidden()

    window.album_wall_options_button.click()
    app.processEvents()
    assert not window.album_wall_power_panel.isHidden()

    window.open_page("music_map")
    app.processEvents()
    QTest.qWait(window._page_refresh_delay_ms + 10)
    app.processEvents()
    journey = window.journey_workspace
    assert journey.music_map_options_panel.isHidden()
    assert journey.music_map_power_panel.isHidden()
    assert journey.music_map_journey_panel.isHidden()

    window._power_changed(None, announce=False)
    app.processEvents()
    assert journey.music_map_options_panel.isHidden()
    assert journey.music_map_power_panel.isHidden()
    assert journey.music_map_journey_panel.isHidden()

    journey.music_map_options_button.click()
    app.processEvents()
    assert not journey.music_map_options_panel.isHidden()
    assert journey.music_map_power_panel.isHidden()

    journey.music_map_plan_button.click()
    app.processEvents()
    assert not journey.music_map_power_panel.isHidden()
    assert journey.music_map_journey_panel.isHidden()

    journey._toggle_music_journey_options()
    app.processEvents()
    assert not journey.music_map_journey_panel.isHidden()

    window.close()
    app.processEvents()


def test_music_map_floating_tools_keep_canvas_geometry_and_camera(monkeypatch, tmp_path: Path):
    """MM2-1a: opening tools must never steal height from the map."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)

    window = main_window.MainWindow()
    window.show()
    window.open_page("music_map")
    app.processEvents()
    QTest.qWait(window._page_refresh_delay_ms + 10)
    app.processEvents()
    journey = window.journey_workspace
    canvas = journey.music_map
    view = canvas.view

    # The initial camera and canvas dimensions are part of the user's context.
    view.centerOn(620.0, 400.0)
    view.scale(1.2, 1.2)
    app.processEvents()
    canvas_geometry = canvas.geometry()
    view_geometry = view.geometry()
    scale_before = float(view.transform().m11())
    center_before = view.mapToScene(view.viewport().rect().center())

    journey.music_map_options_button.click()
    app.processEvents()
    assert journey.music_map_options_panel.isVisible()
    assert journey.music_map_options_panel.parentWidget() is journey.music_map_page
    assert canvas.geometry() == canvas_geometry
    assert view.geometry() == view_geometry

    # Journey replaces View; neither overlays should take layout height.
    journey.music_map_plan_button.click()
    app.processEvents()
    assert not journey.music_map_options_panel.isVisible()
    assert journey.music_map_power_scroll.isVisible()
    assert journey.music_map_power_scroll.parentWidget() is journey.music_map_page
    assert canvas.geometry() == canvas_geometry
    assert view.geometry() == view_geometry
    assert canvas_geometry.contains(journey.music_map_power_scroll.geometry())
    assert abs(float(view.transform().m11()) - scale_before) < 0.01
    center_after = view.mapToScene(view.viewport().rect().center())
    assert abs(center_after.x() - center_before.x()) < 3
    assert abs(center_after.y() - center_before.y()) < 3

    journey._toggle_music_journey_options()
    app.processEvents()
    assert canvas.geometry() == canvas_geometry
    assert view.geometry() == view_geometry

    journey.music_map_plan_button.click()
    app.processEvents()
    assert not journey.music_map_power_scroll.isVisible()
    assert canvas.geometry() == canvas_geometry

    window.close()
    app.processEvents()
