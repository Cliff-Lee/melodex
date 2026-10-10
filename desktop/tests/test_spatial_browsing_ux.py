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
    assert not widget.edge_mode.isVisible()
    assert widget.zoom_in_button.accessibleName() == "Zoom into Music Map"
    assert widget.zoom_out_button.accessibleName() == "Zoom out of Music Map"
    assert widget.zoom_in_button.toolTip().startswith("Zoom in")
    assert widget.zoom_out_button.toolTip().startswith("Zoom out")
    assert len(widget.edge_items) == 0
    assert "deep cut from an album you enjoyed" in widget.node_items["a"].toolTip()
    widget.view_button.click()
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


def test_mm2_compact_controls_and_track_context(monkeypatch, tmp_path: Path):
    """A map selection reveals actions without adding global toolbar clutter."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda:tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self:None)

    window=main_window.MainWindow()
    window.show()
    window.open_page("music_map")
    app.processEvents()
    QTest.qWait(window._page_refresh_delay_ms+10)
    app.processEvents()
    workspace=window.journey_workspace
    canvas=workspace.music_map
    assert workspace.music_map_track_panel.isHidden()
    assert canvas.view_settings_panel.isHidden()
    assert workspace.music_map_play_button.parentWidget() is workspace.music_map_track_panel
    assert workspace.music_map_queue_button.parentWidget() is workspace.music_map_track_panel
    assert workspace.music_map_plan_button.text()=="Journey"
    assert canvas.view_button.text()=="View"

    tracks={
        "a":{"track_id":"a","artist":"First Artist","album":"First Album","title":"First Track"},
        "b":{"track_id":"b","artist":"Second Artist","album":"Second Album","title":"Second Track"},
    }
    model={"nodes":[
        {"ref":"a","title":"First Track","artist":"First Artist","x":-0.5,"y":0.0},
        {"ref":"b","title":"Second Track","artist":"Second Artist","x":0.5,"y":0.2},
    ],"edges":[],"analysed":2}
    canvas.set_map(model,tracks)
    app.processEvents()
    assert workspace.music_map_track_panel.isHidden()

    playback_requests=[]
    workspace.playTracksRequested.connect(lambda rows:playback_requests.append(rows))
    canvas._select_ref("a")
    app.processEvents()
    assert workspace.music_map_track_panel.isVisible()
    assert "First Artist" in workspace.music_map_track_label.text()
    assert workspace.music_map_play_button.isEnabled()
    assert workspace.music_map_queue_button.isEnabled()
    assert workspace.music_map_start_journey_button.isEnabled()
    assert not playback_requests  # Selecting never triggers playback.

    rect=canvas.geometry()
    before_scale=float(canvas.view.transform().m11())
    workspace.music_map_start_journey_button.click()
    app.processEvents()
    assert workspace.music_path_start_ref=="a"
    assert workspace.music_map_quick_route_panel.isVisible()
    assert not workspace.music_map_power_scroll.isVisible()
    assert workspace.music_map_track_panel.isHidden()
    assert not workspace.music_map_quick_preview_button.isEnabled()
    assert canvas.geometry()==rect
    assert abs(float(canvas.view.transform().m11())-before_scale)<0.01

    # Escape dismisses the compact route without stopping or unselecting.
    canvas.search.setFocus()
    QTest.keyClick(canvas.search, Qt.Key_Escape)
    app.processEvents()
    assert not workspace.music_map_quick_route_panel.isVisible()
    assert not workspace._map_quick_route_active
    assert canvas.selected_ref_value()=="a"
    assert workspace.music_map_track_panel.isVisible()
    assert not playback_requests
    window.close()
    app.processEvents()


def test_mm2_view_settings_are_overlay_not_an_expanding_toolbar(monkeypatch, tmp_path: Path):
    """View menu keeps colour/connection options without resizing the map."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtTest import QTest
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window,"app_data_dir",lambda:tmp_path)
    monkeypatch.setattr(main_window.MainWindow,"_start_local_bridge",lambda self:None)
    window=main_window.MainWindow()
    window.show()
    window.open_page("music_map")
    app.processEvents()
    QTest.qWait(window._page_refresh_delay_ms+10)
    app.processEvents()
    workspace=window.journey_workspace
    canvas=workspace.music_map
    rect=canvas.geometry()
    viewport=canvas.view.geometry()
    scale=float(canvas.view.transform().m11())

    canvas.view_button.click()
    app.processEvents()
    assert canvas.view_settings_panel.isVisible()
    assert canvas.mode.isVisible()
    assert canvas.edge_mode.isVisible()
    assert canvas.geometry()==rect
    assert canvas.view.geometry()==viewport
    assert canvas.mode.isVisible()
    assert canvas.view_settings_panel.geometry().height() <= 172

    workspace.music_map_plan_button.click()
    app.processEvents()
    assert not canvas.view_settings_panel.isVisible()
    assert workspace.music_map_power_scroll.isVisible()
    workspace.music_map_options_button.click()
    app.processEvents()
    assert not workspace.music_map_power_scroll.isVisible()
    assert workspace.music_map_options_panel.isVisible()
    assert canvas.geometry()==rect
    assert canvas.view.geometry()==viewport
    assert abs(float(canvas.view.transform().m11())-scale)<0.01

    window.close()
    app.processEvents()


def test_mm2_overlays_respect_graphics_view_and_keep_track_actions_clear(monkeypatch, tmp_path: Path):
    """MM2-1c: tools stay below search, and selection never covers the Journey drawer."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import QRect, Qt
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

    workspace = window.journey_workspace
    canvas = workspace.music_map
    model = {"nodes": [
        {"ref": "a", "title": "Long Track Name " * 8, "artist": "Artist One", "x": -0.5, "y": 0},
        {"ref": "b", "title": "Track Two", "artist": "Artist Two", "x": 0.5, "y": 0},
    ], "edges": [], "analysed": 2}
    tracks = {
        "a": {"track_id": "a", "title": "Long Track Name " * 8, "artist": "Artist One"},
        "b": {"track_id": "b", "title": "Track Two", "artist": "Artist Two"},
    }
    canvas.set_map(model, tracks)
    canvas._select_ref("a")
    app.processEvents()
    assert workspace.music_map_track_panel.isVisible()
    assert workspace.music_map_track_label.toolTip().startswith("Artist One")
    assert len(workspace.music_map_track_label.text()) < len(workspace.music_map_track_label.toolTip())

    start_geom = canvas.geometry()
    start_view_geom = canvas.view.geometry()
    def viewport_rect():
        return QRect(
            canvas.mapTo(workspace.music_map_page, canvas.view.geometry().topLeft()),
            canvas.view.size(),
        )

    workspace.music_map_options_button.click()
    app.processEvents()
    assert workspace.music_map_options_panel.isVisible()
    assert viewport_rect().contains(workspace.music_map_options_panel.geometry())
    assert workspace.music_map_options_panel.geometry().top() >= viewport_rect().top()
    assert workspace.music_map_track_panel.isHidden()
    assert canvas.geometry() == start_geom
    assert canvas.view.geometry() == start_view_geom

    # View settings takes precedence over More; track actions restore when closed.
    canvas.view_button.click()
    app.processEvents()
    assert canvas.view_settings_panel.isVisible()
    assert workspace.music_map_options_panel.isHidden()
    assert workspace.music_map_track_panel.isHidden()
    canvas.search.setFocus()
    QTest.keyClick(canvas.search, Qt.Key_Escape)
    app.processEvents()
    assert canvas.view_settings_panel.isHidden()
    assert workspace.music_map_track_panel.isVisible()

    workspace.music_map_plan_button.click()
    app.processEvents()
    assert workspace.music_map_power_scroll.isVisible()
    assert viewport_rect().contains(workspace.music_map_power_scroll.geometry())
    assert workspace.music_map_track_panel.isHidden()
    canvas._select_ref("b")
    app.processEvents()
    assert workspace.music_map_track_panel.isHidden()
    assert workspace._music_map_track_full_label.startswith("Artist Two")
    canvas.search.setFocus()
    QTest.keyClick(canvas.search, Qt.Key_Escape)
    app.processEvents()
    assert workspace.music_map_power_scroll.isHidden()
    assert workspace.music_map_track_panel.isVisible()
    assert "Artist Two" in workspace.music_map_track_label.text()
    assert canvas.selected_ref_value() == "b"
    assert canvas.geometry() == start_geom
    window.close()
    app.processEvents()


def test_mm2_location_history_search_now_playing_and_safe_unmapped_fallback():
    """MM2-2a: camera visits are reversible and never emit a playback request."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    widget = MusicMapWidget()
    widget.resize(700, 460)
    widget.show()
    model = {"nodes": [
        {"ref": "a", "artist": "Alpha", "title": "First", "x": -0.75, "y": 0},
        {"ref": "b", "artist": "Beta", "title": "Second", "x": 0, "y": 0},
        {"ref": "c", "artist": "Gamma", "title": "Third", "x": 0.75, "y": 0},
    ], "edges": [], "analysed": 3}
    tracks = {
        ref: {"track_id": ref, "artist": name, "title": title}
        for ref, name, title in [
            ("a", "Alpha", "First"), ("b", "Beta", "Second"), ("c", "Gamma", "Third"),
        ]
    }
    widget.set_map(model, tracks)
    app.processEvents()
    assert not widget.back_button.isEnabled()
    assert not widget.forward_button.isEnabled()
    assert not widget.now_playing_button.isEnabled()

    selections = []
    widget.trackSelected.connect(selections.append)
    widget.view.centerOn(640, 410)
    widget.view.scale(1.1, 1.1)
    app.processEvents()
    home = widget._capture_location()

    assert widget.focus_ref("a")
    assert widget.selected_ref_value() == "a"
    assert widget.back_button.isEnabled()
    assert not widget.forward_button.isEnabled()
    at_a = widget._capture_location()

    widget.search.setText("Gamma")
    widget.search.returnPressed.emit()
    app.processEvents()
    assert widget.selected_ref_value() == "c"
    assert widget._capture_location()[3] == "c"

    widget.back_button.click()
    app.processEvents()
    assert widget.selected_ref_value() == "a"
    restored = widget._capture_location()
    assert abs(restored[0] - at_a[0]) < 4
    assert abs(restored[1] - at_a[1]) < 4
    assert widget.forward_button.isEnabled()

    widget.forward_button.click()
    app.processEvents()
    assert widget.selected_ref_value() == "c"
    # Keyboard navigation works with the search control focused, without
    # introducing separate Qt shortcut objects or changing playback.
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    widget.search.setFocus()
    QTest.keyClick(widget.search, Qt.Key_Left, Qt.AltModifier)
    app.processEvents()
    assert widget.selected_ref_value() == "a"
    QTest.keyClick(widget.search, Qt.Key_Right, Qt.AltModifier)
    app.processEvents()
    assert widget.selected_ref_value() == "c"
    widget.navigate_back()
    widget.navigate_back()
    app.processEvents()
    assert widget.selected_ref_value() == home[3]
    assert abs(widget._capture_location()[0] - home[0]) < 4
    assert abs(widget._capture_location()[2] - home[2]) < 0.01

    # Navigating somewhere new after Back cuts off the previous Forward path.
    widget.focus_ref("b")
    assert widget.selected_ref_value() == "b"
    assert not widget.forward_button.isEnabled()

    # Following playback never moves the map until the user deliberately asks.
    widget.highlight_track(tracks["c"])
    assert widget.now_playing_button.isEnabled()
    before = widget._capture_location()
    assert widget._capture_location() == before
    assert widget.locate_now_playing()
    assert widget.selected_ref_value() == "c"
    widget.navigate_back()
    assert widget.selected_ref_value() == "b"

    widget.highlight_track({"track_id": "not-mapped", "artist": "Off-map", "title": "Elsewhere"})
    before = widget._capture_location()
    assert not widget.locate_now_playing()
    assert widget._capture_location() == before
    assert "not in this map" in widget.status.text()
    assert widget.now_playing_button.isEnabled()  # Explains why locating is unavailable.

    widget._fit_with_history()
    assert widget.back_button.isEnabled()
    widget.set_map(model, tracks)
    assert not widget.back_button.isEnabled()
    assert not widget.forward_button.isEnabled()
    assert selections  # Selection signals are UI-only and never start playback.
    widget.close()
    app.processEvents()


def test_mm2_navigation_via_workspace_does_not_start_music(monkeypatch, tmp_path: Path):
    """Find Playing operates through existing workspace track updates."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtTest import QTest
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
    ws = window.journey_workspace
    model = {"nodes": [
        {"ref": "a", "artist": "Example", "title": "Example Song", "x": 0, "y": 0}
    ], "edges": [], "analysed": 1}
    track = {"track_id": "a", "artist": "Example", "title": "Example Song"}
    ws.music_map.set_map(model, {"a": track})
    requests = []
    ws.playTracksRequested.connect(requests.append)
    ws.on_track_changed(track)
    assert ws.music_map.now_playing_button.isEnabled()
    ws.music_map.now_playing_button.click()
    app.processEvents()
    assert ws.music_map.selected_ref_value() == "a"
    assert ws.music_map_track_panel.isVisible()
    assert requests == []
    window.close()
    app.processEvents()


def test_mm2_related_tracks_use_graph_evidence_not_canvas_distance():
    """Only real sonic edges and cached relationships may be recommended."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    widget = MusicMapWidget()
    widget.resize(1000, 660)
    widget.show()
    refs = {
        key: {"track_id": key, "artist": f"Artist {key}", "title": f"Track {key}"}
        for key in ("a", "b", "c", "d", "e")
    }
    model = {
        "nodes": [
            {"ref": ref, "artist": f"Artist {ref}", "title": f"Track {ref}",
             "x": 0.0 if ref in ("a", "e") else i / 4, "y": i / 4}
            for i, ref in enumerate(refs)
        ],
        "edges": [
            {"a": "a", "b": "b", "similarity": 0.72},
            {"a": "c", "b": "a", "similarity": 0.89},
            {"a": "a", "b": "unknown", "similarity": 0.98},
            {"a": "b", "b": "c", "similarity": 0.99},
        ],
        "analysed": len(refs),
    }
    graph = {"edges": [
        {"a": "a", "b": "d", "kind": "production", "label": "Shared producer",
         "strength": 0.91, "evidence": "MusicBrainz credits"},
        {"a": "a", "b": "b", "kind": "artist", "label": "Artist b",
         "strength": 0.65},
        {"a": "e", "b": "d", "kind": "album", "label": "Album Z", "strength": 0.8},
    ]}
    widget.set_map(model, refs, knowledge_graph=graph)
    result = widget.related_tracks("a", 2)
    assert [r["ref"] for r in result] == ["c", "d"]
    assert result[0]["kind"] == "Sonic neighbour"
    assert "89%" in result[0]["reason"]
    assert result[1]["kind"] == "Production"
    assert "MusicBrainz" in result[1]["reason"]
    assert widget.related_tracks("a", 8)[2]["ref"] == "b"
    assert "e" not in [r["ref"] for r in widget.related_tracks("a", 8)]
    assert [r["ref"] for r in widget.related_tracks("e")] == ["d"]
    assert widget.related_tracks("unknown") == []
    widget.close()
    app.processEvents()


def test_mm2_explore_nearby_chips_are_contextual_and_do_not_start_audio(monkeypatch, tmp_path: Path):
    """Selecting another mapped song is navigation, not a playback request."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window,"app_data_dir",lambda:tmp_path)
    monkeypatch.setattr(main_window.MainWindow,"_start_local_bridge",lambda self:None)
    window=main_window.MainWindow()
    window.show()
    window.open_page("music_map")
    app.processEvents()
    QTest.qWait(window._page_refresh_delay_ms+10)
    app.processEvents()
    ws=window.journey_workspace
    widget=ws.music_map
    tracks={
        "a":{"track_id":"a","artist":"Alpha","title":"First Song"},
        "b":{"track_id":"b","artist":"Beta","title":"Second Song"},
        "c":{"track_id":"c","artist":"Gamma","title":"Third Song"},
    }
    model={"nodes":[
        {"ref":"a","artist":"Alpha","title":"First Song","x":-0.6,"y":0.0},
        {"ref":"b","artist":"Beta","title":"Second Song","x":0.1,"y":0.3},
        {"ref":"c","artist":"Gamma","title":"Third Song","x":0.7,"y":-0.2},
    ],"edges":[{"a":"a","b":"b","similarity":0.86}],"analysed":3}
    widget.set_map(model,tracks,knowledge_graph={
        "edges":[{"a":"a","b":"c","kind":"album","label":"Album C",
                  "strength":0.87,"evidence":"local album metadata"}]
    })
    app.processEvents()
    playback=[]
    queued=[]
    ws.playTracksRequested.connect(playback.append)
    ws.queueTracksRequested.connect(queued.append)
    widget._select_ref("a")
    app.processEvents()
    assert ws.music_map_nearby_label.isVisible()
    assert len(ws._music_map_related_refs)==2
    assert "Sonic" in ws.music_map_related_buttons[0].toolTip()
    assert "Same album" in ws.music_map_related_buttons[1].toolTip()
    assert ws.music_map_track_panel.isVisible()
    start_geom=widget.geometry()

    ws.music_map_related_buttons[0].click()
    app.processEvents()
    assert widget.selected_ref_value()=="b"
    assert widget.back_button.isEnabled()
    assert ws._music_map_related_refs == ["a"]
    assert ws.music_map_nearby_label.isVisible()
    assert not playback and not queued
    widget.navigate_back()
    app.processEvents()
    assert widget.selected_ref_value()=="a"
    assert ws.music_map_nearby_label.isVisible()

    ws.music_map_plan_button.click()
    app.processEvents()
    assert ws.music_map_power_scroll.isVisible()
    assert ws.music_map_track_panel.isHidden()
    widget._select_ref("c")
    app.processEvents()
    assert ws.music_map_track_panel.isHidden()
    ws._dismiss_music_map_overlays()
    app.processEvents()
    assert ws.music_map_track_panel.isVisible()
    assert widget.geometry()==start_geom
    assert not playback and not queued
    window.close()
    app.processEvents()


def test_mm2_cluster_drilldown_restores_map_and_protects_playing_track():
    """Clustering is only a visual LOD change: tracks and navigation remain intact."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    widget = MusicMapWidget()
    widget.resize(900, 620)
    widget.show()
    nodes = []
    ref_map = {}
    for i in range(220):
        ref = f"t{i}"
        x = -0.6 + (i % 11) * 0.008 if i < 110 else 0.45 + (i % 11) * 0.008
        y = 0.2 + (i % 9) * 0.008 if i < 110 else -0.3 + (i % 9) * 0.008
        nodes.append({"ref": ref, "title": f"Track {i}", "artist": f"Artist {i}",
                      "x": x, "y": y})
        ref_map[ref] = {"track_id": ref, "artist": f"Artist {i}",
                        "title": f"Track {i}"}
    widget.set_map({"nodes": nodes, "edges": [
        {"a": "t3", "b": "t4", "similarity": 0.89},
    ], "analysed": 220}, ref_map)
    app.processEvents()
    assert len(widget.node_items) == 220
    assert widget._cluster_items
    assert widget.regions_button.isVisible()
    assert len(widget._cluster_items) < 220
    assert all(cluster.landmark for cluster in widget._cluster_items)
    # Stored sonic edges remain in the scene but are invisible behind groups.
    idx = widget.edge_mode.findData("sonic")
    widget.edge_mode.setCurrentIndex(idx)
    app.processEvents()
    assert len(widget.edge_items) == 1
    assert not widget.edge_items[0].isVisible()
    members = widget._cluster_items[0].members
    assert len(members) >= 3
    assert all(not widget.node_items[ref].isVisible() for ref in members)

    # Selected and currently playing points are always exposed individually.
    pinned = members[0]
    widget._select_ref(pinned)
    assert widget.node_items[pinned].isVisible()
    assert widget.node_items[pinned].zValue() > widget._cluster_items[0].zValue()
    widget.highlight_track(ref_map[members[1]])
    assert widget.node_items[members[1]].isVisible()
    widget.set_route_endpoints(pinned, members[2])
    assert widget.node_items[members[2]].isVisible()

    # No music starts when an overview cluster is opened.
    activated = []
    widget.trackActivated.connect(activated.append)
    before = widget._capture_location()
    cluster_members = widget._cluster_items[0].members
    widget._open_cluster(cluster_members)
    app.processEvents()
    assert abs(widget.view.transform().m11() - 1.55) < 0.01
    assert not widget.regions_button.isVisible()
    assert not widget._cluster_items
    assert all(item.isVisible() for item in widget.node_items.values())
    assert widget.edge_items[0].isVisible()
    assert not activated
    assert widget.back_button.isEnabled()
    widget.navigate_back()
    app.processEvents()
    assert abs(widget.view.transform().m11() - before[2]) < 0.01
    assert widget._cluster_items
    assert widget.regions_button.isVisible()
    assert len(widget.node_items) == 220
    assert widget.selected_ref_value() == pinned

    widget.close()
    app.processEvents()


def test_mm2_sparse_music_map_does_not_replace_album_covers_with_clusters():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")
    app = QApplication.instance() or QApplication([])
    widget = MusicMapWidget()
    widget.resize(960, 640)
    widget.show()
    nodes = [
        {"ref": f"r{i}", "artist": f"Artist {i}", "title": f"Song {i}",
         "x": i / 15.0 - 1, "y": i / 15.0 - 1}
        for i in range(28)
    ]
    ref_map = {row["ref"]: {"track_id": row["ref"], "artist": row["artist"],
                            "title": row["title"]} for row in nodes}
    widget.set_map({"nodes": nodes, "edges": [], "analysed": 28}, ref_map)
    app.processEvents()
    assert not widget._cluster_items
    assert all(item.isVisible() for item in widget.node_items.values())
    widget.close()
    app.processEvents()


def test_mm2_region_navigation_menu_is_reversible_and_does_not_play():
    """Region chooser provides an optional compact index; no playback effects."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")
    app = QApplication.instance() or QApplication([])
    widget = MusicMapWidget()
    widget.resize(960, 680)
    widget.show()
    nodes = []
    tracks = {}
    for i in range(120):
        ref = f"t{i}"
        x = -0.55 + (i % 6) * 0.015 if i < 60 else 0.55 + (i % 6) * 0.015
        y = -0.50 + (i % 10) * 0.013 if i < 60 else 0.55 + (i % 10) * 0.013
        artist = "Northbound" if i < 60 else "The Islands"
        nodes.append({"ref": ref, "x": x, "y": y, "artist": artist,
                      "title": f"Song {i}"})
        tracks[ref] = {"track_id": ref, "artist": artist, "title": f"Song {i}"}
    widget.set_map({"nodes": nodes, "edges": [], "analysed": 120}, tracks)
    app.processEvents()
    assert widget.regions_button.isVisible()
    assert widget._cluster_items
    before = widget._capture_location()
    activated = []
    widget.trackActivated.connect(activated.append)
    widget.regions_button.click()
    app.processEvents()
    actions = widget.region_menu.actions()
    assert 1 <= len(actions) <= 8
    assert any("Northbound" in action.text() for action in actions)
    assert any("The Islands" in action.text() for action in actions)
    assert all("mapped tracks" in action.text() for action in actions)

    actions[0].trigger()
    app.processEvents()
    assert abs(float(widget.view.transform().m11()) - 1.55) < 0.01
    assert not widget.regions_button.isVisible()
    assert not activated
    assert widget.back_button.isEnabled()
    widget.navigate_back()
    app.processEvents()
    assert widget.regions_button.isVisible()
    assert abs(widget._capture_location()[2] - before[2]) < 0.01
    assert not activated
    widget.set_map({"nodes": [], "edges": [], "analysed": 0}, {})
    app.processEvents()
    assert not widget.regions_button.isVisible()
    assert widget.region_menu.isHidden()
    widget.close()
    app.processEvents()


def test_mm2_incremental_map_update_preserves_spatial_landmarks():
    """An axis-mirrored refresh should not make existing tracks jump."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")
    app = QApplication.instance() or QApplication([])
    widget = MusicMapWidget()
    widget.resize(900, 640)
    widget.show()
    nodes = []
    tracks = {}
    for i in range(16):
        ref = f"t{i:02d}"
        x = -0.65 + (i % 4) * 0.35
        y = -0.55 + (i // 4) * 0.30
        nodes.append({"ref": ref, "x": x, "y": y, "artist": "Local", "title": ref})
        tracks[ref] = {"track_id": ref, "artist": "Local", "title": ref}
    widget.set_map({"nodes": nodes, "edges": [], "analysed": 16}, tracks)
    app.processEvents()
    positions = dict(widget.positions)
    widget.focus_ref("t06")
    center_before = widget._capture_location()
    updated = [
        {**node, "x": -node["y"], "y": node["x"]}
        for node in nodes
    ]
    updated.append({"ref": "new", "x": 0.15, "y": 0.25,
                    "artist": "New", "title": "New Track"})
    widget.set_map(
        {"nodes": updated, "edges": [], "analysed": len(updated)},
        {**tracks, "new": {"track_id": "new", "artist": "New", "title": "New Track"}},
    )
    app.processEvents()
    for ref, old_xy in positions.items():
        new_xy = widget.positions[ref]
        assert abs(old_xy[0] - new_xy[0]) < 0.02
        assert abs(old_xy[1] - new_xy[1]) < 0.02
    assert widget.selected_ref_value() == "t06"
    assert abs(widget._capture_location()[0] - center_before[0]) < 4
    assert not widget.back_button.isEnabled()
    assert len(widget.node_items) == 17
    widget.close()
    app.processEvents()


def test_mm2_cluster_zoom_hysteresis_keeps_items_stable_near_threshold():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")
    app = QApplication.instance() or QApplication([])
    widget = MusicMapWidget()
    widget.resize(900, 600)
    widget.show()
    nodes = [{"ref": f"r{i}", "x": -0.5 + (i % 12) * 0.007,
              "y": 0.5 + (i // 12) * 0.006} for i in range(120)]
    tracks = {row["ref"]: {"track_id": row["ref"], "artist": "Same",
                            "title": row["ref"]} for row in nodes}
    widget.set_map({"nodes": nodes, "edges": [], "analysed": 120}, tracks)
    widget.view.resetTransform()
    widget.view.scale(0.91, 0.91)
    widget._refresh_clusters()
    app.processEvents()
    initial = [id(item) for item in widget._cluster_items]
    assert initial
    widget.view.scale(0.94 / 0.91, 0.94 / 0.91)
    widget._refresh_clusters()
    app.processEvents()
    assert [id(item) for item in widget._cluster_items] == initial
    widget.view.scale(1.02 / 0.94, 1.02 / 0.94)
    widget._refresh_clusters()
    app.processEvents()
    assert widget._cluster_signature[0] == 125.0
    widget.close()
    app.processEvents()


def test_mm2_small_window_zoom_starts_smoothly_from_fitted_overview():
    """A wheel zoom must not jump from a 0.3-fit view straight to 0.62."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")
    app = QApplication.instance() or QApplication([])
    widget = MusicMapWidget()
    widget.resize(480, 330)
    widget.show()
    nodes = [
        {"ref": f"s{i}", "x": -0.75 + (i % 8)*0.2,
         "y": -0.75 + (i // 8)*0.25}
        for i in range(48)
    ]
    tracks = {
        row["ref"]: {"track_id": row["ref"], "artist": "Local", "title": row["ref"]}
        for row in nodes
    }
    widget.set_map({"nodes": nodes, "edges": [], "analysed": 48}, tracks)
    app.processEvents()
    fitted = float(widget.view.transform().m11())
    assert fitted < 0.62
    widget.view.smooth_zoom(1.10)
    target = float(widget.view._zoom_animation.endValue())
    assert abs(target - fitted * 1.10) < 0.01
    assert target < 0.62
    # An explicit navigation must cancel the unfinished zoom animation.
    widget.focus_ref("s20")
    assert widget.view._zoom_animation.state().value == 0
    widget.view.smooth_zoom(1.15)
    widget.reset_view()
    assert widget.view._zoom_animation.state().value == 0
    widget.close()
    app.processEvents()


def test_mm2_play_from_here_starts_existing_session_only_on_explicit_click(monkeypatch, tmp_path: Path):
    """A selected track anchors Mind + Flow without modifying the player on selection."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtTest import QTest
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")
    app = QApplication.instance() or QApplication([])
    requests = []
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)
    monkeypatch.setattr(
        main_window.MainWindow, "_start_session_from_map_track",
        lambda self, track: requests.append(dict(track)),
    )
    window = main_window.MainWindow()
    window.show()
    window.open_page("music_map")
    app.processEvents()
    QTest.qWait(window._page_refresh_delay_ms + 10)
    app.processEvents()
    ws = window.journey_workspace
    canvas = ws.music_map
    seed = {"track_id": "anchor", "artist": "The Anchor", "title": "Start Here"}
    model = {"nodes": [{"ref": "anchor", "artist": "The Anchor",
                         "title": "Start Here", "x": 0.0, "y": 0.0}],
             "edges": [], "analysed": 1}
    canvas.set_map(model, {"anchor": seed})
    app.processEvents()
    assert ws.music_map_listen_here_button.isEnabled() is False
    assert not requests
    canvas._select_ref("anchor")
    app.processEvents()
    assert ws.music_map_listen_here_button.isEnabled()
    assert ws.music_map_listen_here_button.text() == "Play from here"
    assert not requests
    ws.music_map_listen_here_button.click()
    app.processEvents()
    assert requests == [seed]
    assert not ws.music_map_power_scroll.isVisible()
    assert canvas.selected_ref_value() == "anchor"
    assert ws.music_map_track_panel.isVisible()
    window.close()
    app.processEvents()


def test_mm2_surprise_me_reuses_existing_mind_session_builder(monkeypatch, tmp_path: Path):
    """Surprise me requires an explicit click and keeps the Map uncluttered."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    sessions = []
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)
    monkeypatch.setattr(
        main_window.MainWindow, "_play_for_me",
        lambda self, mode, minutes, adventure: sessions.append(
            (mode, minutes, adventure)
        ),
    )

    window = main_window.MainWindow()
    window.show()
    window.open_page("music_map")
    app.processEvents()
    QTest.qWait(window._page_refresh_delay_ms + 10)
    app.processEvents()

    ws = window.journey_workspace
    canvas = ws.music_map
    assert ws.music_map_surprise_button.isVisible()
    assert ws.music_map_surprise_button.text() == "Surprise me"
    assert ws.music_map_track_panel.isHidden()
    assert not sessions

    canvas_geometry = canvas.geometry()
    camera = canvas._capture_location()
    ws.music_map_surprise_button.click()
    app.processEvents()
    assert len(sessions) == 1
    assert sessions[0] == (
        str(window.mode.currentData() or "balanced"),
        int(window.minutes.currentText()),
        window.adventure.value() / 100,
    )
    assert canvas.geometry() == canvas_geometry
    assert canvas._capture_location() == camera
    assert not ws.music_map_power_scroll.isVisible()
    assert not ws.music_map_options_panel.isVisible()

    window.close()
    app.processEvents()


def test_mm2_play_region_uses_only_cluster_members_and_preserves_camera():
    """The play glyph requests a scoped session; the cluster cover still zooms."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        from melodex.music_map import MusicMapWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    widget = MusicMapWidget()
    widget.resize(980, 700)
    widget.show()
    nodes = []
    tracks = {}
    for i in range(100):
        ref = f"t{i}"
        artist = "North" if i < 50 else "South"
        x = -0.55 + (i % 5) * 0.008 if i < 50 else 0.48 + (i % 5) * 0.008
        y = 0.5 + (i % 7) * 0.008 if i < 50 else -0.48 + (i % 7) * 0.008
        nodes.append({"ref": ref, "x": x, "y": y, "artist": artist,
                      "title": f"Song {i}"})
        tracks[ref] = {"track_id": ref, "local_path": f"/music/{ref}.flac",
                       "artist": artist, "title": f"Song {i}"}
    widget.set_map({"nodes": nodes, "edges": [], "analysed": 100}, tracks)
    app.processEvents()
    assert widget._cluster_items
    requests = []
    activated = []
    widget.regionListenRequested.connect(requests.append)
    widget.trackActivated.connect(activated.append)

    cluster = widget._cluster_items[0]
    before = widget._capture_location()
    # Click the visible play glyph instead of the cover.
    location = cluster.mapToScene(cluster.play_rect().center())
    click_position = widget.view.mapFromScene(location)
    QTest.mouseClick(widget.view.viewport(), Qt.LeftButton, pos=click_position)
    app.processEvents()
    assert len(requests) == 1
    request = requests[0]
    assert request["count"] == len(cluster.members)
    assert {row["track_id"] for row in request["tracks"]} == set(cluster.members)
    assert request["seed"]["track_id"] == cluster.representative
    assert widget._capture_location() == before
    assert not activated

    # Clicking the cover continues to drill down rather than start audio.
    cover = cluster.mapToScene(cluster.boundingRect().center())
    QTest.mouseClick(widget.view.viewport(), Qt.LeftButton,
                     pos=widget.view.mapFromScene(cover))
    app.processEvents()
    assert abs(widget.view.transform().m11() - 1.55) < 0.01
    assert len(requests) == 1
    assert not activated
    widget.close()
    app.processEvents()


def test_mm2_region_session_reuses_mind_engine_with_local_pool(monkeypatch, tmp_path: Path):
    """MainWindow filters the region before handing candidates to Mind."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)
    window = main_window.MainWindow()
    catalog = [
        {"local_path": "/music/stray.flac", "artist": "North", "title": "Not here"},
        {"local_path": "/music/a.flac", "artist": "North", "title": "First"},
        {"local_path": "/music/b.flac", "artist": "North", "title": "Second"},
    ]
    monkeypatch.setattr(window.providers, "local_catalog", lambda: list(catalog))
    # Observe actual candidate selection but do not initiate playback.
    captured = []
    monkeypatch.setattr(
        window.mind, "build_session",
        lambda candidates, path_for, **kwargs: captured.append(
            (list(candidates), kwargs)
        ) or {"tracks": []},
    )
    monkeypatch.setattr(
        window, "_run_async",
        lambda worker, callback, **kwargs: worker(),
    )
    window._start_session_from_map_region({
        "tracks": [
            {"local_path": "/music/b.flac", "artist": "North", "title": "Second"},
            {"local_path": "/music/a.flac", "artist": "North", "title": "First"},
        ],
        "seed": {"local_path": "/music/b.flac", "artist": "North", "title": "Second"},
    })
    assert len(captured) == 1
    candidates, kwargs = captured[0]
    assert {row["local_path"] for row in candidates} == {
        "/music/a.flac", "/music/b.flac"
    }
    assert kwargs["start_track"]["local_path"] == "/music/b.flac"

    captured.clear()
    window._start_session_from_map_region({
        "tracks": [{"local_path": "/gone.flac"}],
        "seed": {"local_path": "/gone.flac"},
    })
    assert not captured  # Stale region does not fall back to the full library.
    window.close()
    app.processEvents()


def test_mm2_quick_journey_a_to_b_uses_map_clicks_and_existing_pathfinder(monkeypatch, tmp_path: Path):
    """Start → destination → preview on the map; no playback until explicit Play."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import Qt
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
    ws, canvas = window.journey_workspace, window.journey_workspace.music_map
    tracks = {
        "a": {"track_id": "a", "artist": "Alpha", "title": "First"},
        "b": {"track_id": "b", "artist": "Beta", "title": "Second"},
        "c": {"track_id": "c", "artist": "Gamma", "title": "Third"},
    }
    model = {
        "nodes": [
            {"ref": "a", "artist": "Alpha", "title": "First", "x": -0.6, "y": 0.1},
            {"ref": "b", "artist": "Beta", "title": "Second", "x": 0.6, "y": -0.1},
            {"ref": "c", "artist": "Gamma", "title": "Third", "x": 0.0, "y": 0.5},
        ],
        "edges": [
            {"a": "a", "b": "b", "similarity": 0.91},
            {"a": "a", "b": "c", "similarity": 0.80},
            {"a": "c", "b": "b", "similarity": 0.81},
        ],
        "analysed": 3,
    }
    canvas.set_map(model, tracks)
    app.processEvents()
    played, queued = [], []
    ws.playTracksRequested.connect(played.append)
    ws.queueTracksRequested.connect(queued.append)
    canvas._select_ref("a")
    ws.music_map_start_journey_button.click()
    app.processEvents()
    rect = canvas.geometry()
    camera = canvas._capture_location()
    assert ws.music_path_start_ref == "a"
    assert not ws.music_path_end_ref
    assert ws.music_map_quick_route_panel.isVisible()

    # Programmatic navigation and Back are not treated as destination clicks.
    canvas.focus_ref("c")
    app.processEvents()
    assert ws.music_path_end_ref == ""
    assert not ws.music_map_quick_preview_button.isEnabled()
    canvas.navigate_back()
    app.processEvents()
    assert ws.music_path_end_ref == ""

    # A genuine click on the destination node arms the preview.
    item = canvas.node_items["b"]
    destination = canvas.view.mapFromScene(item.mapToScene(item.boundingRect().center()))
    QTest.mouseClick(canvas.view.viewport(), Qt.LeftButton, pos=destination)
    app.processEvents()
    assert ws.music_path_end_ref == "b"
    assert ws.music_map_quick_preview_button.isEnabled()
    assert ws.music_map_quick_route_panel.isVisible()
    assert not played and not queued
    assert canvas.geometry() == rect
    assert abs(canvas._capture_location()[2] - camera[2]) < 0.01

    ws.music_map_quick_preview_button.click()
    app.processEvents()
    assert ws.music_path_result.get("found")
    assert ws.music_path_result["path_refs"][0] == "a"
    assert ws.music_path_result["path_refs"][-1] == "b"
    assert canvas.route_result.get("found")
    assert ws.music_map_quick_play_button.isEnabled()
    assert ws.music_map_quick_queue_button.isEnabled()
    assert not played and not queued

    ws.music_map_quick_queue_button.click()
    assert len(queued) == 1
    assert queued[0][0]["track_id"] == "a"
    assert not played
    ws.music_map_quick_play_button.click()
    assert len(played) == 1
    assert played[0][-1]["track_id"] == "b"

    ws.music_map_quick_more_button.click()
    app.processEvents()
    assert ws.music_map_power_scroll.isVisible()
    assert ws.music_map_quick_route_panel.isHidden()
    ws.music_map_quick_more_button.click()
    app.processEvents()
    assert ws.music_map_quick_route_panel.isVisible()

    ws.music_map_quick_cancel_button.click()
    app.processEvents()
    assert not ws.music_map_quick_route_panel.isVisible()
    assert not canvas.route_result
    assert ws.music_path_start_ref == ws.music_path_end_ref == ""
    assert canvas.geometry() == rect

    window.close()
    app.processEvents()
