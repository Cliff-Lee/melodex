from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from melodex.lyrics_state import (
    LyricsDocument,
    build_lyrics_document,
    lyric_frame,
    lyrics_have_content,
)


def test_synced_document_is_normalized_once_and_shared_frame_is_stable():
    doc = build_lyrics_document({
        "source": "LRCLIB",
        "text": "First\nSecond",
        "synced": [
            {"time_ms": 2000, "text": " Second  line "},
            {"time_ms": 0, "text": "First   line"},
        ],
        "match": {"method": "structured_search"},
    })
    assert isinstance(doc, LyricsDocument)
    assert [line.time_ms for line in doc.lines] == [0, 2000]
    assert [line.text for line in doc.lines] == ["First line", "Second line"]
    assert doc.frame(2500, 5000).current == "Second line"
    assert doc.frame(2500, 5000).index == 1
    assert lyric_frame(doc, 2500, 5000) == doc.frame(2500, 5000)
    assert build_lyrics_document(doc) is doc


def test_untimed_lyrics_never_guess_a_current_line():
    text = "one\ntwo\nthree\nfour"
    doc = build_lyrics_document({"text": text, "source": "local"})
    start = doc.frame(0, 4000)
    middle = doc.frame(2100, 4000)
    end = doc.frame(4000, 4000)

    for frame in (start, middle, end):
        assert frame.current == ""
        assert frame.previous == ""
        assert frame.following == ""
        assert frame.full_text == text
        assert frame.synced is False


def test_instrumental_counts_as_content_without_fake_text():
    doc = build_lyrics_document({"instrumental": True, "source": "local"})
    assert doc.has_content
    assert lyrics_have_content(doc)
    assert doc.searchable_text == ""
    assert doc.frame(1000, 5000).current == ""


def test_document_payload_round_trip_preserves_reader_metadata():
    source = {
        "text": "hello",
        "source": "Edited lyrics",
        "status": "ok",
        "cache": "memory",
        "user_added": True,
        "path": "/tmp/example.lrc",
        "provenance": {"source_url": "https://example.test"},
        "match": {"method": "exact"},
    }
    doc = build_lyrics_document(source)
    payload = doc.as_payload()
    assert payload["text"] == "hello"
    assert payload["source"] == "Edited lyrics"
    assert payload["user_added"] is True
    assert payload["path"] == "/tmp/example.lrc"
    assert payload["provenance"]["source_url"] == "https://example.test"
    assert payload["match"]["method"] == "exact"


def test_empty_and_malformed_inputs_fail_softly():
    assert build_lyrics_document(None) == LyricsDocument.empty()
    assert not lyrics_have_content({})
    malformed = build_lyrics_document({"synced": [{"time_ms": "bad", "text": None}]})
    assert malformed.lines[0].time_ms == 0
    assert malformed.lines[0].text == ""
