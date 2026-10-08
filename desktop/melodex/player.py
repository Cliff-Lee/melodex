from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from .album_track_order import album_order_diagnostics
from .playback_gateway import PlaybackGateway


PLAYBACK_INTENTS = frozenset({"album", "playlist", "journey", "manual_queue", "provider"})


def _normalise_playback_intent(value: object) -> str:
    intent = str(value or "").strip().casefold()
    return intent if intent in PLAYBACK_INTENTS else "manual_queue"


def _expired(value: Any, skew_seconds: int = 15) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.timestamp() <= datetime.now(timezone.utc).timestamp() + skew_seconds
    except ValueError:
        return False


def _qt_error_name(value: object) -> str:
    known = (
        "NoError",
        "ResourceError",
        "FormatError",
        "NetworkError",
        "AccessDeniedError",
        "ServiceMissingError",
    )
    name = getattr(value, "name", None)
    if name:
        return str(name).rsplit(".", 1)[-1]
    for candidate in known:
        scope = getattr(QMediaPlayer, "Error", QMediaPlayer)
        expected = getattr(scope, candidate, None)
        if expected is None:
            expected = getattr(QMediaPlayer, candidate, None)
        if expected is not None and value == expected:
            return candidate
    return str(value or "").rsplit(".", 1)[-1]


class FlowPlayer(QObject):
    trackChanged = Signal(dict)
    positionChanged = Signal(int, int)
    playingChanged = Signal(bool)
    queueChanged = Signal(list)
    audioProcessingChanged = Signal(dict)
    manualAdvanced = Signal(dict, dict, int, int)
    error = Signal(str)
    playbackNotice = Signal(str, int)
    _transitionPlanReady = Signal(int, int, object)
    _playbackRecoveryReady = Signal(int, int, int, int, object)

    def __init__(
        self,
        resolver,
        transition_for=None,
        parent=None,
        playback_refresher=None,
        transition_submit=None,
        first_music_timeline=None,
        playback_refresh_scheduler=None,
        playback_refresh_submit=None,
    ):
        super().__init__(parent)
        self.resolver = resolver
        self.playback_refresher = playback_refresher
        self.transition_for = transition_for
        self._transition_submit = transition_submit
        self._playback_refresh_scheduler = playback_refresh_scheduler
        self._playback_refresh_submit = playback_refresh_submit or getattr(
            playback_refresh_scheduler, "submit", None
        )
        self._playback_refresh_cancel = getattr(
            playback_refresh_scheduler, "cancel_pending", None
        )
        self._first_music_timeline = first_music_timeline
        self._playback_recovery_generation = 0
        self._playback_recovery_attempts = 0
        self._local_reconnect_attempts = 0
        self._local_reconnect_max_attempts = 3
        self._local_reconnect_delays_ms = (1000, 3500, 9000)
        self._playback_recovery_pending = False
        self._playback_recovery_request: dict[str, Any] | None = None
        self._playback_recovery_candidate: dict[str, Any] | None = None
        self._playback_recovery_position_ms = 0
        self._playback_recovery_exhausted_reported = False
        self._playback_recovery_max_attempts = 2
        self._playback_recovery_delays_ms = (350, 1200)
        self._first_music_play_by_deck: dict[int, int] = {}
        self._first_music_position_base: dict[int, int] = {}
        self._first_music_output_recorded: set[int] = set()
        self.gateway = PlaybackGateway()
        self.players = [QMediaPlayer(self), QMediaPlayer(self)]
        self.outputs = [QAudioOutput(self), QAudioOutput(self)]
        for player, output in zip(self.players, self.outputs):
            player.setAudioOutput(output)
            output.setVolume(1.0)
        self.active = 0
        self.queue: list[dict[str, Any]] = []
        self.index = -1
        self._crossfading = False
        self._transition_ms = 0
        self._crossfade_target_index: int | None = None
        self._crossfade_deck: int | None = None
        self._buffer_progress_by_deck = {0: 1.0, 1: 1.0}
        self._buffer_stall_started_at: float | None = None
        self._buffer_stall_deck: int | None = None
        self._buffer_stall_causes: set[str] = set()
        self._buffer_stall_notice_shown = False
        self._last_progress_position_ms = 0
        self._last_progress_at = time.monotonic()
        self._position_stall_monitor_active = False
        self._position_stall_threshold_ms = 1800
        self._local_reconnect_resume = True
        self._volume = 1.0
        self._playback_intent = "manual_queue"
        self._playback_should_play = False
        self._transition_plan_generation = 0
        self._planned_transition_target = -1
        self._planned_transition_ms = 4500
        # P14 runtime counters are deliberately metadata-free. They exist so a
        # beta tester can export evidence of playback/transport divergence
        # without exposing track names, paths, URLs or provider credentials.
        self._runtime_metrics = {
            "ticks": 0,
            "track_commits": 0,
            "seek_requests": 0,
            "manual_next": 0,
            "manual_previous": 0,
            "crossfade_started": 0,
            "crossfade_completed": 0,
            "crossfade_eof_commits": 0,
            "natural_ends": 0,
            "transition_aborts": 0,
            "queue_position_commits": 0,
            "transition_plan_requests": 0,
            "transition_plan_completed": 0,
            "transition_plan_stale": 0,
            "transition_plan_failures": 0,
            "transition_plan_submit_rejected": 0,
            "playback_errors": 0,
            "active_deck_errors": 0,
            "incoming_deck_errors": 0,
            "inactive_deck_errors_ignored": 0,
            "transient_source_errors": 0,
            "permanent_source_errors": 0,
            "unclassified_source_errors": 0,
            "recovery_attempts": 0,
            "recovery_successes": 0,
            "recovery_refresh_failures": 0,
            "recovery_source_rejections": 0,
            "recovery_submit_rejected": 0,
            "recovery_exhausted": 0,
            "recovery_stale_results": 0,
            "recovery_skipped_paused": 0,
            "recovery_unavailable": 0,
            "local_resource_errors": 0,
            "local_reconnect_attempts": 0,
            "local_reconnect_probe_failures": 0,
            "local_reconnect_unavailable": 0,
            "local_reconnect_successes": 0,
            "local_reconnect_exhausted": 0,
            "buffer_stall_events": 0,
            "buffer_stall_status_events": 0,
            "buffer_stall_no_progress_events": 0,
            "buffer_stall_notices": 0,
            "buffer_progress_events": 0,
            "buffer_stall_ms_total": 0,
            "buffer_stall_ms_max": 0,
            "buffer_progress_min_permille": 1000,
        }
        self._last_seek_requested_ms = 0
        self._transitionPlanReady.connect(self._apply_transition_plan)
        self._playbackRecoveryReady.connect(self._apply_playback_recovery)
        self._playback_recovery_timer = QTimer(self)
        self._playback_recovery_timer.setSingleShot(True)
        self._playback_recovery_timer.timeout.connect(
            self._start_playback_recovery
        )
        self._buffer_notice_timer = QTimer(self)
        self._buffer_notice_timer.setSingleShot(True)
        self._buffer_notice_timer.timeout.connect(self._show_buffering_notice)
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        for deck, player in enumerate(self.players):
            player.errorOccurred.connect(
                lambda error, msg, deck=deck: self._on_player_error(deck, error, msg)
            )
            player.mediaStatusChanged.connect(
                lambda status, deck=deck: self._on_media_status(deck, status)
            )
            progress_signal = getattr(player, "bufferProgressChanged", None)
            if progress_signal is not None:
                progress_signal.connect(
                    lambda progress, deck=deck: self._on_buffer_progress(
                        deck, progress
                    )
                )

    def set_queue(
        self,
        tracks: list[dict[str, Any]],
        start: int = 0,
        autoplay: bool = True,
        *,
        intent: str = "manual_queue",
    ) -> None:
        self._invalidate_playback_recovery(reset_attempts=True)
        self._cancel_transition(stop_incoming=True, count_abort=True)
        self._stop_all_decks()
        self._playback_intent = _normalise_playback_intent(intent)
        self._playback_should_play = bool(autoplay and tracks)
        self._invalidate_transition_plan()
        self.queue = [dict(item) for item in tracks]
        self.index = max(0, min(len(self.queue) - 1, start)) if self.queue else -1
        self.queueChanged.emit(self.queue)
        if self.queue and self._first_music_timeline is not None:
            source_id = self._first_music_timeline.active_source_id
            if source_id is not None:
                self._first_music_timeline.mark(
                    "first_queue_ready", source_id=source_id
                )
        if autoplay and self.index >= 0:
            self._load_index(self.index, play=True)
        else:
            self._schedule_transition_plan()
            self.playingChanged.emit(False)

    def append_queue(
        self,
        tracks: list[dict[str, Any]],
        autoplay: bool = False,
        *,
        intent: str | None = None,
    ) -> None:
        incoming = [dict(item) for item in tracks]
        if not incoming:
            return
        if not self.queue:
            self.set_queue(
                incoming,
                0,
                autoplay,
                intent=_normalise_playback_intent(intent),
            )
            return
        self.queue.extend(incoming)
        self.queueChanged.emit(self.queue)
        self._schedule_transition_plan()

    def queue_snapshot(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.queue]

    def jump_to(self, index: int, autoplay: bool = True) -> bool:
        index = int(index)
        if not (0 <= index < len(self.queue)):
            return False
        self._invalidate_playback_recovery(reset_attempts=True)
        self._cancel_transition(stop_incoming=True, count_abort=True)
        self._stop_all_decks()
        return self._load_index(
            index,
            bool(autoplay),
            announce_queue=True,
        )

    def replace_queue_item(
        self,
        index: int,
        track: dict[str, Any],
        *,
        autoplay: bool = False,
    ) -> bool:
        index = int(index)
        if not (0 <= index < len(self.queue)):
            return False
        position_changed = index != self.index
        if index == self.index:
            self._invalidate_playback_recovery(reset_attempts=True)
        self.queue[index] = dict(track)
        self.queueChanged.emit(self.queue)
        if autoplay:
            self._cancel_transition(stop_incoming=True, count_abort=True)
            self._stop_all_decks()
            return self._load_index(
                index,
                True,
                announce_queue=position_changed,
            )
        if index == self.index:
            self.trackChanged.emit(dict(self.queue[index]))
        if index in {self.index, self.index + 1}:
            self._schedule_transition_plan()
        return True

    def remove_queue_item(self, index: int) -> bool:
        """Remove an upcoming track without restarting the active track."""
        index = int(index)
        minimum = max(0, self.index + 1)
        if not (minimum <= index < len(self.queue)):
            return False
        if self._crossfading and index == self.index + 1:
            self._cancel_transition(stop_incoming=True, count_abort=True)
        del self.queue[index]
        self.queueChanged.emit(self.queue)
        self._schedule_transition_plan()
        return True

    def move_queue_item(self, source: int, target: int) -> bool:
        """Move an upcoming track while leaving playback position untouched."""
        source, target = int(source), int(target)
        minimum = max(0, self.index + 1)
        if not (
            minimum <= source < len(self.queue)
            and minimum <= target < len(self.queue)
        ):
            return False
        if source == target:
            return False
        if self._crossfading:
            self._cancel_transition(stop_incoming=True, count_abort=True)
        track = self.queue.pop(source)
        self.queue.insert(target, track)
        self.queueChanged.emit(self.queue)
        self._schedule_transition_plan()
        return True

    def merge_queue_items(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        changes: dict[str, Any],
    ) -> int:
        updated = 0
        transition_pair_changed = False
        for index, item in enumerate(list(self.queue)):
            row = dict(item)
            if not predicate(row):
                continue
            self.queue[index] = {**row, **dict(changes)}
            updated += 1
            transition_pair_changed = transition_pair_changed or index in {
                self.index,
                self.index + 1,
            }
        if updated:
            self.queueChanged.emit(self.queue)
        if transition_pair_changed:
            self._schedule_transition_plan()
        return updated

    def clear_queue(self) -> None:
        self._invalidate_playback_recovery(reset_attempts=True)
        self._cancel_transition(stop_incoming=True, count_abort=True)
        self._stop_all_decks()
        self.queue = []
        self.index = -1
        self._playback_intent = "manual_queue"
        self._playback_should_play = False
        self._invalidate_transition_plan()
        self.queueChanged.emit(self.queue)
        self.playingChanged.emit(False)
        self._emit_audio_processing_state()

    def stop(self) -> None:
        self._playback_should_play = False
        self._invalidate_playback_recovery(reset_attempts=True)
        self._cancel_transition(stop_incoming=True, count_abort=True)
        self._stop_all_decks()
        self.playingChanged.emit(False)

    def close(self) -> None:
        self._invalidate_transition_plan()
        self.stop()
        self.gateway.close()

    def current_track(self) -> dict[str, Any] | None:
        return dict(self.queue[self.index]) if 0 <= self.index < len(self.queue) else None

    def status(self) -> dict[str, Any]:
        player = self.players[self.active]
        return {
            "playing": player.playbackState() == QMediaPlayer.PlayingState,
            "position_ms": int(player.position()),
            "duration_ms": int(player.duration()),
            "volume": float(self.outputs[self.active].volume()),
            "index": int(self.index),
            "current_track": self.current_track(),
            "queue": [dict(item) for item in self.queue],
            "intent": self._playback_intent,
        }

    def diagnostics_snapshot(self) -> dict[str, Any]:
        """Return playback runtime metrics without collection/user content."""
        player = self.players[self.active]
        queue_length = len(self.queue)
        index_valid = (
            (queue_length == 0 and self.index == -1)
            or (queue_length > 0 and 0 <= self.index < queue_length)
        )
        transition_target = self._crossfade_target_index
        transition_deck = self._crossfade_deck
        transition_valid = (
            not self._crossfading
            or (
                transition_target == self.index + 1
                and transition_target is not None
                and 0 <= transition_target < queue_length
                and transition_deck is not None
                and 0 <= transition_deck < len(self.players)
                and transition_deck != self.active
            )
        )
        playing = player.playbackState() == QMediaPlayer.PlayingState
        if self._crossfading and transition_deck is not None:
            playing = playing or (
                self.players[transition_deck].playbackState()
                == QMediaPlayer.PlayingState
            )
        snapshot = {
            **dict(self._runtime_metrics),
            "queue_length": int(queue_length),
            "queue_index": int(self.index),
            "queue_index_valid": bool(index_valid),
            "active_deck": int(self.active),
            "crossfading": bool(self._crossfading),
            "transition_ms": int(self._transition_ms),
            "transition_target_index": transition_target,
            "transition_deck": transition_deck,
            "transition_state_valid": bool(transition_valid),
            "playback_intent": self._playback_intent,
            "journey_transitions_enabled": self._playback_intent == "journey",
            "planned_transition_target": int(self._planned_transition_target),
            "planned_transition_ms": int(self._planned_transition_ms),
            "playing": bool(playing),
            "position_ms": int(player.position()),
            "duration_ms": int(player.duration()),
            "seekable": bool(player.isSeekable()),
            "last_seek_requested_ms": int(self._last_seek_requested_ms),
            "buffer_progress_permille": int(
                round(self._buffer_progress_by_deck.get(self.active, 1.0) * 1000)
            ),
            "buffer_stall_active": bool(
                self._buffer_stall_started_at is not None
            ),
            "buffer_stall_age_ms": int(
                max(0.0, time.monotonic() - self._buffer_stall_started_at) * 1000
            ) if self._buffer_stall_started_at is not None else 0,
            "active_buffer_progress_permille": int(
                round(self._buffer_progress_by_deck.get(self.active, 1.0) * 1000)
            ),
        }
        for name, value in self.gateway.diagnostics_snapshot().items():
            snapshot[f"gateway_{name}"] = int(value)
        if self._playback_intent == "album":
            snapshot["album_order"] = album_order_diagnostics(self.queue)
        return snapshot

    def _invalidate_playback_recovery(self, *, reset_attempts: bool) -> None:
        self._playback_recovery_generation += 1
        self._playback_recovery_timer.stop()
        self._buffer_notice_timer.stop()
        self._end_buffer_stall()
        self._position_stall_monitor_active = False
        if self._playback_refresh_cancel is not None:
            try:
                self._playback_refresh_cancel("playback-recovery")
            except Exception:
                pass
        candidate = self._playback_recovery_candidate
        self._playback_recovery_pending = False
        self._playback_recovery_request = None
        self._playback_recovery_candidate = None
        if reset_attempts:
            self._playback_recovery_attempts = 0
            self._local_reconnect_attempts = 0
            self._playback_recovery_position_ms = 0
            self._playback_recovery_exhausted_reported = False
            self._local_reconnect_resume = True
        if candidate is not None:
            deck = int(candidate.get("deck", -1))
            if 0 <= deck < len(self.players):
                self.players[deck].stop()
                self.players[deck].setSource(QUrl())
    def _recovery_request_is_current(
        self,
        generation: int,
        index: int,
        deck: int,
        attempt: int,
    ) -> bool:
        request = self._playback_recovery_request
        return bool(
            self._playback_recovery_pending
            and request is not None
            and int(generation) == self._playback_recovery_generation
            and int(index) == self.index
            and int(deck) == self.active
            and 0 <= int(index) < len(self.queue)
            and int(request.get("generation", -1)) == int(generation)
            and int(request.get("index", -1)) == int(index)
            and int(request.get("deck", -1)) == int(deck)
            and int(request.get("attempt", -1)) == int(attempt)
        )

    def _queue_playback_recovery(
        self,
        generation: int,
        index: int,
        deck: int,
        *,
        mode: str = "remote",
        resume_after_recovery: bool | None = None,
    ) -> None:
        if self._playback_recovery_pending:
            return
        if not (0 <= index < len(self.queue)):
            return
        mode = "local" if mode == "local" else "remote"
        attempts = (
            self._local_reconnect_attempts
            if mode == "local"
            else self._playback_recovery_attempts
        )
        max_attempts = (
            self._local_reconnect_max_attempts
            if mode == "local"
            else self._playback_recovery_max_attempts
        )
        delays = (
            self._local_reconnect_delays_ms
            if mode == "local"
            else self._playback_recovery_delays_ms
        )
        if attempts >= max_attempts:
            self._finish_playback_recovery(mode=mode)
            return
        attempt = attempts + 1
        if mode == "local":
            self._local_reconnect_attempts = attempt
        else:
            self._playback_recovery_attempts = attempt
        self._playback_recovery_pending = True
        self._playback_recovery_candidate = None
        track = dict(self.queue[index])
        self._playback_recovery_request = {
            "generation": int(generation),
            "index": int(index),
            "deck": int(deck),
            "attempt": int(attempt),
            "mode": mode,
            "track": track,
            "position_ms": int(self._playback_recovery_position_ms),
            "resume_after_recovery": (
                self._local_reconnect_resume
                if resume_after_recovery is None
                else bool(resume_after_recovery)
            ),
        }
        delay = delays[min(attempt - 1, len(delays) - 1)]
        self._playback_recovery_timer.start(max(0, int(delay)))

    def _start_playback_recovery(self) -> None:
        request = self._playback_recovery_request
        if request is None:
            return
        generation = int(request["generation"])
        index = int(request["index"])
        deck = int(request["deck"])
        attempt = int(request["attempt"])
        mode = str(request.get("mode") or "remote")
        if not self._recovery_request_is_current(
            generation, index, deck, attempt
        ):
            self._runtime_metrics["recovery_stale_results"] += 1
            return
        if self._playback_refresh_submit is None:
            self._playback_recovery_pending = False
            self._playback_recovery_request = None
            self._runtime_metrics["recovery_unavailable"] += 1
            if mode == "local":
                self._runtime_metrics["local_reconnect_unavailable"] += 1
                self._finish_playback_recovery(mode="local")
            else:
                self._finish_playback_recovery(mode="remote")
            return

        track = dict(request["track"])
        if mode == "local":
            local_path = str(track.get("local_path") or "")

            def probe() -> None:
                try:
                    available = bool(local_path) and Path(local_path).is_file()
                except (OSError, ValueError):
                    available = False
                self._playbackRecoveryReady.emit(
                    generation,
                    index,
                    deck,
                    attempt,
                    {"ok": bool(available)},
                )

            job_name = "playback-reconnect-probe"
        else:
            if self.playback_refresher is None:
                self._playback_recovery_pending = False
                self._playback_recovery_request = None
                self._runtime_metrics["recovery_unavailable"] += 1
                self._finish_playback_recovery(mode="remote")
                return

            def probe() -> None:
                try:
                    refreshed = dict(self.playback_refresher(dict(track)))
                    payload = {"ok": True, "track": refreshed}
                except Exception:
                    payload = {"ok": False}
                self._playbackRecoveryReady.emit(
                    generation, index, deck, attempt, payload
                )

            job_name = "playback-refresh"

        try:
            accepted = bool(
                self._playback_refresh_submit(
                    probe,
                    priority="foreground",
                    name=job_name,
                    replace_key="playback-recovery",
                )
            )
        except Exception:
            accepted = False
        if not accepted:
            if mode == "local":
                self._runtime_metrics["local_reconnect_probe_failures"] += 1
            else:
                self._runtime_metrics["recovery_submit_rejected"] += 1
            self._playback_recovery_pending = False
            self._playback_recovery_request = None
            self._retry_or_finish_playback_recovery(
                generation, index, deck, mode=mode
            )
            return
        if mode == "local":
            self._runtime_metrics["local_reconnect_attempts"] += 1
        else:
            self._runtime_metrics["recovery_attempts"] += 1

    def _apply_playback_recovery(
        self,
        generation: int,
        index: int,
        deck: int,
        attempt: int,
        payload: object,
    ) -> None:
        if not self._recovery_request_is_current(
            generation, index, deck, attempt
        ):
            self._runtime_metrics["recovery_stale_results"] += 1
            return
        request = self._playback_recovery_request or {}
        mode = str(request.get("mode") or "remote")
        self._playback_recovery_pending = False
        self._playback_recovery_request = None
        result = dict(payload or {}) if isinstance(payload, dict) else {}
        if mode == "local":
            if not result.get("ok"):
                self._runtime_metrics["local_reconnect_probe_failures"] += 1
                self._retry_or_finish_playback_recovery(
                    generation, index, deck, mode="local"
                )
                return
            track = dict(request.get("track") or {})
            local_path = str(track.get("local_path") or "")
            if not local_path:
                self._runtime_metrics["local_reconnect_probe_failures"] += 1
                self._retry_or_finish_playback_recovery(
                    generation, index, deck, mode="local"
                )
                return
            candidate_url = QUrl.fromLocalFile(local_path)
            self._playback_recovery_candidate = {
                "generation": int(generation),
                "index": int(index),
                "deck": int(deck),
                "attempt": int(attempt),
                "mode": "local",
                "track": track,
                "url": candidate_url,
                "position_ms": int(request.get("position_ms", 0)),
                "resume_after_recovery": bool(
                    request.get("resume_after_recovery", True)
                ),
            }
            try:
                self._set_local_recovery_source(deck, candidate_url)
            except Exception:
                self._playback_recovery_candidate = None
                self._runtime_metrics["local_reconnect_probe_failures"] += 1
                self._retry_or_finish_playback_recovery(
                    generation, index, deck, mode="local"
                )
            return

        if not result.get("ok"):
            self._runtime_metrics["recovery_refresh_failures"] += 1
            self._retry_or_finish_playback_recovery(
                generation, index, deck, mode="remote"
            )
            return

        refreshed = result.get("track")
        try:
            track = dict(refreshed) if isinstance(refreshed, dict) else {}
            url = self._media_url_for(track)
            if url.isEmpty():
                raise RuntimeError("Recovery source is empty")
        except Exception:
            self._runtime_metrics["recovery_source_rejections"] += 1
            self._retry_or_finish_playback_recovery(
                generation, index, deck, mode="remote"
            )
            return

        self._playback_recovery_candidate = {
            "generation": int(generation),
            "index": int(index),
            "deck": int(deck),
            "attempt": int(attempt),
            "mode": "remote",
            "track": track,
            "url": url,
            "position_ms": int(self._playback_recovery_position_ms),
            "resume_after_recovery": True,
        }
        try:
            self.players[deck].setSource(url)
        except Exception:
            self._playback_recovery_candidate = None
            self._runtime_metrics["recovery_source_rejections"] += 1
            self._retry_or_finish_playback_recovery(
                generation, index, deck, mode="remote"
            )

    def _retry_or_finish_playback_recovery(
        self,
        generation: int,
        index: int,
        deck: int,
        *,
        mode: str = "remote",
    ) -> None:
        if generation != self._playback_recovery_generation:
            self._runtime_metrics["recovery_stale_results"] += 1
            return
        attempts = (
            self._local_reconnect_attempts
            if mode == "local"
            else self._playback_recovery_attempts
        )
        max_attempts = (
            self._local_reconnect_max_attempts
            if mode == "local"
            else self._playback_recovery_max_attempts
        )
        if attempts < max_attempts:
            self._queue_playback_recovery(
                generation, index, deck, mode=mode
            )
        else:
            self._finish_playback_recovery(mode=mode)

    def _finish_playback_recovery(self, *, mode: str = "remote") -> None:
        self._playback_recovery_timer.stop()
        self._playback_recovery_pending = False
        self._playback_recovery_request = None
        candidate = self._playback_recovery_candidate
        self._playback_recovery_candidate = None
        if candidate is not None:
            deck = int(candidate.get("deck", -1))
            if 0 <= deck < len(self.players):
                self.players[deck].stop()
                self.players[deck].setSource(QUrl())
        if mode == "local":
            if not self._playback_recovery_exhausted_reported:
                self._playback_recovery_exhausted_reported = True
                self._runtime_metrics["local_reconnect_exhausted"] += 1
                self.error.emit(
                    "Storage is still unavailable. The track remains in your queue."
                )
            return
        if not self._playback_recovery_exhausted_reported:
            self._playback_recovery_exhausted_reported = True
            self._runtime_metrics["recovery_exhausted"] += 1
            self.error.emit(
                "Playback could not be resumed. The track remains in your queue."
            )

    def _set_local_recovery_source(self, deck: int, url: QUrl) -> None:
        self.players[deck].setSource(url)

    def _complete_playback_recovery(self, deck: int) -> None:
        candidate = self._playback_recovery_candidate
        if candidate is None:
            return
        if (
            int(candidate["generation"]) != self._playback_recovery_generation
            or int(candidate["index"]) != self.index
            or int(candidate["deck"]) != int(deck)
            or int(deck) != self.active
            or (
                candidate.get("mode") != "local"
                and self.players[int(deck)].source() != candidate.get("url")
            )
        ):
            self._runtime_metrics["recovery_stale_results"] += 1
            self._playback_recovery_candidate = None
            return
        mode = str(candidate.get("mode") or "remote")
        index = int(candidate["index"])
        player = self.players[deck]
        position = max(0, int(candidate.get("position_ms", 0)))
        self._playback_recovery_candidate = None
        if position:
            player.setPosition(position)
        self._playback_recovery_position_ms = position
        if mode == "local":
            if bool(candidate.get("resume_after_recovery", True)):
                player.play()
                self.playingChanged.emit(True)
                self.playbackNotice.emit(
                    "Storage is available. Playback resumed.", 4000
                )
            else:
                self.playingChanged.emit(False)
                self.playbackNotice.emit("Storage is available.", 4000)
            self._runtime_metrics["local_reconnect_successes"] += 1
            return

        track = dict(candidate["track"])
        self.queue[index] = track
        self._runtime_metrics["recovery_successes"] += 1
        self.queueChanged.emit(self.queue)
        player.play()
        self.playingChanged.emit(True)
        self.error.emit("Playback resumed after a temporary source interruption.")

    def _resolve_for_playback(self, index: int) -> dict[str, Any]:
        resolved = dict(self.resolver(dict(self.queue[index])))
        if _expired(resolved.get("expires_at")) and self.playback_refresher:
            resolved = dict(self.playback_refresher(resolved))
        self.queue[index] = resolved
        return resolved

    def _media_url_for(self, resolved: dict[str, Any]) -> QUrl:
        local = str(resolved.get("local_path") or "")
        if local:
            return QUrl.fromLocalFile(str(Path(local)))
        url = str(resolved.get("stream_url") or resolved.get("url") or "")
        if not url:
            raise RuntimeError("This source did not provide a playable stream")
        guarded_external = "_playback_allowed_hosts" in resolved
        kind = str(resolved.get("kind") or "http").casefold()
        needs_gateway = bool(
            resolved.get("headers")
            or resolved.get("cookies")
            or resolved.get("gateway_required")
            or (guarded_external and kind != "hls")
        )
        if needs_gateway:
            url = self.gateway.register(resolved)
        elif guarded_external:
            self.gateway.validate_resource(resolved)
        return QUrl(url)

    def audio_processing_snapshot(self) -> dict[str, Any]:
        """Describe effective audio behavior without exposing track metadata."""
        if self._playback_intent == "journey" and self.index + 1 < len(self.queue):
            if self._crossfading:
                transition_state = "active"
                transition_ms = max(0, int(self._transition_ms))
            else:
                transition_state = "planned"
                transition_ms = (
                    int(self._planned_transition_ms)
                    if self._planned_transition_target == self.index + 1
                    else 4500
                )
        else:
            transition_state = "off"
            transition_ms = 0
        return {
            "intent": self._playback_intent,
            "transition_state": transition_state,
            "transition_ms": transition_ms,
            "normalization": "off",
        }

    def _emit_audio_processing_state(self) -> None:
        snapshot = self.audio_processing_snapshot()
        signature = tuple(sorted(snapshot.items()))
        if signature == getattr(self, "_last_audio_processing_signature", None):
            return
        self._last_audio_processing_signature = signature
        self.audioProcessingChanged.emit(snapshot)

    def _clear_transition_state(self) -> None:
        self._crossfading = False
        self._transition_ms = 0
        self._crossfade_target_index = None
        self._crossfade_deck = None

    def _cancel_transition(
        self,
        *,
        stop_incoming: bool = True,
        count_abort: bool = True,
    ) -> None:
        if not self._crossfading:
            self._clear_transition_state()
            self._emit_audio_processing_state()
            return
        incoming = (
            self._crossfade_deck
            if self._crossfade_deck is not None
            else 1 - self.active
        )
        if stop_incoming and 0 <= incoming < len(self.players):
            self.players[incoming].stop()
        if 0 <= incoming < len(self.outputs):
            self.outputs[incoming].setVolume(0.0)
        self.outputs[self.active].setVolume(self._volume)
        if count_abort:
            self._runtime_metrics["transition_aborts"] += 1
        self._clear_transition_state()
        self._emit_audio_processing_state()

    def _stop_all_decks(self) -> None:
        for deck, player in enumerate(self.players):
            player.stop()
            if deck != self.active:
                self.outputs[deck].setVolume(0.0)

    def _commit_track(
        self,
        index: int,
        deck: int,
        *,
        announce_queue: bool,
    ) -> bool:
        self._invalidate_playback_recovery(reset_attempts=True)
        if not (0 <= index < len(self.queue)):
            return False
        if not (0 <= deck < len(self.players)):
            return False
        self.index = int(index)
        self.active = int(deck)
        if announce_queue:
            self._runtime_metrics["queue_position_commits"] += 1
            self.queueChanged.emit(self.queue)
        self._runtime_metrics["track_commits"] += 1
        self.trackChanged.emit(dict(self.queue[self.index]))
        self._schedule_transition_plan()
        return True

    def _load_index(
        self,
        index: int,
        play: bool = True,
        deck: int | None = None,
        *,
        announce_queue: bool = False,
    ) -> bool:
        self._invalidate_playback_recovery(reset_attempts=True)
        if not (0 <= index < len(self.queue)):
            return False
        deck = self.active if deck is None else int(deck)
        if deck == self.active:
            self._playback_should_play = bool(play)
        player = self.players[deck]
        try:
            if play and self._first_music_timeline is not None:
                self._first_music_play_by_deck[deck] = (
                    self._first_music_timeline.begin_play()
                )
                self._first_music_output_recorded.intersection_update(
                    self._first_music_play_by_deck.values()
                )
            resolved = self._resolve_for_playback(index)
            player.setSource(self._media_url_for(resolved))
            self._first_music_position_base[deck] = int(player.position())
            if not self._commit_track(index, deck, announce_queue=announce_queue):
                return False
            if play:
                player.play()
                self.playingChanged.emit(True)
            else:
                self.playingChanged.emit(False)
            return True
        except Exception as exc:
            if play:
                self.playingChanged.emit(False)
            self.error.emit(str(exc))
            return False

    def play_pause(self) -> None:
        self._invalidate_playback_recovery(reset_attempts=True)
        if self._crossfading:
            self._cancel_transition(stop_incoming=True, count_abort=True)
        player = self.players[self.active]
        if player.playbackState() == QMediaPlayer.PlayingState:
            self._playback_should_play = False
            player.pause()
            self.playingChanged.emit(False)
        else:
            self._playback_should_play = True
            if player.source().isEmpty() and self.index >= 0:
                self._load_index(self.index, True)
            else:
                if self._first_music_timeline is not None:
                    play_id = self._first_music_timeline.begin_play()
                    self._first_music_play_by_deck[self.active] = play_id
                    self._first_music_output_recorded.intersection_update(
                        self._first_music_play_by_deck.values()
                    )
                    self._first_music_position_base[self.active] = int(
                        player.position()
                    )
                player.play()
                self.playingChanged.emit(True)

    def next(self) -> None:
        self._runtime_metrics["manual_next"] += 1
        next_index = self.index + 1
        if next_index < len(self.queue):
            previous = dict(self.queue[self.index]) if 0 <= self.index < len(self.queue) else {}
            played_ms = int(self.players[self.active].position())
            duration_ms = int(self.players[self.active].duration())
            self._cancel_transition(stop_incoming=True, count_abort=True)
            self._stop_all_decks()
            self._load_index(
                next_index,
                True,
                announce_queue=True,
            )
            current = dict(self.queue[self.index]) if 0 <= self.index < len(self.queue) else {}
            self.manualAdvanced.emit(previous, current, played_ms, duration_ms)

    def replace_upcoming(self, tracks: list[dict[str, Any]]) -> None:
        """Replace only the queue tail, preserving the track currently playing."""
        incoming = [dict(item) for item in tracks]
        if not self.queue or self.index < 0:
            self.set_queue(incoming, 0, False)
            return
        if self._crossfading:
            self._cancel_transition(stop_incoming=True, count_abort=True)
        self.queue = self.queue[: self.index + 1] + incoming
        self.queueChanged.emit(self.queue)
        self._schedule_transition_plan()

    def previous(self) -> None:
        self._runtime_metrics["manual_previous"] += 1
        player = self.players[self.active]
        if self._crossfading:
            self._cancel_transition(stop_incoming=True, count_abort=True)
        if player.position() > 5000:
            player.setPosition(0)
        elif self.index > 0:
            self._stop_all_decks()
            self._load_index(
                self.index - 1,
                True,
                announce_queue=True,
            )

    def seek(self, ms: int) -> None:
        self._invalidate_playback_recovery(reset_attempts=True)
        target = max(0, int(ms))
        self._runtime_metrics["seek_requests"] += 1
        self._last_seek_requested_ms = target
        if self._crossfading:
            self._cancel_transition(stop_incoming=True, count_abort=True)
        self.players[self.active].setPosition(target)

    def set_volume(self, value: float) -> None:
        value = max(0.0, min(1.0, float(value)))
        self._volume = value
        self.outputs[self.active].setVolume(value)

    def _invalidate_transition_plan(self) -> None:
        self._transition_plan_generation += 1
        self._planned_transition_target = -1
        self._planned_transition_ms = 4500

    def _schedule_transition_plan(self) -> None:
        self._transition_plan_generation += 1
        generation = self._transition_plan_generation
        target = self.index + 1
        self._planned_transition_target = -1
        self._planned_transition_ms = 4500
        if self._playback_intent != "journey":
            self._emit_audio_processing_state()
            return
        if not (0 <= self.index < len(self.queue)) or target >= len(self.queue):
            self._emit_audio_processing_state()
            return
        if not self.transition_for:
            self._planned_transition_target = target
            self._emit_audio_processing_state()
            return

        current = dict(self.queue[self.index])
        upcoming = dict(self.queue[target])
        self._runtime_metrics["transition_plan_requests"] += 1

        def work() -> None:
            try:
                plan = self.transition_for(current, upcoming) or {}
                payload = {
                    "ok": True,
                    "duration_ms": max(300, int(plan.get("duration_ms", 4500))),
                }
            except Exception:
                payload = {"ok": False, "duration_ms": 4500}
            self._transitionPlanReady.emit(generation, target, payload)

        if self._transition_submit is None:
            work()
            self._emit_audio_processing_state()
            return
        try:
            accepted = bool(
                self._transition_submit(
                    work,
                    priority="prefetch",
                    name="transition-plan",
                    replace_key="transition-plan",
                )
            )
        except Exception:
            accepted = False
        if not accepted:
            self._runtime_metrics["transition_plan_submit_rejected"] += 1
            self._planned_transition_target = target
        self._emit_audio_processing_state()

    def _apply_transition_plan(
        self,
        generation: int,
        target: int,
        payload: object,
    ) -> None:
        if (
            int(generation) != self._transition_plan_generation
            or int(target) != self.index + 1
        ):
            self._runtime_metrics["transition_plan_stale"] += 1
            return
        row = dict(payload or {}) if isinstance(payload, dict) else {}
        self._planned_transition_target = int(target)
        self._planned_transition_ms = max(
            300,
            int(row.get("duration_ms") or 4500),
        )
        if bool(row.get("ok")):
            self._runtime_metrics["transition_plan_completed"] += 1
        else:
            self._runtime_metrics["transition_plan_failures"] += 1
        self._emit_audio_processing_state()

    def _transition_duration(self) -> int:
        if self._playback_intent != "journey":
            return 0
        if self.index + 1 >= len(self.queue):
            return 0
        if self._planned_transition_target == self.index + 1:
            return int(self._planned_transition_ms)
        return 4500

    def _begin_crossfade(self) -> None:
        if self._playback_intent != "journey":
            return
        if self._crossfading or self.index + 1 >= len(self.queue):
            return
        next_deck = 1 - self.active
        next_index = self.index + 1
        self._crossfading = True
        self._crossfade_target_index = next_index
        self._crossfade_deck = next_deck
        self._runtime_metrics["crossfade_started"] += 1
        self._transition_ms = self._transition_duration()
        self._emit_audio_processing_state()
        self.outputs[next_deck].setVolume(0.0)
        try:
            resolved = self._resolve_for_playback(next_index)
            url = self._media_url_for(resolved)
            if url.isEmpty():
                raise RuntimeError("Next track is not playable")
            self.players[next_deck].setSource(url)
            self.players[next_deck].play()
        except Exception as exc:
            self._cancel_transition(stop_incoming=True, count_abort=True)
            self.error.emit(str(exc))

    def _complete_crossfade(self, reason: str) -> bool:
        if not self._crossfading:
            return False
        target = self._crossfade_target_index
        incoming = self._crossfade_deck
        if (
            target is None
            or incoming is None
            or not (0 <= target < len(self.queue))
            or not (0 <= incoming < len(self.players))
        ):
            self._cancel_transition(stop_incoming=True, count_abort=True)
            return False

        outgoing = self.active
        self.players[outgoing].stop()
        self.outputs[outgoing].setVolume(0.0)
        self.outputs[incoming].setVolume(self._volume)
        self._clear_transition_state()
        self._runtime_metrics["crossfade_completed"] += 1
        if reason == "end_of_media":
            self._runtime_metrics["crossfade_eof_commits"] += 1

        committed = self._commit_track(
            target,
            incoming,
            announce_queue=True,
        )
        if committed:
            self.playingChanged.emit(
                self.players[incoming].playbackState()
                == QMediaPlayer.PlayingState
            )
        return committed

    def _on_player_error(self, deck: int, _error: object, message: object) -> None:
        """Keep failures on a speculative deck from disrupting active playback."""
        deck = int(deck)
        if not (0 <= deck < len(self.players)):
            return

        detail = str(message or "").strip() or "Playback failed"
        self._runtime_metrics["playback_errors"] += 1
        if deck != self.active:
            if self._crossfading and deck == self._crossfade_deck:
                self._runtime_metrics["incoming_deck_errors"] += 1
                self._cancel_transition(stop_incoming=False, count_abort=True)
                self.error.emit(
                    "Next track could not be prepared; current track continues. "
                    + detail
                )
            else:
                self._runtime_metrics["inactive_deck_errors_ignored"] += 1
            return

        self._runtime_metrics["active_deck_errors"] += 1
        error_name = _qt_error_name(_error)
        current = (
            self.queue[self.index]
            if 0 <= self.index < len(self.queue)
            else {}
        )
        local_source = bool(current.get("local_path"))
        if error_name == "ResourceError" and local_source:
            self._runtime_metrics["local_resource_errors"] += 1
            candidate = self._playback_recovery_candidate
            if candidate is not None and candidate.get("mode") == "local":
                self._playback_recovery_candidate = None
                self.players[deck].stop()
                self.players[deck].setSource(QUrl())
                self._runtime_metrics["local_reconnect_probe_failures"] += 1
                self._retry_or_finish_playback_recovery(
                    self._playback_recovery_generation,
                    self.index,
                    deck,
                    mode="local",
                )
                return
            if (
                self._local_reconnect_attempts == 0
                and not self._playback_recovery_pending
            ):
                self._playback_recovery_position_ms = max(
                    0, int(self.players[deck].position())
                )
                self._local_reconnect_resume = self._playback_should_play
                self.error.emit(
                    "Storage is unavailable. Checking again in the background."
                )
            self._queue_playback_recovery(
                self._playback_recovery_generation,
                self.index,
                deck,
                mode="local",
                resume_after_recovery=self._local_reconnect_resume,
            )
            return

        transient = error_name == "NetworkError" or (
            error_name == "ResourceError" and not local_source
        )
        if transient:
            self._runtime_metrics["transient_source_errors"] += 1
            if not self._playback_should_play:
                self._runtime_metrics["recovery_skipped_paused"] += 1
                self.error.emit(detail)
                return
            if (
                self.playback_refresher is None
                or self._playback_refresh_submit is None
            ):
                self._runtime_metrics["recovery_unavailable"] += 1
                self.error.emit(detail)
                return
            if self._playback_recovery_attempts == 0:
                self._playback_recovery_position_ms = max(
                    0, int(self.players[deck].position())
                )
                self.error.emit(
                    "Connection interrupted. Trying to resume playback."
                )
            self._queue_playback_recovery(
                self._playback_recovery_generation,
                self.index,
                deck,
            )
            return

        if error_name in {
            "FormatError",
            "AccessDeniedError",
            "ServiceMissingError",
            "ResourceError",
        }:
            self._runtime_metrics["permanent_source_errors"] += 1
        else:
            self._runtime_metrics["unclassified_source_errors"] += 1
        if self._playback_recovery_pending or self._playback_recovery_candidate:
            self._invalidate_playback_recovery(reset_attempts=False)
        self.error.emit(detail)

    def _on_buffer_progress(self, deck: int, progress: float) -> None:
        deck = int(deck)
        try:
            value = max(0.0, min(1.0, float(progress)))
        except (TypeError, ValueError):
            return
        self._buffer_progress_by_deck[deck] = value
        self._runtime_metrics["buffer_progress_events"] += 1
        if deck == self.active:
            permille = int(round(value * 1000))
            self._runtime_metrics["buffer_progress_min_permille"] = min(
                int(self._runtime_metrics["buffer_progress_min_permille"]),
                permille,
            )

    def _begin_buffer_stall(self, deck: int, cause: str) -> None:
        deck = int(deck)
        if deck != self.active:
            return
        if self._buffer_stall_started_at is None:
            self._buffer_stall_started_at = time.monotonic()
            self._buffer_stall_deck = deck
            self._buffer_stall_causes.clear()
            self._runtime_metrics["buffer_stall_events"] += 1
            self._buffer_notice_timer.start(400)
        if cause not in self._buffer_stall_causes:
            self._buffer_stall_causes.add(cause)
            if cause == "media_status":
                self._runtime_metrics["buffer_stall_status_events"] += 1
            elif cause == "no_progress":
                self._runtime_metrics["buffer_stall_no_progress_events"] += 1

    def _show_buffering_notice(self) -> None:
        if self._buffer_stall_started_at is None:
            return
        self._buffer_stall_notice_shown = True
        self._runtime_metrics["buffer_stall_notices"] += 1
        self.playbackNotice.emit("Buffering audio…", 0)

    def _end_buffer_stall(self) -> None:
        started_at = self._buffer_stall_started_at
        self._buffer_stall_started_at = None
        self._buffer_stall_deck = None
        self._buffer_stall_causes.clear()
        self._buffer_notice_timer.stop()
        if started_at is not None:
            elapsed_ms = max(0, int((time.monotonic() - started_at) * 1000))
            self._runtime_metrics["buffer_stall_ms_total"] += elapsed_ms
            self._runtime_metrics["buffer_stall_ms_max"] = max(
                int(self._runtime_metrics["buffer_stall_ms_max"]),
                elapsed_ms,
            )
        if self._buffer_stall_notice_shown:
            self._buffer_stall_notice_shown = False
            self.playbackNotice.emit("", 0)

    def _monitor_position_progress(
        self,
        deck: int,
        position_ms: int,
        playback_state: QMediaPlayer.PlaybackState,
    ) -> None:
        if int(deck) != self.active:
            return
        now = time.monotonic()
        position_ms = int(position_ms)
        if playback_state == QMediaPlayer.PlayingState:
            if position_ms != self._last_progress_position_ms:
                self._last_progress_position_ms = position_ms
                self._last_progress_at = now
                self._end_buffer_stall()
            elif now - self._last_progress_at >= (
                self._position_stall_threshold_ms / 1000.0
            ):
                self._begin_buffer_stall(deck, "no_progress")
            return
        self._last_progress_position_ms = position_ms
        self._last_progress_at = now
        if playback_state == QMediaPlayer.PausedState:
            self._end_buffer_stall()

    def _on_media_status(self, deck: int, status: QMediaPlayer.MediaStatus) -> None:
        deck = int(deck)
        if deck == self.active and status in {
            QMediaPlayer.StalledMedia,
            QMediaPlayer.BufferingMedia,
        }:
            self._begin_buffer_stall(deck, "media_status")
        if status in {
            QMediaPlayer.LoadedMedia,
            QMediaPlayer.BufferedMedia,
        }:
            self._complete_playback_recovery(deck)
            if (
                deck == self.active
                and self.players[deck].playbackState()
                == QMediaPlayer.PlayingState
            ):
                self._end_buffer_stall()
            play_id = self._first_music_play_by_deck.get(deck)
            if play_id is not None and self._first_music_timeline is not None:
                self._first_music_timeline.mark(
                    "decoder_started",
                    play_id=play_id,
                    source_id=self._first_music_timeline.source_for_play(play_id),
                )
        if status != QMediaPlayer.EndOfMedia:
            return

        if deck != self.active:
            if self._crossfading and deck == self._crossfade_deck:
                # The incoming deck ended before it became authoritative.
                # Keep the current track authoritative and abandon this transition.
                self._cancel_transition(stop_incoming=False, count_abort=True)
            return

        self._runtime_metrics["natural_ends"] += 1
        if self._crossfading:
            self._complete_crossfade("end_of_media")
            return

        next_index = self.index + 1
        if next_index < len(self.queue):
            other = 1 - self.active
            self.players[other].stop()
            self.outputs[other].setVolume(0.0)
            self._load_index(
                next_index,
                True,
                deck=self.active,
                announce_queue=True,
            )
            return

        self._playback_should_play = False
        self.playingChanged.emit(False)

    def _tick(self) -> None:
        self._runtime_metrics["ticks"] += 1
        player = self.players[self.active]
        duration, pos = player.duration(), player.position()
        self._monitor_position_progress(
            self.active, int(pos), player.playbackState()
        )
        play_id = self._first_music_play_by_deck.get(self.active)
        if (
            play_id is not None
            and play_id not in self._first_music_output_recorded
            and pos > self._first_music_position_base.get(self.active, 0)
            and player.playbackState() == QMediaPlayer.PlayingState
            and self._first_music_timeline is not None
        ):
            self._first_music_output_recorded.add(play_id)
            self._first_music_timeline.mark(
                "first_audio_output",
                play_id=play_id,
                source_id=self._first_music_timeline.source_for_play(play_id),
            )
        if duration > 0:
            self.positionChanged.emit(pos, duration)

        # Crossfade reconciliation must run before checking the outgoing
        # deck's playback state. The outgoing deck can enter EndOfMedia while
        # the incoming deck is already audible; returning here used to leave
        # Melodex showing the old track indefinitely.
        if self._crossfading:
            remaining = duration - pos if duration > 0 else 999999999
            incoming = self._crossfade_deck
            if duration > 0 and incoming is not None:
                progress = 1.0 - max(
                    0.0,
                    min(1.0, remaining / max(1, self._transition_ms)),
                )
                self.outputs[self.active].setVolume(
                    self._volume * max(0.0, 1.0 - progress)
                )
                self.outputs[incoming].setVolume(
                    self._volume * min(1.0, progress)
                )
                if progress >= 0.98 or remaining <= 80:
                    self._complete_crossfade("timer")
            return

        if player.playbackState() != QMediaPlayer.PlayingState:
            return
        if self.index + 1 >= len(self.queue):
            return
        if self._playback_intent != "journey":
            return
        transition = self._transition_duration()
        remaining = duration - pos if duration > 0 else 999999999
        if duration > 0 and remaining <= transition:
            self._begin_crossfade()
