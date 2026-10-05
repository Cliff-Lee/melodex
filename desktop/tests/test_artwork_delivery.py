from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication
    from melodex.album_wall import AlbumWallWidget
    from melodex.library_browser import LibraryBrowser
except ImportError as exc:  # pragma: no cover - runner capability guard
    pytest.skip(f"Qt desktop runtime is unavailable: {exc}", allow_module_level=True)


def _app():
    return QApplication.instance() or QApplication([])


def _track(index=1):
    return {
        "provider_id": "local",
        "track_id": f"/music/{index}.flac",
        "local_path": f"/music/{index}.flac",
        "artist": "Artist",
        "album": "Album",
        "title": f"Track {index}",
        "disc_number": 1,
        "track_number": index,
        "year": 2024,
    }


def _image(size):
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(QColor("#225588"))
    return image


def test_library_drops_stale_prepared_artwork_generation():
    app = _app()
    browser = LibraryBrowser()
    browser.resize(900, 700)
    browser.set_catalog([_track()])
    browser.show()
    app.processEvents()

    key = str(browser.albums[0]["key"])
    generation = browser._artwork_generation("albums")
    browser._art_requested.add(key)

    browser.set_artwork({
        key: {
            "path": "/cache/stale.png",
            "generation": generation - 1,
            "image": _image(160),
            "track_image": _image(58),
        }
    })

    assert key not in browser.artwork_paths
    assert key not in browser._art_requested
    assert browser.cards[key].has_real_cover is False

    browser.set_artwork({
        key: {
            "path": "/cache/current.png",
            "generation": generation,
            "image": _image(160),
            "track_image": _image(58),
        }
    })

    assert browser.artwork_paths[key] == "/cache/current.png"
    assert browser.cards[key].has_real_cover is True

    browser.close()
    browser.deleteLater()
    app.processEvents()


def test_album_wall_drops_stale_generation_and_never_decodes_structured_path():
    app = _app()
    track = _track()
    album = {
        "key": "artist|album",
        "artist": "Artist",
        "title": "Album",
        "year": 2024,
        "genres": [],
        "track_count": 1,
        "tracks": [track],
        "representative_track": track,
        "analysed_tracks": 0,
        "sound_x": 0.0,
        "sound_y": 0.0,
        "fallback_x": 0.0,
        "fallback_y": 0.0,
        "familiarity": 0.0,
        "rediscovery": 0.0,
        "plays": 0,
        "time_x": 0.0,
        "time_y": 0.0,
        "familiarity_x": 0.0,
        "familiarity_y": 0.0,
        "cover_path": "",
    }
    model = {"albums": [album], "album_count": 1, "analysed_albums": 0}

    wall = AlbumWallWidget()
    wall.resize(700, 520)
    wall.set_model(model)
    wall.set_model(model)
    wall.show()
    app.processEvents()

    generation = wall._art_generation
    tile = wall.tiles["artist|album"]
    wall._art_requested.add("artist|album")

    wall.set_artwork({
        "artist|album": {
            "path": "/cache/stale.png",
            "generation": generation - 1,
            "image": _image(228),
        }
    })
    assert tile._pixmap.isNull()
    assert "artist|album" not in wall._art_requested

    def forbidden_path_decode(_path):
        raise AssertionError("structured artwork must not decode a path on the UI thread")

    tile.set_cover_path = forbidden_path_decode
    wall.set_artwork({
        "artist|album": {
            "path": "/cache/current.png",
            "generation": generation,
            "image": _image(228),
        }
    })

    assert not tile._pixmap.isNull()
    assert tile._pixmap.width() == tile._pixmap.height() == 228
    assert tile._cover_prepares == 1

    wall.close()
    wall.deleteLater()
    app.processEvents()
