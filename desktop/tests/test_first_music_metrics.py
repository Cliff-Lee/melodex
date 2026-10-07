from __future__ import annotations

import pytest

from melodex.first_music_metrics import FirstMusicTimeline


def test_first_music_timeline_calculates_source_and_play_latencies() -> None:
    timeline = FirstMusicTimeline(started_at=10.0)
    source_id = timeline.begin_source(selection_started=True)
    timeline.mark("source_selected", source_id=source_id, now=11.0)
    timeline.mark("first_directory_result", source_id=source_id, now=11.2)
    timeline.mark("first_audio_file_discovered", source_id=source_id, now=11.5)
    timeline.mark("first_playable_track_ready", source_id=source_id, now=12.8)
    timeline.mark("first_track_visible", source_id=source_id, now=13.0)
    timeline.mark("background_scan_finished", source_id=source_id, now=13.5)

    play_id = timeline.begin_play(now=13.0)
    timeline.mark(
        "decoder_started", play_id=play_id,
        source_id=timeline.source_for_play(play_id), now=14.2,
    )
    timeline.mark(
        "first_audio_output", play_id=play_id,
        source_id=timeline.source_for_play(play_id), now=14.5,
    )

    summary = timeline.summary()
    source = summary["journeys"]["sources"][0]
    play = summary["journeys"]["plays"][0]
    assert source["source_selected_to_first_directory_ms"] == pytest.approx(200.0)
    assert source["source_selected_to_first_audio_file_ms"] == pytest.approx(500.0)
    assert source["source_selected_to_first_playable_track_ms"] == pytest.approx(1800.0)
    assert source["source_selected_to_first_track_visible_ms"] == pytest.approx(2000.0)
    assert source["source_selected_to_scan_finished_ms"] == pytest.approx(2500.0)
    assert source["source_selected_to_first_audio_output_ms"] == pytest.approx(3500.0)
    assert play["play_requested_to_decoder_ms"] == pytest.approx(1200.0)
    assert play["play_requested_to_audio_output_ms"] == pytest.approx(1500.0)
    assert summary["audio_output_measurement"].startswith("first playback-position advance")


def test_first_music_timeline_rejects_content_as_event_label() -> None:
    timeline = FirstMusicTimeline(started_at=1.0)
    with pytest.raises(ValueError):
        timeline.mark("/Users/listener/Music/private.flac")


def test_first_music_timeline_deduplicates_progress_events_per_attempt() -> None:
    timeline = FirstMusicTimeline(started_at=0.0)
    source_id = timeline.begin_source()
    timeline.mark("first_audio_file_discovered", source_id=source_id, now=1.0)
    timeline.mark("first_audio_file_discovered", source_id=source_id, now=2.0)
    rows = [
        row for row in timeline.summary()["events"]
        if row["event"] == "first_audio_file_discovered"
    ]
    assert len(rows) == 1
    assert rows[0]["elapsed_ms"] == pytest.approx(1000.0)


def test_first_music_timeline_keeps_startup_anchor_with_bounded_history() -> None:
    timeline = FirstMusicTimeline(started_at=0.0)
    for index in range(510):
        timeline.begin_play(now=float(index + 1))
    summary = timeline.summary()
    assert len(summary["events"]) == 500
    assert summary["events"][0]["event"] == "application_process_start"
    assert summary["journeys"]["plays"][-1]["play_id"] == 510
