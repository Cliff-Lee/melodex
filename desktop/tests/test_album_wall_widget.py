from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_album_wall_widget_renders_switches_lenses_and_tracks_current(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QApplication

        from melodex.album_wall import AlbumWallWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    tracks = [
        {
            "provider_id": "local",
            "track_id": "/music/a1.mp3",
            "local_path": "/music/a1.mp3",
            "artist": "Artist A",
            "album": "Album A",
            "title": "Track A1",
        },
        {
            "provider_id": "local",
            "track_id": "/music/b1.mp3",
            "local_path": "/music/b1.mp3",
            "artist": "Artist B",
            "album": "Album B",
            "title": "Track B1",
        },
    ]
    model = {
        "album_count": 2,
        "analysed_albums": 1,
        "albums": [
            {
                "key": "a|album a",
                "artist": "Artist A",
                "title": "Album A",
                "year": 2001,
                "genres": ["Electronic"],
                "track_count": 1,
                "tracks": [tracks[0]],
                "representative_track": tracks[0],
                "analysed_tracks": 1,
                "sound_x": -0.5,
                "sound_y": 0.2,
                "fallback_x": -0.5,
                "fallback_y": 0.2,
                "familiarity": 0.8,
                "rediscovery": 0.1,
                "plays": 5,
                "time_x": -1.0,
                "time_y": 0.2,
                "familiarity_x": 0.6,
                "familiarity_y": 0.2,
                "cover_path": "",
            },
            {
                "key": "b|album b",
                "artist": "Artist B",
                "title": "Album B",
                "year": 2010,
                "genres": ["Ambient"],
                "track_count": 1,
                "tracks": [tracks[1]],
                "representative_track": tracks[1],
                "analysed_tracks": 0,
                "sound_x": 0.4,
                "sound_y": -0.3,
                "fallback_x": 0.4,
                "fallback_y": -0.3,
                "familiarity": 0.0,
                "rediscovery": 0.0,
                "plays": 0,
                "time_x": 1.0,
                "time_y": -0.3,
                "familiarity_x": -1.0,
                "familiarity_y": -0.3,
                "cover_path": "",
            },
        ],
    }

    widget = AlbumWallWidget()
    widget.resize(900, 620)
    requested = []
    widget.artworkRequested.connect(requested.append)
    widget.set_model(model, tracks[0])
    widget.show()
    app.processEvents()

    assert widget.current_key == "a|album a"
    assert widget.tiles["a|album a"]._current
    assert len(set((tile.pos().x(), tile.pos().y()) for tile in widget.tiles.values())) == 2

    for lens in ("familiarity", "time", "shelves", "sound"):
        idx = widget.lens.findData(lens)
        assert idx >= 0
        widget.lens.setCurrentIndex(idx)
        app.processEvents()

    cover = QImage(32, 32, QImage.Format_ARGB32)
    cover.fill(QColor("#8844aa"))
    path = tmp_path / "cover.png"
    assert cover.save(str(path))
    widget.set_artwork({"a|album a": str(path)})
    assert not widget.tiles["a|album a"]._pixmap.isNull()

    image = QImage(widget.size(), QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    widget.render(image)
    assert sum(
        image.pixelColor(x, y).alpha() > 0
        for x in range(0, image.width(), 8)
        for y in range(0, image.height(), 8)
    ) > 100

    widget.deleteLater()
    app.processEvents()


def test_album_wall_artwork_loading_does_not_recurse_without_navigation():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.album_wall import AlbumWallWidget
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    albums = []
    for i in range(80):
        track = {
            "provider_id": "local",
            "track_id": f"/music/{i}.mp3",
            "local_path": f"/music/{i}.mp3",
            "artist": f"Artist {i}",
            "album": f"Album {i}",
            "title": "Track",
        }
        albums.append({
            "key": f"k{i}",
            "artist": track["artist"],
            "title": track["album"],
            "year": 2000 + i % 20,
            "genres": [],
            "track_count": 1,
            "tracks": [track],
            "representative_track": track,
            "analysed_tracks": 0,
            "sound_x": 0.0,
            "sound_y": 0.0,
            "fallback_x": (i % 10) / 5 - 1,
            "fallback_y": (i // 10) / 4 - 1,
            "familiarity": 0.0,
            "rediscovery": 0.0,
            "plays": 0,
            "time_x": 0.0,
            "time_y": 0.0,
            "familiarity_x": -1.0,
            "familiarity_y": 0.0,
            "cover_path": "",
        })

    widget = AlbumWallWidget()
    batches = []
    widget.artworkRequested.connect(lambda rows: batches.append(list(rows)))
    widget.resize(900, 620)
    widget.set_model({"albums": albums, "album_count": len(albums), "analysed_albums": 0})
    widget.show()
    app.processEvents()
    widget._art_timer.stop()
    widget._request_visible_art()
    assert batches
    assert len(batches[-1]) <= 36

    before = len(batches)
    widget.set_artwork({})
    app.processEvents()
    assert len(batches) == before

    widget.deleteLater()
    app.processEvents()
