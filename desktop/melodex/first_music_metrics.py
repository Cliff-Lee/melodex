from __future__ import annotations

import threading
import time
from typing import Any


_EVENTS = frozenset(
    {
        "application_process_start",
        "window_created",
        "shell_visible",
        "library_cache_visible",
        "source_selection_started",
        "source_selected",
        "source_probe_started",
        "source_probe_finished",
        "first_directory_result",
        "first_audio_file_discovered",
        "first_playable_track_ready",
        "first_track_visible",
        "first_queue_ready",
        "play_requested",
        "decoder_started",
        "first_audio_output",
        "background_scan_finished",
        "artwork_enrichment_finished",
    }
)
_SESSION_ANCHORS = frozenset(
    {"application_process_start", "window_created", "shell_visible", "library_cache_visible"}
)


class FirstMusicTimeline:
    """Content-free timing evidence for startup, source discovery and playback.

    Event labels and integer attempt IDs are the only recorded context. Paths,
    track metadata, URLs, provider configuration and exception text are never
    accepted by this recorder.
    """

    def __init__(self, *, started_at: float | None = None) -> None:
        self.started_at = time.perf_counter() if started_at is None else float(started_at)
        self._lock = threading.RLock()
        self._events: list[dict[str, Any]] = []
        self._source_sequence = 0
        self._play_sequence = 0
        self._active_source_id: int | None = None
        self._active_play_id: int | None = None
        self._play_sources: dict[int, int | None] = {}
        self.mark("application_process_start", now=self.started_at)

    @property
    def active_source_id(self) -> int | None:
        with self._lock:
            return self._active_source_id

    def begin_source(
        self, *, selection_started: bool = False, now: float | None = None
    ) -> int:
        with self._lock:
            self._source_sequence += 1
            source_id = self._source_sequence
            self._active_source_id = source_id
        if selection_started:
            self.mark("source_selection_started", source_id=source_id, now=now)
        return source_id

    def begin_play(self, *, now: float | None = None) -> int:
        with self._lock:
            self._play_sequence += 1
            play_id = self._play_sequence
            self._active_play_id = play_id
            source_id = self._active_source_id
            self._play_sources[play_id] = source_id
        self.mark("play_requested", play_id=play_id, source_id=source_id, now=now)
        return play_id

    def source_for_play(self, play_id: int) -> int | None:
        with self._lock:
            return self._play_sources.get(int(play_id))

    def mark(
        self,
        event: str,
        *,
        source_id: int | None = None,
        play_id: int | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        label = str(event or "").strip()
        if label not in _EVENTS:
            raise ValueError("Unknown first-music event")
        current = time.perf_counter() if now is None else float(now)
        row: dict[str, Any] = {
            "event": label,
            "elapsed_ms": round(max(0.0, (current - self.started_at) * 1000.0), 3),
        }
        if source_id is not None:
            row["source_id"] = max(0, int(source_id))
        if play_id is not None:
            row["play_id"] = max(0, int(play_id))
        with self._lock:
            # Repeated progress messages should produce one timestamp per
            # event and attempt, while separate attempts remain visible.
            if any(
                item.get("event") == label
                and item.get("source_id") == row.get("source_id")
                and item.get("play_id") == row.get("play_id")
                for item in self._events
            ):
                return dict(next(
                    item for item in self._events
                    if item.get("event") == label
                    and item.get("source_id") == row.get("source_id")
                    and item.get("play_id") == row.get("play_id")
                ))
            self._events.append(row)
            while len(self._events) > 500:
                discard_at = next(
                    index for index, item in enumerate(self._events)
                    if item["event"] not in _SESSION_ANCHORS
                )
                del self._events[discard_at]
                retained_play_ids = {
                    int(item["play_id"])
                    for item in self._events
                    if "play_id" in item
                }
                self._play_sources = {
                    key: value
                    for key, value in self._play_sources.items()
                    if key in retained_play_ids
                }
        return dict(row)

    @staticmethod
    def _elapsed(
        events: list[dict[str, Any]],
        start_event: str,
        end_event: str,
        *,
        identity_key: str | None = None,
        identity: int | None = None,
    ) -> float | None:
        selected = [
            row for row in events
            if identity_key is None or row.get(identity_key) == identity
        ]
        start = next((row for row in selected if row["event"] == start_event), None)
        end = next((row for row in selected if row["event"] == end_event), None)
        if start is None or end is None:
            return None
        return round(max(0.0, float(end["elapsed_ms"]) - float(start["elapsed_ms"])), 3)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            events = [dict(row) for row in self._events]
        sources = sorted(
            {int(row["source_id"]) for row in events if "source_id" in row}
        )
        plays = sorted(
            {int(row["play_id"]) for row in events if "play_id" in row}
        )
        journeys = {
            "process_to_shell_ms": self._elapsed(events, "application_process_start", "shell_visible"),
            "process_to_cached_library_ms": self._elapsed(events, "application_process_start", "library_cache_visible"),
            "plays": [
                {
                    "play_id": play_id,
                    "play_requested_to_decoder_ms": self._elapsed(
                        events, "play_requested", "decoder_started",
                        identity_key="play_id", identity=play_id,
                    ),
                    "play_requested_to_audio_output_ms": self._elapsed(
                        events, "play_requested", "first_audio_output",
                        identity_key="play_id", identity=play_id,
                    ),
                }
                for play_id in plays[-20:]
            ],
            "sources": [
                {
                    "source_id": source_id,
                    "source_selected_to_first_directory_ms": self._elapsed(
                        events, "source_selected", "first_directory_result",
                        identity_key="source_id", identity=source_id,
                    ),
                    "source_selected_to_first_audio_file_ms": self._elapsed(
                        events, "source_selected", "first_audio_file_discovered",
                        identity_key="source_id", identity=source_id,
                    ),
                    "source_selected_to_first_playable_track_ms": self._elapsed(
                        events, "source_selected", "first_playable_track_ready",
                        identity_key="source_id", identity=source_id,
                    ),
                    "source_selected_to_first_track_visible_ms": self._elapsed(
                        events, "source_selected", "first_track_visible",
                        identity_key="source_id", identity=source_id,
                    ),
                    "source_selected_to_first_queue_ready_ms": self._elapsed(
                        events, "source_selected", "first_queue_ready",
                        identity_key="source_id", identity=source_id,
                    ),
                    "source_selected_to_first_audio_output_ms": self._elapsed(
                        events, "source_selected", "first_audio_output",
                        identity_key="source_id", identity=source_id,
                    ),
                    "source_selected_to_scan_finished_ms": self._elapsed(
                        events, "source_selected", "background_scan_finished",
                        identity_key="source_id", identity=source_id,
                    ),
                }
                for source_id in sources[-20:]
            ],
        }
        return {
            "schema": 1,
            "audio_output_measurement": "first playback-position advance; not hardware loopback",
            "source_probe_measurement": "ends when the first provisional path is accepted; empty sources end with scan completion",
            "events": events,
            "journeys": journeys,
        }


__all__ = ["FirstMusicTimeline"]
