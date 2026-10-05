from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from .playback_gateway import PlaybackGateway


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


class FlowPlayer(QObject):
    trackChanged = Signal(dict)
    positionChanged = Signal(int, int)
    playingChanged = Signal(bool)
    queueChanged = Signal(list)
    manualAdvanced = Signal(dict, dict, int, int)
    error = Signal(str)

    def __init__(
        self,
        resolver,
        transition_for=None,
        parent=None,
        playback_refresher=None,
    ):
        super().__init__(parent)
        self.resolver = resolver
        self.playback_refresher = playback_refresher
        self.transition_for = transition_for
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
        }
        self._last_seek_requested_ms = 0
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        for deck, player in enumerate(self.players):
            player.errorOccurred.connect(lambda _error, msg: self.error.emit(str(msg)))
            player.mediaStatusChanged.connect(
                lambda status, deck=deck: self._on_media_status(deck, status)
            )

    def set_queue(self, tracks: list[dict[str, Any]], start: int = 0, autoplay: bool = True) -> None:
        self._cancel_transition(stop_incoming=True, count_abort=True)
        self._stop_all_decks()
        self.queue = [dict(item) for item in tracks]
        self.index = max(0, min(len(self.queue) - 1, start)) if self.queue else -1
        self.queueChanged.emit(self.queue)
        if autoplay and self.index >= 0:
            self._load_index(self.index, play=True)
        else:
            self.playingChanged.emit(False)

    def append_queue(self, tracks: list[dict[str, Any]], autoplay: bool = False) -> None:
        incoming = [dict(item) for item in tracks]
        if not incoming:
            return
        if not self.queue:
            self.set_queue(incoming, 0, autoplay)
            return
        self.queue.extend(incoming)
        self.queueChanged.emit(self.queue)

    def queue_snapshot(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.queue]

    def jump_to(self, index: int, autoplay: bool = True) -> bool:
        index = int(index)
        if not (0 <= index < len(self.queue)):
            return False
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
        self.queue[index] = dict(track)
        self.queueChanged.emit(self.queue)
        if autoplay:
            self._cancel_transition(stop_incoming=True, count_abort=True)
            self._stop_all_decks()
            return self._load_index(index, True)
        return True

    def merge_queue_items(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        changes: dict[str, Any],
    ) -> int:
        updated = 0
        for index, item in enumerate(list(self.queue)):
            row = dict(item)
            if not predicate(row):
                continue
            self.queue[index] = {**row, **dict(changes)}
            updated += 1
        if updated:
            self.queueChanged.emit(self.queue)
        return updated

    def clear_queue(self) -> None:
        self._cancel_transition(stop_incoming=True, count_abort=True)
        self._stop_all_decks()
        self.queue = []
        self.index = -1
        self.queueChanged.emit(self.queue)
        self.playingChanged.emit(False)

    def stop(self) -> None:
        self._cancel_transition(stop_incoming=True, count_abort=True)
        self._stop_all_decks()
        self.playingChanged.emit(False)

    def close(self) -> None:
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
        return {
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
            "playing": bool(playing),
            "position_ms": int(player.position()),
            "duration_ms": int(player.duration()),
            "seekable": bool(player.isSeekable()),
            "last_seek_requested_ms": int(self._last_seek_requested_ms),
        }

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
        self.outputs[self.active].setVolume(1.0)
        if count_abort:
            self._runtime_metrics["transition_aborts"] += 1
        self._clear_transition_state()

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
        return True

    def _load_index(
        self,
        index: int,
        play: bool = True,
        deck: int | None = None,
        *,
        announce_queue: bool = False,
    ) -> bool:
        if not (0 <= index < len(self.queue)):
            return False
        deck = self.active if deck is None else int(deck)
        player = self.players[deck]
        try:
            resolved = self._resolve_for_playback(index)
            player.setSource(self._media_url_for(resolved))
            if not self._commit_track(index, deck, announce_queue=announce_queue):
                return False
            if play:
                player.play()
                self.playingChanged.emit(True)
            else:
                self.playingChanged.emit(False)
            return True
        except Exception as exc:
            self.error.emit(str(exc))
            return False

    def play_pause(self) -> None:
        player = self.players[self.active]
        if player.playbackState() == QMediaPlayer.PlayingState:
            player.pause()
            self.playingChanged.emit(False)
        else:
            if player.source().isEmpty() and self.index >= 0:
                self._load_index(self.index, True)
            else:
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
        target = max(0, int(ms))
        self._runtime_metrics["seek_requests"] += 1
        self._last_seek_requested_ms = target
        self.players[self.active].setPosition(target)

    def set_volume(self, value: float) -> None:
        value = max(0.0, min(1.0, float(value)))
        self.outputs[self.active].setVolume(value)

    def _transition_duration(self) -> int:
        if self.index + 1 >= len(self.queue):
            return 0
        if not self.transition_for:
            return 4500
        try:
            plan = self.transition_for(self.queue[self.index], self.queue[self.index + 1]) or {}
            return max(300, int(plan.get("duration_ms", 4500)))
        except Exception:
            return 4500

    def _begin_crossfade(self) -> None:
        if self._crossfading or self.index + 1 >= len(self.queue):
            return
        next_deck = 1 - self.active
        next_index = self.index + 1
        self._crossfading = True
        self._crossfade_target_index = next_index
        self._crossfade_deck = next_deck
        self._runtime_metrics["crossfade_started"] += 1
        self._transition_ms = self._transition_duration()
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
        self.outputs[incoming].setVolume(1.0)
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

    def _on_media_status(self, deck: int, status: QMediaPlayer.MediaStatus) -> None:
        if status != QMediaPlayer.EndOfMedia:
            return

        deck = int(deck)
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

        self.playingChanged.emit(False)

    def _tick(self) -> None:
        self._runtime_metrics["ticks"] += 1
        player = self.players[self.active]
        duration, pos = player.duration(), player.position()
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
                self.outputs[self.active].setVolume(max(0.0, 1.0 - progress))
                self.outputs[incoming].setVolume(min(1.0, progress))
                if progress >= 0.98 or remaining <= 80:
                    self._complete_crossfade("timer")
            return

        if player.playbackState() != QMediaPlayer.PlayingState:
            return
        if self.index + 1 >= len(self.queue):
            return
        transition = self._transition_duration()
        remaining = duration - pos if duration > 0 else 999999999
        if duration > 0 and remaining <= transition:
            self._begin_crossfade()
