from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class FlowPlayer(QObject):
    trackChanged = Signal(dict)
    positionChanged = Signal(int, int)
    playingChanged = Signal(bool)
    queueChanged = Signal(list)
    error = Signal(str)

    def __init__(self, resolver, transition_for=None, parent=None):
        super().__init__(parent)
        self.resolver = resolver
        self.transition_for = transition_for
        self.players = [QMediaPlayer(self), QMediaPlayer(self)]
        self.outputs = [QAudioOutput(self), QAudioOutput(self)]
        for p, o in zip(self.players, self.outputs):
            p.setAudioOutput(o)
            o.setVolume(1.0)
        self.active = 0
        self.queue: list[dict[str, Any]] = []
        self.index = -1
        self._crossfading = False
        self._transition_ms = 0
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        for p in self.players:
            p.errorOccurred.connect(lambda _e, msg: self.error.emit(str(msg)))

    def set_queue(self, tracks: list[dict[str, Any]], start: int = 0, autoplay: bool = True) -> None:
        self.queue = [dict(x) for x in tracks]
        self.index = max(0, min(len(self.queue) - 1, start)) if self.queue else -1
        self.queueChanged.emit(self.queue)
        if autoplay and self.index >= 0:
            self._load_index(self.index, play=True)

    def append_queue(self, tracks: list[dict[str, Any]], autoplay: bool = False) -> None:
        incoming = [dict(x) for x in tracks]
        if not incoming:
            return
        if not self.queue:
            self.set_queue(incoming, 0, autoplay)
            return
        self.queue.extend(incoming)
        self.queueChanged.emit(self.queue)

    def clear_queue(self) -> None:
        for p in self.players:
            p.stop()
        self.queue = []
        self.index = -1
        self._crossfading = False
        self.queueChanged.emit(self.queue)
        self.playingChanged.emit(False)

    def stop(self) -> None:
        for p in self.players:
            p.stop()
        self._crossfading = False
        self.playingChanged.emit(False)

    def current_track(self) -> dict[str, Any] | None:
        return dict(self.queue[self.index]) if 0 <= self.index < len(self.queue) else None

    def status(self) -> dict[str, Any]:
        p = self.players[self.active]
        return {
            "playing": p.playbackState() == QMediaPlayer.PlayingState,
            "position_ms": int(p.position()),
            "duration_ms": int(p.duration()),
            "volume": float(self.outputs[self.active].volume()),
            "index": int(self.index),
            "current_track": self.current_track(),
            "queue": [dict(x) for x in self.queue],
        }

    def _media_url(self, track: dict[str, Any]) -> QUrl:
        resolved = self.resolver(dict(track))
        self.queue[self.index] = dict(resolved)
        local = str(resolved.get("local_path") or "")
        if local:
            return QUrl.fromLocalFile(str(Path(local)))
        url = str(resolved.get("stream_url") or resolved.get("url") or "")
        if not url:
            raise RuntimeError("This source did not provide a playable stream")
        return QUrl(url)

    def _load_index(self, index: int, play: bool = True, deck: int | None = None) -> None:
        if not (0 <= index < len(self.queue)):
            return
        self.index = index
        deck = self.active if deck is None else deck
        p = self.players[deck]
        try:
            p.setSource(self._media_url(self.queue[index]))
            if play:
                p.play()
                self.playingChanged.emit(True)
            self.trackChanged.emit(dict(self.queue[index]))
        except Exception as exc:
            self.error.emit(str(exc))

    def play_pause(self) -> None:
        p = self.players[self.active]
        if p.playbackState() == QMediaPlayer.PlayingState:
            p.pause(); self.playingChanged.emit(False)
        else:
            if p.source().isEmpty() and self.index >= 0:
                self._load_index(self.index, True)
            else:
                p.play(); self.playingChanged.emit(True)

    def next(self) -> None:
        if self.index + 1 < len(self.queue):
            self.players[self.active].stop()
            self._crossfading = False
            self._load_index(self.index + 1, True)

    def previous(self) -> None:
        p = self.players[self.active]
        if p.position() > 5000:
            p.setPosition(0)
        elif self.index > 0:
            p.stop(); self._load_index(self.index - 1, True)

    def seek(self, ms: int) -> None:
        self.players[self.active].setPosition(max(0, int(ms)))

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
        self._crossfading = True
        self._transition_ms = self._transition_duration()
        next_deck = 1 - self.active
        self.outputs[next_deck].setVolume(0.0)
        next_index = self.index + 1
        try:
            resolved = self.resolver(dict(self.queue[next_index]))
            self.queue[next_index] = dict(resolved)
            local = str(resolved.get("local_path") or "")
            url = QUrl.fromLocalFile(local) if local else QUrl(str(resolved.get("stream_url") or ""))
            if url.isEmpty():
                raise RuntimeError("Next track is not playable")
            self.players[next_deck].setSource(url)
            self.players[next_deck].play()
        except Exception as exc:
            self._crossfading = False
            self.error.emit(str(exc))

    def _tick(self) -> None:
        p = self.players[self.active]
        duration, pos = p.duration(), p.position()
        if duration > 0:
            self.positionChanged.emit(pos, duration)
        if p.playbackState() != QMediaPlayer.PlayingState:
            return
        if self.index + 1 >= len(self.queue):
            return
        transition = self._transition_duration()
        remaining = duration - pos if duration > 0 else 999999999
        if not self._crossfading and duration > 0 and remaining <= transition:
            self._begin_crossfade()
        if self._crossfading:
            next_deck = 1 - self.active
            progress = 1.0 - max(0.0, min(1.0, remaining / max(1, self._transition_ms)))
            self.outputs[self.active].setVolume(max(0.0, 1.0 - progress))
            self.outputs[next_deck].setVolume(min(1.0, progress))
            if progress >= 0.98 or remaining <= 80:
                self.players[self.active].stop()
                self.outputs[self.active].setVolume(1.0)
                self.active = next_deck
                self.index += 1
                self.outputs[self.active].setVolume(1.0)
                self._crossfading = False
                self.trackChanged.emit(dict(self.queue[self.index]))
                self.queueChanged.emit(self.queue)
