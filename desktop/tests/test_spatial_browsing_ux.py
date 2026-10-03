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
        {"ref": "a", "artist": "A", "title": "One", "x": -0.7, "y": 0.0, "taste": 0.5, "rediscovery": 0.1},
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
    assert len(widget.edge_items) == 0
    assert widget.view.minimumHeight() >= 500

    widget._select_ref("a")
    app.processEvents()
    assert len(widget.edge_items) == 1

    all_links = widget.edge_mode.findData("sonic")
    assert all_links >= 0
    widget.edge_mode.setCurrentIndex(all_links)
    app.processEvents()
    assert len(widget.edge_items) == 2

    widget.close()
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
