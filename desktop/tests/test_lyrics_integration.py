from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_now_playing_and_visuals_share_one_lyrics_document():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication

        from melodex.living_canvas import LivingCanvasView
        from melodex.lyrics_state import LyricsDocument
        from melodex.rich_now_playing import RichNowPlayingWidget
    except ImportError as exc:
        import pytest

        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    now = RichNowPlayingWidget(object())
    visual = LivingCanvasView()

    states = []
    legacy = []
    now.lyricsStateChanged.connect(states.append)
    now.lyricsChanged.connect(legacy.append)

    payload = {
        "text": "First line\nSecond line",
        "source": "LRCLIB",
        "synced": [
            {"time_ms": 0, "text": "First line"},
            {"time_ms": 1500, "text": "Second line"},
        ],
    }
    now._apply_lyrics(payload)

    assert states
    assert isinstance(states[-1], LyricsDocument)
    assert states[-1] is now.lyrics_document
    assert legacy[-1]["source"] == "LRCLIB"

    visual.set_track({"artist": "Example", "title": "Track", "duration": 4})
    visual.set_lyrics(states[-1])
    assert visual._lyrics is states[-1]

    now.set_position(2000)
    visual.set_position(2000, 4000)
    assert now._lyric_index == 1
    assert visual.scene._lyrics.index == 1
    assert visual.scene._lyrics.current == "Second line"

    now.deleteLater()
    visual.deleteLater()
    app.processEvents()


def test_reader_search_and_seekable_synced_lines_survive_state_consolidation():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication

        from melodex.rich_now_playing import RichNowPlayingWidget
    except ImportError as exc:
        import pytest

        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    now = RichNowPlayingWidget(object())
    sought = []
    now.lyricsSeekRequested.connect(sought.append)
    now._apply_lyrics({
        "source": "local",
        "synced": [
            {"time_ms": 0, "text": "Alpha line"},
            {"time_ms": 2500, "text": "Visible target words"},
        ],
    })

    now.lyrics_search.setText("target words")
    now._find_lyrics_text()
    assert "target words" in now.lyrics.textCursor().selectedText().casefold()

    from PySide6.QtCore import QUrl
    now._lyrics_anchor_clicked(QUrl("seek:2500"))
    assert sought == [2500]

    now.deleteLater()
    app.processEvents()
