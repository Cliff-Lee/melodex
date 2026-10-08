from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QMenu,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .motion import FAST_MOTION_MS, STANDARD_MOTION_MS
from .living_queue import LivingQueue, queue_track_key
from .playback_state import PlaybackSessionState
from .seek_control import SeekInteraction, SeekSlider
from .user_state import UserState
from .ux_components import CoverLabel, set_help


def _escape_html(value: Any) -> str:
    import html

    return html.escape(str(value or ""))


def _track_text(track: dict[str, Any]) -> str:
    artist = str(track.get("artist") or "Unknown artist")
    title = str(track.get("title") or "Unknown track")
    source = str(track.get("provider_id") or "")
    return f"{artist} — {title}" + (f"   ·   {source}" if source else "")


class PlaybackFeature(QObject):
    """Own persistent playback presentation and the lazy Now Playing workspace.

    FlowPlayer remains authoritative. This feature observes player state and
    requests playback mutations through semantic signals.
    """

    previousRequested = Signal()
    playPauseRequested = Signal()
    nextRequested = Signal()
    seekRequested = Signal(int)
    setQueueRequested = Signal(object, int, bool, str)
    appendQueueRequested = Signal(object, bool)
    jumpQueueRequested = Signal(int)
    replaceQueueItemRequested = Signal(int, object, bool)
    removeQueueItemRequested = Signal(int)
    moveQueueItemRequested = Signal(int, int)
    replaceUpcomingRequested = Signal(object)
    moreLikeRequested = Signal(object, int)
    towardArtistRequested = Signal(object)
    towardRegionRequested = Signal(object)
    steerJourneyRequested = Signal(str)
    currentTrackChanged = Signal(object)
    pluginDirectoryRequested = Signal(str)
    knowledgeChanged = Signal()
    statusMessageRequested = Signal(str, int)

    def __init__(
        self,
        providers: Any,
        user_state: Any,
        flow: Any,
        data_dir: Path,
        *,
        metadata: Callable[[], Any],
        knowledge: Callable[[], Any],
        llm_settings: Callable[[], Any],
        open_llm_settings: Callable[[], None],
        llm_complete: Callable[..., Any],
        run_async: Callable[..., Any],
        invalidate_async: Callable[[str], None],
        is_closing: Callable[[], bool],
        scan_active: Callable[[], bool],
        power_tools_enabled: Callable[[], bool],
        motion: Any,
        page_titles: dict[str, QLabel],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.providers = providers
        self.state = user_state
        self.flow = flow
        self.data_dir = Path(data_dir)
        self._metadata_getter = metadata
        self._knowledge_getter = knowledge
        self._llm_settings_getter = llm_settings
        self._open_llm_settings = open_llm_settings
        self._llm_complete = llm_complete
        self._run_async = run_async
        self._invalidate_async = invalidate_async
        self._is_closing = is_closing
        self._scan_active = scan_active
        self._power_tools_enabled = power_tools_enabled
        self.motion = motion
        self.page_titles = page_titles

        self._playback_state = PlaybackSessionState()
        self.living_queue = LivingQueue()
        self._queue_reasons: dict[tuple[str, ...], str] = {}
        self._visual_context_sequence = 0
        self._visual_neighbour_tracks: dict[int, dict[str, Any]] = {}
        self._visual_neighbour_artwork: dict[int, str] = {}
        self._visual_neighbour_preview_sequence = 0
        self._prefetched_track_assets: dict[str, dict[str, Any]] = {}
        self._prefetch_sequence = 0
        self._prefetch_delay_ms = 350
        self._play_history_generation = 0
        self._history_recorded_generation = 0
        self._history_completed_before_write: set[int] = set()
        self._seek_interaction = SeekInteraction()
        self._audio_processing = {
            "intent": "manual_queue",
            "transition_state": "off",
            "transition_ms": 0,
            "normalization": "off",
        }
        self.now_playing_page = QWidget()
        self.now_playing_built = False
        self.queue_panel = self._build_queue_panel()
        self.player_bar = self._build_player_bar()

    @property
    def metadata(self) -> Any:
        return self._metadata_getter()

    @property
    def knowledge(self) -> Any:
        return self._knowledge_getter()

    def current_track(self) -> dict[str, Any] | None:
        return self._playback_state.snapshot().current_track

    def current_position_ms(self) -> int:
        return self._playback_state.snapshot().position_ms

    def current_history_id(self) -> int:
        return self._playback_state.snapshot().current_history_id

    def on_position(self, position_ms: int, duration_ms: int) -> None:
        self._on_position(position_ms, duration_ms)

    def on_track_changed(self, track: object) -> None:
        row = dict(track or {}) if isinstance(track, dict) else {}
        if row:
            self._on_track_changed(row)

    def queue_snapshot(self) -> list[dict[str, Any]]:
        return list(self._playback_state.snapshot().queue)

    def queue_index(self) -> int:
        return self._playback_state.snapshot().queue_index

    @property
    def _current_track(self) -> dict[str, Any] | None:
        return self._playback_state.snapshot().current_track

    @property
    def _current_track_started(self) -> float:
        return self._playback_state.snapshot().current_track_started

    @property
    def _current_history_id(self) -> int:
        return self._playback_state.snapshot().current_history_id

    @property
    def _visual_position_ms(self) -> int:
        return self._playback_state.snapshot().position_ms

    @property
    def _visual_duration_ms(self) -> int:
        return self._playback_state.snapshot().duration_ms

    @property
    def _queue(self) -> list[dict[str, Any]]:
        return list(self._playback_state.snapshot().queue)

    @property
    def _queue_index(self) -> int:
        return self._playback_state.snapshot().queue_index

    @property
    def _playing(self) -> bool:
        return self._playback_state.snapshot().playing

    @_playing.setter
    def _playing(self, playing: bool) -> None:
        self._playback_state.set_playing(playing)

    def _status(self, message: str, timeout_ms: int = 0) -> None:
        self.statusMessageRequested.emit(str(message), int(timeout_ms))

    def _dialog_parent(self) -> QWidget:
        return self.now_playing_page if self.now_playing_built else self.player_bar

    def _page_layout(self, title: str, subtitle: str = ""):
        existing = self.now_playing_page.layout()
        if existing is None:
            layout = QVBoxLayout(self.now_playing_page)
        else:
            layout = existing
            while layout.count():
                item = layout.takeAt(0)
                child = item.widget()
                if child is not None:
                    child.deleteLater()
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        layout.addWidget(title_label)
        self.page_titles["now_playing"] = title_label
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setWordWrap(True)
            subtitle_label.setObjectName("pageSubtitle")
            layout.addWidget(subtitle_label)
        return layout

    def _build_queue_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("queuePanel")
        panel.setFixedWidth(330)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        head = QHBoxLayout()
        title = QLabel("Up next")
        title.setObjectName("panelTitle")
        head.addWidget(title)
        head.addStretch(1)
        flow_button = QPushButton("Refine with Flow")
        flow_button.setObjectName("quietButton")
        flow_button.clicked.connect(self._flow_queue)
        set_help(
            flow_button,
            "Refine with Flow",
            "Reorders upcoming music to make transitions feel more coherent while preserving the current track.",
        )
        head.addWidget(flow_button)
        layout.addLayout(head)
        self.queue_list = QListWidget()
        self.queue_list.itemDoubleClicked.connect(self._queue_jump)
        self.queue_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(
            self._queue_context_menu
        )
        layout.addWidget(self.queue_list, 1)
        self.queue_reason_label = QLabel("Select an upcoming track to see why it was chosen.")
        self.queue_reason_label.setWordWrap(True)
        self.queue_reason_label.setObjectName("queueReasonLabel")
        layout.addWidget(self.queue_reason_label)
        edit_row = QHBoxLayout()
        self.queue_keep_button = QPushButton("Keep")
        self.queue_keep_button.clicked.connect(self._queue_toggle_keep)
        set_help(
            self.queue_keep_button,
            "Keep this track",
            "Keep this track in the journey when Melodex changes the route. "
            "You can still move it yourself.",
        )
        self.queue_remove_button = QPushButton("Remove")
        self.queue_remove_button.clicked.connect(self._queue_remove_selected)
        set_help(
            self.queue_remove_button,
            "Remove from queue",
            "Remove the selected upcoming track. The track currently playing stays in place.",
        )
        self.queue_up_button = QPushButton("↑")
        self.queue_up_button.setAccessibleName("Move earlier")
        self.queue_up_button.clicked.connect(
            lambda: self._queue_move_selected(-1)
        )
        set_help(
            self.queue_up_button,
            "Move earlier",
            "Move the selected track earlier in the upcoming queue.",
        )
        self.queue_down_button = QPushButton("↓")
        self.queue_down_button.setAccessibleName("Move later")
        self.queue_down_button.clicked.connect(
            lambda: self._queue_move_selected(1)
        )
        set_help(
            self.queue_down_button,
            "Move later",
            "Move the selected track later in the upcoming queue.",
        )
        for button in (
            self.queue_keep_button,
            self.queue_remove_button,
            self.queue_up_button,
            self.queue_down_button,
        ):
            edit_row.addWidget(button)
        layout.addLayout(edit_row)
        safety_row = QHBoxLayout()
        self.queue_lock_button = QPushButton("Lock next 3")
        self.queue_lock_button.clicked.connect(self._queue_lock_next)
        set_help(
            self.queue_lock_button,
            "Lock next three tracks",
            "Keep the next three upcoming tracks fixed through automatic journey changes. "
            "Unlock individual tracks from their row menu.",
        )
        self.queue_undo_button = QPushButton("Undo route change")
        self.queue_undo_button.clicked.connect(self._queue_undo_replan)
        set_help(
            self.queue_undo_button,
            "Undo route change",
            "Restore the generated tracks from before the latest automatic route change. "
            "Your current track and protected choices stay in place.",
        )
        safety_row.addWidget(self.queue_lock_button)
        safety_row.addWidget(self.queue_undo_button)
        layout.addLayout(safety_row)
        steering_row = QHBoxLayout()
        self.queue_steering = QComboBox()
        self.queue_steering.addItem("Guide next…", "")
        for key, label in (
            ("calmer", "Calmer"),
            ("more_energy", "More energy"),
            ("darker", "Darker"),
            ("brighter", "Brighter"),
            ("more_rhythmic", "More rhythmic"),
            ("more_familiar", "More familiar"),
            ("more_surprising", "More surprising"),
            ("rediscover", "Rediscover"),
        ):
            self.queue_steering.addItem(label, key)
        self.queue_steer_button = QPushButton("Steer")
        self.queue_steer_button.clicked.connect(self._queue_apply_steer)
        set_help(
            self.queue_steering,
            "Steer the next part",
            "Choose a direction and Melodex will adapt the remaining live journey. "
            "Your kept tracks stay in the queue.",
        )
        set_help(
            self.queue_steer_button,
            "Apply direction",
            "Replan the remaining live journey using the selected direction.",
        )
        steering_row.addWidget(self.queue_steering, 1)
        steering_row.addWidget(self.queue_steer_button)
        layout.addLayout(steering_row)
        self.queue_more_like_button = QPushButton("More like selected track")
        self.queue_more_like_button.clicked.connect(
            self._queue_more_like_selected
        )
        set_help(
            self.queue_more_like_button,
            "More like this",
            "Find a nearby track like this one and adapt the rest of the live journey.",
        )
        layout.addWidget(self.queue_more_like_button)
        self.queue_list.currentRowChanged.connect(self._update_queue_edit_buttons)
        self._update_queue_edit_buttons()
        panel.hide()
        return panel

    def _build_player_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("playerBar")
        bar.setFixedHeight(86)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(8)

        previous = QPushButton()
        previous.setObjectName("transportButton")
        previous.setIcon(self._transport_icon("previous", "#c7ced9"))
        previous.setIconSize(QSize(18, 18))
        previous.setAccessibleName("Previous")
        previous.clicked.connect(self.previousRequested.emit)
        self.play_button = QPushButton()
        self.play_button.setObjectName("transportPrimaryButton")
        self.play_button.setIcon(self._transport_icon("play", "#ffffff"))
        self.play_button.setIconSize(QSize(18, 18))
        self.play_button.setAccessibleName("Play")
        self.play_button.clicked.connect(self.playPauseRequested.emit)
        next_button = QPushButton()
        next_button.setObjectName("transportButton")
        next_button.setIcon(self._transport_icon("next", "#c7ced9"))
        next_button.setIconSize(QSize(18, 18))
        next_button.setAccessibleName("Next")
        next_button.clicked.connect(self.nextRequested.emit)
        set_help(previous, "Previous", "Restart the current track or return to the previous track.")
        set_help(self.play_button, "Play / pause", "Pause or continue the current music.")
        set_help(next_button, "Next", "Move to the next track in the queue.")
        layout.addWidget(previous)
        layout.addWidget(self.play_button)
        layout.addWidget(next_button)

        self.player_cover = CoverLabel(52)
        self.player_cover.set_cover("", title="Melodex", key="melodex")
        self.player_cover.setToolTip("Now playing artwork")
        layout.addWidget(self.player_cover)

        text_column = QVBoxLayout()
        text_column.setSpacing(0)
        self.now_title = QPushButton("Nothing playing")
        self.now_title.setObjectName("nowPlayingTitle")
        set_help(
            self.now_title,
            "Open Now Playing",
            "See large artwork, lyrics, track information and visualisations for the current music.",
        )
        self.now_meta = QLabel("")
        self.now_meta.setObjectName("nowPlayingMeta")
        self.now_meta.setOpenExternalLinks(True)
        self.audio_processing_label = QLabel("")
        self.audio_processing_label.setObjectName("audioProcessingState")
        self.audio_processing_label.setToolTip(
            "Shows the transition behavior in effect. Melodex does not currently apply normalization."
        )
        text_column.addWidget(self.now_title)
        text_column.addWidget(self.now_meta)
        text_column.addWidget(self.audio_processing_label)
        self.seek = SeekSlider(Qt.Horizontal)
        self.seek.setObjectName("seekSlider")
        self.seek.setRange(0, 1000)
        self.seek.seekStarted.connect(self._seek_started)
        self.seek.seekFinished.connect(self._seek_finished)
        text_column.addWidget(self.seek)
        layout.addLayout(text_column, 1)

        self.keep_button = QPushButton("Keep")
        self.keep_button.setObjectName("playerAction")
        self.keep_button.clicked.connect(self._keep)
        self.love_button = QPushButton("♥")
        self.love_button.setObjectName("playerAction")
        self.love_button.clicked.connect(lambda: self._feedback(True))
        self.queue_button = QPushButton("Queue")
        self.queue_button.setObjectName("playerAction")
        self.queue_button.clicked.connect(
            lambda: self.queue_panel.setVisible(not self.queue_panel.isVisible())
        )
        set_help(
            self.keep_button,
            "Keep",
            "Teach Melodex that this track is worth keeping around in future listening.",
        )
        set_help(self.love_button, "Love", "Mark this as a strong positive preference.")
        set_help(self.queue_button, "Queue", "Show or hide the music that is coming next.")
        layout.addWidget(self.keep_button)
        layout.addWidget(self.love_button)
        layout.addWidget(self.queue_button)

        self.player_power_actions = QWidget()
        power_row = QHBoxLayout(self.player_power_actions)
        power_row.setContentsMargins(0, 0, 0, 0)
        power_row.setSpacing(6)
        match = QPushButton("Match")
        match.setObjectName("quietButton")
        match.clicked.connect(self._inspect_current_match)
        more = QPushButton("•••")
        more.setObjectName("quietButton")
        more.clicked.connect(self._more_actions)
        set_help(
            match, "Inspect match", "Show how Melodex resolved this track to its playable source."
        )
        set_help(
            more,
            "More actions",
            "Open technical and less frequently used actions for the current track.",
        )
        power_row.addWidget(match)
        power_row.addWidget(more)
        self.player_power_actions.setVisible(self._power_tools_enabled())
        layout.addWidget(self.player_power_actions)
        return bar

    @staticmethod
    def _transport_icon(name: str, color: str) -> QIcon:
        """Draw small transport marks so they do not depend on font glyphs."""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        if name == "play":
            painter.drawPolygon(QPolygon([QPoint(6, 3), QPoint(20, 12), QPoint(6, 21)]))
        elif name == "pause":
            painter.drawRoundedRect(5, 4, 5, 16, 1, 1)
            painter.drawRoundedRect(14, 4, 5, 16, 1, 1)
        elif name == "previous":
            painter.drawRect(3, 4, 2, 16)
            painter.drawPolygon(QPolygon([QPoint(12, 4), QPoint(5, 12), QPoint(12, 20)]))
            painter.drawPolygon(QPolygon([QPoint(21, 4), QPoint(14, 12), QPoint(21, 20)]))
        elif name == "next":
            painter.drawRect(19, 4, 2, 16)
            painter.drawPolygon(QPolygon([QPoint(12, 4), QPoint(19, 12), QPoint(12, 20)]))
            painter.drawPolygon(QPolygon([QPoint(3, 4), QPoint(10, 12), QPoint(3, 20)]))
        painter.end()
        return QIcon(pixmap)

    def set_open_now_playing_handler(self, callback: Callable[[], None]) -> None:
        self.now_title.clicked.connect(callback)

    def set_power_tools_visible(self, enabled: bool) -> None:
        self.player_power_actions.setVisible(bool(enabled))
        self._render_current_track_summary()

    def build_now_playing(self) -> None:
        if self.now_playing_built:
            return
        self._build_now_playing()
        self.now_playing_built = True
        if self._current_track and hasattr(self, "rich_now"):
            self.rich_now.set_track(dict(self._current_track))
        if hasattr(self, "living_canvas"):
            self.living_canvas.set_playing(self._playing)

    def _open_lyric_flow_fullscreen(self) -> None:
        """Reconcile the visual canvas with the reader immediately before opening."""
        if not hasattr(self, "living_canvas") or not hasattr(self, "rich_now"):
            return
        self.living_canvas.set_lyrics(self.rich_now.lyrics_document)
        self.living_canvas.set_position(
            self._visual_position_ms,
            self._visual_duration_ms,
        )
        self.living_canvas.show_lyric_flow_fullscreen()

    def on_audio_processing_changed(self, snapshot: object) -> None:
        self._audio_processing = (
            dict(snapshot) if isinstance(snapshot, dict) else {}
        )
        intent = str(self._audio_processing.get("intent") or "manual_queue")
        state = str(self._audio_processing.get("transition_state") or "off")
        transition_ms = max(0, int(self._audio_processing.get("transition_ms") or 0))
        if intent == "journey" and state in {"planned", "active"}:
            seconds = transition_ms / 1000
            transition = (
                f"Journey crossfade {state} · {seconds:g} s"
            )
        elif intent == "journey":
            transition = "Journey crossfade off"
        else:
            intent_label = {
                "album": "Album",
                "playlist": "Playlist",
                "manual_queue": "Queue",
                "provider": "Provider",
            }.get(intent, "Queue")
            transition = f"{intent_label} · crossfade off"
        normalization = str(
            self._audio_processing.get("normalization") or "off"
        )
        normalization_label = (
            "Normalization on"
            if normalization == "on"
            else "Normalization off"
        )
        summary = f"{transition} · {normalization_label}"
        self.audio_processing_label.setText(summary)
        if hasattr(self, "now_audio_processing_label"):
            self.now_audio_processing_label.setText(summary)

    def on_playing_changed(self, playing: bool) -> None:
        self._playing = bool(playing)
        state = "pause" if self._playing else "play"
        self.play_button.setIcon(self._transport_icon(state, "#ffffff"))
        self.play_button.setAccessibleName("Pause" if self._playing else "Play")
        if self.now_playing_built and hasattr(self, "living_canvas"):
            self.living_canvas.set_playing(self._playing)
        if (
            self._playing
            and self._current_track
            and self._play_history_generation
            != self._history_recorded_generation
        ):
            self._history_recorded_generation = self._play_history_generation
            self._schedule_play_history(
                dict(self._current_track), self._play_history_generation
            )

    def _schedule_play_history(
        self, track: dict[str, Any], history_generation: int
    ) -> None:
        """Write play history after FlowPlayer has acknowledged playback."""
        def history_recorded(result: object) -> None:
            history_id = max(0, int(result or 0))
            if not history_id:
                return
            completed_before_write = (
                history_generation in self._history_completed_before_write
            )
            self._history_completed_before_write.discard(history_generation)
            if (
                not completed_before_write
                and history_generation == self._play_history_generation
            ):
                self._playback_state.set_current_history_id(history_id)
            if completed_before_write:
                self._run_async(
                    lambda: self.state.mark_completed(history_id),
                    lambda _result: None,
                    lambda _error: None,
                    priority="background",
                    task_name="playback-completion-history",
                )

        self._run_async(
            lambda: self.state.record_play(dict(track)),
            history_recorded,
            lambda _error: None,
            priority="background",
            task_name="playback-start-history",
        )

    def _render_current_track_summary(self) -> None:
        track = dict(self._current_track or {})
        if not track:
            self.now_title.setText("Nothing playing")
            self.now_meta.setText("")
            return
        self.now_title.setText(str(track.get("title") or "Unknown track"))
        artist = str(track.get("artist") or "Unknown artist")
        album = str(track.get("album") or "")
        provider = str(track.get("provider_id") or "")
        pieces = [artist]
        if album:
            pieces.append(album)
        if self._power_tools_enabled() and provider:
            pieces.append(provider)
        source_page = str(track.get("source_page") or "")
        attribution = str(track.get("attribution") or "")
        base = "   ·   ".join(pieces)
        self.now_meta.setText(
            base
            + (
                f'   ·   <a href="{source_page}">{attribution or "Source"}</a>'
                if source_page
                else ""
            )
        )

    def merge_current_track(self, changes: dict[str, Any]) -> None:
        track = self._playback_state.merge_current_track(changes)
        if not track:
            return
        self._render_current_track_summary()
        if self.now_playing_built and hasattr(self, "rich_now"):
            self.rich_now.set_track(dict(track))
        self.currentTrackChanged.emit(dict(track))

    def apply_cached_artwork(self, token: str, path: str) -> None:
        current = dict(self._current_track or {})
        if token != UserState.track_key(current):
            return
        self.player_cover.set_cover(
            str(path or ""),
            title=str(current.get("album") or current.get("title") or ""),
            key=token,
        )

    def set_window_minimized(self, minimized: bool) -> None:
        if self.now_playing_built and hasattr(self, "living_canvas"):
            self.living_canvas.set_window_minimized(bool(minimized))

    def set_plugin_presence(self, *, lyrics: object = (), context: object = ()) -> None:
        if self.now_playing_built and hasattr(self, "rich_now"):
            self.rich_now.set_plugin_presence(
                lyrics=list(lyrics or ()),
                context=list(context or ()),
            )

    def record_feedback(self, positive: bool) -> None:
        self._feedback(bool(positive))

    def keep_current(self) -> None:
        self._keep()

    def refine_queue(self) -> None:
        self._flow_queue()

    def _build_now_playing(self):
        from .living_canvas import LivingCanvasView
        from .rich_now_playing import RichNowPlayingWidget

        l = self._page_layout(
            "Now playing",
            "Artwork, lyrics and context for what is playing now.",
        )
        self.now_audio_processing_label = QLabel("")
        self.now_audio_processing_label.setObjectName("audioProcessingState")
        self.now_audio_processing_label.setToolTip(
            "Shows the transition behavior in effect. Melodex does not currently apply normalization."
        )
        l.addWidget(self.now_audio_processing_label)
        self.on_audio_processing_changed(self._audio_processing)
        self.now_views = QTabWidget()
        self.rich_now = RichNowPlayingWidget(
            self.metadata,
            self.now_playing_page,
            auto_online_lyrics=self.state.get_bool("auto_online_lyrics", False),
        )
        self.living_canvas = LivingCanvasView(self.now_playing_page, self.data_dir / "visualizers")
        self.rich_now.knowledgeChanged.connect(self._remember_now_playing_knowledge)
        self.rich_now.accentChanged.connect(self.living_canvas.set_accent_color)
        self.rich_now.paletteChanged.connect(self.living_canvas.set_palette)
        self.rich_now.artworkChanged.connect(self.living_canvas.set_artwork)
        self.rich_now.lyricsStateChanged.connect(self.living_canvas.set_lyrics)
        self.rich_now.lyricsFullscreenRequested.connect(
            self._open_lyric_flow_fullscreen
        )
        self.rich_now.lyricsSeekRequested.connect(self.seekRequested.emit)
        self.rich_now.lyricsTranslationRequested.connect(self._translate_lyrics)
        self.rich_now.lyricsPluginRequested.connect(
            lambda: self.pluginDirectoryRequested.emit("lyrics")
        )
        self.rich_now.contextPluginRequested.connect(
            lambda: self.pluginDirectoryRequested.emit("context")
        )
        self.rich_now.onlineLyricsPreferenceChanged.connect(
            lambda enabled: self.state.set_bool("auto_online_lyrics", bool(enabled))
        )
        self.living_canvas.seekRequested.connect(self.seekRequested.emit)
        self.living_canvas.modeDataRequested.connect(self._request_visual_mode_data)
        self.living_canvas.neighbourActivated.connect(self._queue_visual_neighbour)
        self.living_canvas.neighbourPreviewRequested.connect(
            self._request_visual_neighbour_preview
        )
        self.now_views.addTab(self.rich_now, "Now Playing")
        self.now_views.addTab(self.living_canvas, "Visuals")
        l.addWidget(self.now_views, 1)

    @staticmethod
    def _path_for(track):
        path = str(track.get("local_path") or "")
        return Path(path) if path else None

    def _flow_queue(self):
        q = [dict(track) for track in self._queue]
        if len(q) < 2:
            return
        self._status("Planning Flow…")
        self._run_async(
            lambda: self.flow.plan_order(
                q, self._path_for, start_index=max(0, self._queue_index), adventurous=0.35
            ),
            lambda plan: self._apply_flow(plan),
            priority="foreground",
            task_name="flow-plan",
            replace_key="flow-plan",
        )

    def _apply_flow(self, plan):
        tracks = list(plan.get("tracks", []))
        self.setQueueRequested.emit(tracks, 0, True, "journey")
        self._status(f"Flow ready · {plan.get('analysed', 0)} tracks audio-analysed", 5000)

    def _next_queue_track(self) -> dict[str, Any]:
        queue = [dict(track) for track in self._queue]
        index = int(self._queue_index)
        next_index = index + 1
        if next_index < 0 or next_index >= len(queue):
            return {}
        row = queue[next_index]
        return dict(row) if isinstance(row, dict) else {}

    def _schedule_next_track_prefetch(self) -> None:
        if self._is_closing():
            return
        self._invalidate_async("next-track-prefetch")
        self._prefetch_sequence += 1
        sequence = self._prefetch_sequence
        QTimer.singleShot(
            self._prefetch_delay_ms,
            lambda token=sequence: self._prefetch_next_track_assets(token),
        )

    def _prefetch_next_track_assets(self, sequence: int) -> None:
        if self._is_closing() or sequence != self._prefetch_sequence or self._scan_active():
            return
        track = self._next_queue_track()
        token = UserState.track_key(track) if track else ""
        if not token or token in self._prefetched_track_assets:
            return

        def load() -> dict[str, Any]:
            payload: dict[str, Any] = {
                "token": token,
                "artwork_loaded": True,
                "artwork": {},
                "analysis_loaded": False,
                "analysis": None,
                "local_path": str(track.get("local_path") or "").strip(),
            }
            try:
                payload["artwork"] = dict(self.metadata.local_artwork(dict(track)) or {})
            except Exception:
                payload["artwork"] = {}
            local_path = str(payload["local_path"] or "")
            if local_path:
                payload["analysis_loaded"] = True
                try:
                    payload["analysis"] = self.flow.cached_analysis_for(Path(local_path))
                except Exception:
                    payload["analysis"] = None
            return payload

        def apply(payload: object) -> None:
            if sequence != self._prefetch_sequence or not isinstance(payload, dict):
                return
            current_next = self._next_queue_track()
            if token != UserState.track_key(current_next):
                return
            self._prefetched_track_assets[token] = dict(payload)
            # Keep this deliberately tiny: prediction must never become a
            # competing cache of the whole queue.
            while len(self._prefetched_track_assets) > 3:
                oldest = next(iter(self._prefetched_track_assets))
                self._prefetched_track_assets.pop(oldest, None)

        self._run_async(
            load,
            apply,
            priority="prefetch",
            task_name="next-track-prefetch",
            replace_key="next-track-prefetch",
        )

    # ------------------------------- player/taste

    def _on_track_changed(self, t):
        if self._is_closing():
            return
        self._seek_interaction.cancel()
        self.seek.setValue(0)
        for scope in (
            "now-playing-artwork",
            "taste-action-state",
            "now-playing-visual-analysis",
        ):
            self._invalidate_async(scope)
        if (
            self._current_track
            and self._current_track_started
            and self._history_recorded_generation == self._play_history_generation
            and time.time() - self._current_track_started < 30
        ):
            previous_track = dict(self._current_track)
            self._run_async(
                lambda: self.state.record_skip(previous_track),
                lambda _result: None,
                lambda _error: None,
                priority="background",
                task_name="playback-skip-history",
            )
        self._play_history_generation += 1
        self._playback_state.start_track(
            t,
            history_id=0,
            started_at=time.time(),
        )
        token = UserState.track_key(self._current_track)
        prefetched = dict(self._prefetched_track_assets.pop(token, {}) or {})
        self._set_taste_action_state()
        self._load_taste_action_state(self._current_track)
        if hasattr(self, "living_canvas"):
            local_path = str(self._current_track.get("local_path") or "").strip()
            if (
                prefetched.get("analysis_loaded")
                and str(prefetched.get("local_path") or "") == local_path
            ):
                self.living_canvas.set_track(
                    self._current_track,
                    prefetched.get("analysis"),
                )
            else:
                self.living_canvas.set_track(self._current_track, None)
                self._request_cached_visual_analysis(self._current_track)
        self.now_title.setText(str(t.get("title") or "Unknown track"))
        artist = str(t.get("artist") or "Unknown artist")
        album = str(t.get("album") or "")
        provider = str(t.get("provider_id") or "")
        pieces = [artist]
        if album:
            pieces.append(album)
        if self._power_tools_enabled() and provider:
            pieces.append(provider)
        src = str(t.get("source_page") or "")
        attr = str(t.get("attribution") or "")
        base = "   ·   ".join(pieces)
        self.now_meta.setText(
            base + ((f'   ·   <a href="{src}">{attr or "Source"}</a>') if src else "")
        )
        if hasattr(self, "player_cover"):
            artwork = dict(prefetched.get("artwork") or {})
            artwork_path = str(artwork.get("path") or "")
            self.player_cover.set_cover(
                artwork_path,
                title=album or str(t.get("title") or ""),
                key=token,
            )
            self.motion.settle(
                self.player_cover,
                duration_ms=STANDARD_MOTION_MS,
                start_opacity=0.84,
            )
            if not prefetched.get("artwork_loaded"):
                self._run_async(
                    lambda: self.metadata.local_artwork(dict(t)),
                    lambda result: self._player_artwork_loaded(token, result),
                    priority="visible",
                    task_name="now-playing-artwork",
                    replace_key="now-playing-artwork",
                )
        if hasattr(self, "rich_now"):
            self.rich_now.set_track(dict(t))
        if hasattr(self, "living_canvas"):
            self.living_canvas.refresh_context()
        self.currentTrackChanged.emit(dict(t))
        self._schedule_next_track_prefetch()

    def _player_artwork_loaded(self, token: str, result: object) -> None:
        if not isinstance(result, dict):
            return
        current = dict(self._current_track or {})
        if token != UserState.track_key(current):
            return
        self.player_cover.set_cover(
            str(result.get("path") or ""),
            title=str(current.get("album") or current.get("title") or ""),
            key=token,
        )
        self.motion.settle(
            self.player_cover,
            duration_ms=STANDARD_MOTION_MS,
            start_opacity=0.84,
        )

    def _request_cached_visual_analysis(self, track: dict[str, Any]) -> None:
        local_path = str(track.get("local_path") or "").strip()
        if not local_path:
            return

        def lookup() -> object:
            try:
                return self.flow.cached_analysis_for(Path(local_path))
            except Exception:
                return None

        self._run_async(
            lookup,
            lambda analysis, path=local_path: self._visual_analysis_loaded(
                path,
                analysis,
            ),
            priority="visible",
            task_name="now-playing-visual-analysis",
            replace_key="now-playing-visual-analysis",
        )

    def _visual_analysis_loaded(self, local_path: str, analysis: object) -> None:
        current_path = str((self._current_track or {}).get("local_path") or "")
        if self._is_closing() or not local_path or local_path != current_path:
            return
        self.living_canvas.set_analysis(analysis)
        self.living_canvas.set_position(self._visual_position_ms, self._visual_duration_ms)

    def _request_visual_mode_data(self, request: str) -> None:
        from .visualization_models import build_visual_memory

        if self._is_closing() or not hasattr(self, "living_canvas"):
            return
        mode, _, scale = str(request or "").partition(":")
        scale = scale or str(self.living_canvas.memory_scale.currentData() or "sessions")
        if mode not in {"constellation", "memory"}:
            return

        self._visual_context_sequence += 1
        sequence = self._visual_context_sequence
        queue_candidates: list[dict[str, Any]] = []
        if mode == "constellation":
            queue = [dict(track) for track in self._queue]
            current_index = int(self._queue_index)
            start = max(0, current_index - 5)
            end = min(len(queue), current_index + 21)
            for index in range(start, end):
                if index == current_index or not isinstance(queue[index], dict):
                    continue
                queue_candidates.append(
                    {
                        "_visual_token": len(queue_candidates),
                        "_visual_relation": "Up next"
                        if index > current_index
                        else "Played earlier",
                        "track": dict(queue[index]),
                    }
                )
        limit = 2000 if mode == "memory" else 120

        def load_context() -> object:
            try:
                recent = self.state.recent_tracks(limit)
                if mode == "memory":
                    return {
                        "scale": scale,
                        "marks": build_visual_memory(recent, scale),
                    }
                return {"queue": queue_candidates, "recent": recent}
            except Exception:
                return (
                    {"scale": scale, "marks": ()}
                    if mode == "memory"
                    else {"queue": queue_candidates, "recent": []}
                )

        self._run_async(
            load_context,
            lambda payload, token=sequence, mode_name=mode: self._visual_context_loaded(
                token, mode_name, payload
            ),
            priority="visible",
            task_name="now-playing-visual-context",
            replace_key="now-playing-visual-context",
        )

    def _visual_context_loaded(self, sequence: int, mode: str, payload: object) -> None:
        from .visualization_models import build_constellation

        if self._is_closing() or sequence != self._visual_context_sequence:
            return
        if not hasattr(self, "living_canvas") or self.living_canvas.active_mode != mode:
            return
        if not isinstance(payload, dict):
            return
        if mode == "memory":
            scale = str(payload.get("scale") or "sessions")
            if scale != str(self.living_canvas.memory_scale.currentData() or "sessions"):
                return
            self.living_canvas.set_memory_marks(tuple(payload.get("marks") or ()), scale)
            return

        current = dict(self._current_track or {})
        candidates = [row for row in payload.get("queue", ()) if isinstance(row, dict)]
        refs: dict[int, dict[str, Any]] = {}
        for row in candidates:
            try:
                refs[int(row.get("_visual_token"))] = dict(row.get("track") or {})
            except (TypeError, ValueError, OverflowError):
                continue
        token = max(refs, default=-1) + 1
        for track in payload.get("recent", ()):
            if not isinstance(track, dict):
                continue
            candidates.append(
                {
                    "_visual_token": token,
                    "_visual_relation": "Played earlier",
                    "track": dict(track),
                }
            )
            refs[token] = dict(track)
            token += 1
        neighbours = build_constellation(current, candidates, limit=24)
        self._visual_neighbour_tracks = {
            node.token: refs[node.token] for node in neighbours if node.token in refs
        }
        self._visual_neighbour_artwork = {}
        self._visual_neighbour_preview_sequence += 1
        self.living_canvas.set_neighbours(neighbours)

        # The normal next-track prefetch may already have exactly the local cover
        # we need. Reuse it rather than doing even a cheap second lookup.
        for node in neighbours:
            track = self._visual_neighbour_tracks.get(node.token) or {}
            track_key = UserState.track_key(track)
            prefetched = dict(self._prefetched_track_assets.get(track_key, {}) or {})
            artwork = dict(prefetched.get("artwork") or {})
            path = str(artwork.get("path") or "")
            if path:
                self._visual_neighbour_artwork[node.token] = path
                self.living_canvas.set_neighbour_artwork(node.token, path)

    def _request_visual_neighbour_preview(self, token: int) -> None:
        token = int(token)
        track = self._visual_neighbour_tracks.get(token)
        if not track or self._is_closing():
            return

        if token in self._visual_neighbour_artwork:
            if hasattr(self, "living_canvas"):
                self.living_canvas.set_neighbour_artwork(
                    token,
                    self._visual_neighbour_artwork[token],
                )
            return

        track_key = UserState.track_key(track)
        prefetched = dict(self._prefetched_track_assets.get(track_key, {}) or {})
        prefetched_art = dict(prefetched.get("artwork") or {})
        prefetched_path = str(prefetched_art.get("path") or "")
        if prefetched_path:
            self._visual_neighbour_artwork[token] = prefetched_path
            if hasattr(self, "living_canvas"):
                self.living_canvas.set_neighbour_artwork(token, prefetched_path)
            return

        self._visual_neighbour_preview_sequence += 1
        preview_sequence = self._visual_neighbour_preview_sequence
        context_sequence = self._visual_context_sequence

        def load() -> object:
            try:
                return dict(self.metadata.local_artwork(dict(track)) or {})
            except Exception:
                return {}

        def apply(result: object) -> None:
            if (
                self._is_closing()
                or preview_sequence != self._visual_neighbour_preview_sequence
                or context_sequence != self._visual_context_sequence
                or not isinstance(result, dict)
            ):
                return
            current = self._visual_neighbour_tracks.get(token)
            if not current or UserState.track_key(current) != track_key:
                return
            path = str(result.get("path") or "")
            self._visual_neighbour_artwork[token] = path
            if hasattr(self, "living_canvas") and self.living_canvas.active_mode == "constellation":
                self.living_canvas.set_neighbour_artwork(token, path)

        self._run_async(
            load,
            apply,
            priority="visible",
            task_name="constellation-hover-artwork",
            replace_key="constellation-hover-artwork",
        )

    def _queue_visual_neighbour(self, token: int) -> None:
        track = self._visual_neighbour_tracks.get(int(token))
        if not track:
            return
        self.appendQueueRequested.emit([dict(track)], False)
        self._status(
            f"Queued {track.get('artist') or 'Unknown artist'} — {track.get('title') or 'Unknown track'}",
            4000,
        )

    def _on_position(self, pos, dur):
        if self._is_closing():
            return
        self._playback_state.update_position(pos, dur)
        if hasattr(self, "living_canvas"):
            self.living_canvas.set_position(pos, dur)
            self.living_canvas.set_playing(self._playing)
        if hasattr(self, "rich_now"):
            self.rich_now.set_position(pos)
        if dur > 0 and self._seek_interaction.follow_player_position(pos, dur):
            self.seek.setValue(int(1000 * pos / dur))
        if dur > 0 and pos >= dur - 1500:
            history_id = self._current_history_id
            if history_id:
                completed_id = self._playback_state.mark_current_track_completed()
                self._run_async(
                    lambda: self.state.mark_completed(completed_id),
                    lambda _result: None,
                    lambda _error: None,
                    priority="background",
                    task_name="playback-completion-history",
                )
            elif self._play_history_generation:
                self._history_completed_before_write.add(
                    self._play_history_generation
                )

    def _seek_started(self) -> None:
        self._seek_interaction.begin()

    def _seek_finished(self, value: int) -> None:
        target = self._seek_interaction.commit(value, self._visual_duration_ms)
        if target is not None:
            self.seekRequested.emit(target)

    def _seek_released(self) -> None:
        """Compatibility shim for older tests/callers using QSlider semantics."""
        self._seek_finished(int(self.seek.value()))

    def _set_taste_action_state(
        self,
        *,
        loved: bool = False,
        kept: bool = False,
    ) -> None:
        if hasattr(self, "love_button"):
            self.love_button.setText("♥ Loved" if loved else "♥")
            self.love_button.setEnabled(not loved)
        if hasattr(self, "keep_button"):
            self.keep_button.setText("✓ Kept" if kept else "Keep")
            self.keep_button.setEnabled(not kept)

    def _load_taste_action_state(self, track: dict[str, Any]) -> None:
        token = UserState.track_key(track)
        if not token:
            self._set_taste_action_state()
            return

        def apply(signal: object) -> None:
            if token != UserState.track_key(dict(self._current_track or {})):
                return
            row = dict(signal or {}) if isinstance(signal, dict) else {}
            self._set_taste_action_state(
                loved=bool(int(row.get("loves") or 0)),
                kept=bool(int(row.get("keeps") or 0)),
            )

        self._run_async(
            lambda: self.state.track_signal(dict(track)),
            apply,
            priority="visible",
            task_name="taste-action-state",
            replace_key="taste-action-state",
        )

    def _feedback(self, positive):
        if not self._current_track:
            return
        track = dict(self._current_track)
        token = UserState.track_key(track)
        if positive and hasattr(self, "love_button"):
            previous_text = self.love_button.text()
            previous_enabled = self.love_button.isEnabled()
            self.love_button.setText("♥ Loved")
            self.love_button.setEnabled(False)
            self.motion.settle(
                self.love_button,
                duration_ms=FAST_MOTION_MS,
                start_opacity=0.82,
            )
            self._status("Loved", 2500)
        else:
            previous_text = ""
            previous_enabled = True
            self._status(
                "Loved" if positive else "Not for me",
                2500,
            )

        def persist() -> bool:
            self.state.record_feedback(track, positive)
            return True

        def failed(error: str) -> None:
            if positive and token == UserState.track_key(dict(self._current_track or {})):
                self.love_button.setText(previous_text)
                self.love_button.setEnabled(previous_enabled)
            self._status(
                f"Could not save preference · {error}",
                5000,
            )

        self._run_async(
            persist,
            lambda _result: None,
            failed,
            priority="foreground",
            task_name="taste-feedback-save",
        )

    def _keep(self):
        if not self._current_track:
            return
        track = dict(self._current_track)
        token = UserState.track_key(track)
        previous_text = self.keep_button.text() if hasattr(self, "keep_button") else "Keep"
        previous_enabled = self.keep_button.isEnabled() if hasattr(self, "keep_button") else True
        if hasattr(self, "keep_button"):
            self.keep_button.setText("✓ Kept")
            self.keep_button.setEnabled(False)
            self.motion.settle(
                self.keep_button,
                duration_ms=FAST_MOTION_MS,
                start_opacity=0.82,
            )
        self._status("Kept in taste memory", 2500)

        def persist() -> bool:
            self.state.record_keep(track)
            return True

        def failed(error: str) -> None:
            if token == UserState.track_key(dict(self._current_track or {})) and hasattr(
                self, "keep_button"
            ):
                self.keep_button.setText(previous_text)
                self.keep_button.setEnabled(previous_enabled)
            self._status(
                f"Could not save Keep · {error}",
                5000,
            )

        self._run_async(
            persist, lambda _result: None, failed, priority="foreground", task_name="keep-save"
        )

    def _more_actions(self):
        if not self._current_track:
            return
        label, ok = QInputDialog.getText(
            self._dialog_parent(), "Save a moment", "Moment note (leave blank if you like):"
        )
        if ok:
            self.state.save_moment(self._current_track, self._visual_position_ms, label)
            self._status("Moment saved", 3000)

    @staticmethod
    def _resolver_target(track):
        track = dict(track or {})
        resolution = track.get("_resolution")
        if isinstance(resolution, dict) and isinstance(resolution.get("requested"), dict):
            requested = dict(resolution.get("requested") or {})
            if str(requested.get("title") or "").strip():
                return requested
        return {
            "artist": str(track.get("artist") or ""),
            "title": str(track.get("title") or ""),
            "album": str(track.get("album") or ""),
            "duration": track.get("duration") or 0,
        }

    def _inspect_current_match(self):
        if not self._current_track:
            self._status("Play a track first, then inspect its source match", 3500)
            return
        target = self._resolver_target(self._current_track)
        self._status("Checking resolver candidates…")
        self._run_async(
            lambda: self.providers.inspect_resolution(target, 24),
            lambda info: self._show_resolver_inspector(target, info),
            priority="foreground",
            task_name="resolver-inspect",
        )

    def _show_resolver_inspector(self, target, info):
        d = QDialog(self._dialog_parent())
        d.setWindowTitle("Resolver Inspector")
        d.resize(760, 560)
        lay = QVBoxLayout(d)
        requested = f"{target.get('artist', '')} — {target.get('title', '')}".strip(" —")
        album = str(target.get("album") or "")
        head = QLabel(f"Requested: {requested}" + (f"  ·  {album}" if album else ""))
        head.setWordWrap(True)
        lay.addWidget(head)
        blocked = int(info.get("blocked_count") or 0)
        threshold = float(info.get("minimum_score") or 0.62)
        preferred = info.get("preferred")
        summary = QLabel(
            f"Automatic threshold: {threshold:.0%}  ·  Wrong matches remembered: {blocked}"
            + ("  ·  Preferred match remembered" if preferred else "")
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("color:#aab0ba")
        lay.addWidget(summary)
        rows = QListWidget()
        lay.addWidget(rows, 1)
        current_pid = str((self._current_track or {}).get("provider_id") or "")
        current_tid = str((self._current_track or {}).get("track_id") or "")
        current_row = -1
        for i, row in enumerate(list(info.get("candidates") or [])):
            if not isinstance(row, dict):
                continue
            t = dict(row.get("track") or {})
            score = float(row.get("score") or 0)
            provider = str(row.get("provider_id") or t.get("provider_id") or "")
            flags = ", ".join(list(row.get("flags") or []))
            reasons = " · ".join(list(row.get("reasons") or []))
            duration = row.get("duration_delta")
            duration_text = f" · Δ{float(duration):.0f}s" if duration is not None else ""
            star = "★ " if bool(row.get("preferred")) else ""
            line1 = f"{star}{score:.0%}  {provider}  ·  {t.get('artist', 'Unknown artist')} — {t.get('title', 'Unknown track')}"
            line2 = f"title {float(row.get('title_score') or 0):.0%} · artist {float(row.get('artist_score') or 0):.0%} · album {float(row.get('album_score') or 0):.0%}{duration_text}"
            if flags:
                line2 += f" · [{flags}]"
            if reasons:
                line2 += f"\n{reasons}"
            item = QListWidgetItem(line1 + "\n" + line2)
            item.setData(Qt.UserRole, row)
            rows.addItem(item)
            if (
                str(t.get("provider_id") or "") == current_pid
                and str(t.get("track_id") or "") == current_tid
            ):
                current_row = rows.count() - 1
        if rows.count() == 0:
            rows.addItem("No resolver candidates were returned by the connected sources.")
        else:
            rows.setCurrentRow(current_row if current_row >= 0 else 0)
        buttons = QHBoxLayout()
        play = QPushButton("Play this match")
        prefer = QPushButton("Prefer")
        wrong = QPushButton("Wrong match")
        reset = QPushButton("Reset memory")
        close = QPushButton("Close")
        for b in (play, prefer, wrong, reset, close):
            buttons.addWidget(b)
        lay.addLayout(buttons)

        def selected():
            item = rows.currentItem()
            data = item.data(Qt.UserRole) if item else None
            return dict(data or {}) if isinstance(data, dict) else {}

        play.clicked.connect(lambda: self._resolver_use_candidate(target, selected(), d, False))
        prefer.clicked.connect(lambda: self._resolver_use_candidate(target, selected(), d, True))
        wrong.clicked.connect(lambda: self._resolver_wrong_candidate(target, selected(), d))
        reset.clicked.connect(lambda: self._resolver_reset_memory(target, d))
        close.clicked.connect(d.reject)
        d.exec()

    def _resolver_use_candidate(self, target, row, dialog, remember):
        candidate = dict(row.get("track") or {}) if isinstance(row, dict) else {}
        if not candidate:
            self._status("Select a resolver candidate first", 3000)
            return
        if remember:
            self.providers.prefer_resolution(target, candidate)
        dialog.accept()
        self._status("Using preferred match…" if remember else "Loading selected match…")
        self._run_async(
            lambda: self.providers.resolve_exact(candidate, target),
            self._apply_resolver_match,
            priority="foreground",
            task_name="resolver-use",
        )

    def _resolver_wrong_candidate(self, target, row, dialog):
        candidate = dict(row.get("track") or {}) if isinstance(row, dict) else {}
        if not candidate:
            self._status("Select a resolver candidate first", 3000)
            return
        self.providers.block_resolution(target, candidate)
        dialog.accept()
        self._status("Wrong match remembered · trying the next candidate…")
        self._run_async(
            lambda: self.providers.resolve(target),
            self._apply_resolver_match,
            priority="foreground",
            task_name="resolver-retry",
        )

    def _resolver_reset_memory(self, target, dialog):
        self.providers.clear_resolution_preference(target)
        self.providers.clear_resolution_blocks(target)
        dialog.accept()
        self._status("Match memory reset for this song", 3500)
        self._run_async(
            lambda: self.providers.inspect_resolution(target, 24),
            lambda info: self._show_resolver_inspector(target, info),
            priority="foreground",
            task_name="resolver-reset",
        )

    def _apply_resolver_match(self, resolved):
        if not isinstance(resolved, dict):
            return
        idx = int(self._queue_index)
        if idx < 0:
            self.setQueueRequested.emit([dict(resolved)], 0, True, "manual_queue")
            return
        self.replaceQueueItemRequested.emit(idx, dict(resolved), True)
        mode = (
            str((resolved.get("_resolution") or {}).get("mode") or "match")
            if isinstance(resolved.get("_resolution"), dict)
            else "match"
        )
        self._status(f"Resolver match applied · {mode}", 4000)

    def on_queue_changed(self, tracks, index=-1):
        incoming = [track for track in list(tracks or []) if isinstance(track, dict)]
        previous = self._queue
        append_only = bool(previous) and len(incoming) > len(previous) and all(
            queue_track_key(old) == queue_track_key(new)
            for old, new in zip(previous, incoming)
        )
        self._playback_state.update_queue(
            incoming,
            index,
        )
        self.living_queue.sync_from_tracks(
            self._queue,
            self._queue_index,
            new_origin="manual" if append_only else "route",
        )
        selected = self.queue_list.currentRow()
        self.queue_list.clear()
        for i, t in enumerate(self._queue):
            entry = self.living_queue.entries[i]
            markers = []
            if entry.pinned:
                markers.append("Kept")
            if entry.locked:
                markers.append("Locked")
            prefix = "▶ " if i == self._queue_index else ""
            if markers:
                prefix += " · ".join(markers) + " · "
            item = QListWidgetItem(prefix + _track_text(t))
            item.setData(Qt.UserRole, i)
            if entry.pinned or entry.locked:
                item.setToolTip(
                    "This track is protected from automatic journey changes."
                )
            explanation = self._queue_reasons.get(queue_track_key(t), "")
            if explanation:
                item.setToolTip(
                    (item.toolTip() + "\n" if item.toolTip() else "")
                    + "Why this track: "
                    + explanation
                )
            self.queue_list.addItem(item)
        if self._queue:
            restored_row = (
                selected
                if 0 <= selected < len(self._queue)
                else self._queue_index
            )
            if 0 <= restored_row < len(self._queue):
                self.queue_list.setCurrentRow(restored_row)
        self._update_queue_edit_buttons()
        if hasattr(self, "living_canvas") and self.living_canvas.active_mode == "constellation":
            self.living_canvas.refresh_context()
        self._schedule_next_track_prefetch()

    def apply_journey_replan(self, tracks):
        """Apply a route tail without dropping choices protected by the user."""
        self.living_queue.sync_from_tracks(self._queue, self._queue_index)
        self.living_queue.replace_generated_tail(
            [track for track in list(tracks or []) if isinstance(track, dict)]
        )
        start = max(0, self._queue_index + 1)
        self.replaceUpcomingRequested.emit(self.living_queue.tracks()[start:])

    def set_queue_track_reasons(self, reasons) -> None:
        self._queue_reasons = {
            tuple(key): str(value)
            for key, value in dict(reasons or {}).items()
            if isinstance(key, (tuple, list)) and str(value or "").strip()
        }
        for index, entry in enumerate(self.living_queue.entries):
            item = self.queue_list.item(index)
            if item is None:
                continue
            parts = []
            if entry.pinned or entry.locked:
                parts.append("This track is protected from automatic journey changes.")
            explanation = self._queue_reasons.get(queue_track_key(entry.track), "")
            if explanation:
                parts.append("Why this track: " + explanation)
            item.setToolTip("\n".join(parts))
        self._update_queue_edit_buttons()

    def _queue_jump(self, item):
        self.jumpQueueRequested.emit(int(item.data(Qt.UserRole)))

    def _queue_context_menu(self, position):
        item = self.queue_list.itemAt(position)
        if item is None:
            return
        self.queue_list.setCurrentItem(item)
        index = int(item.data(Qt.UserRole))
        entry = self.living_queue.entries[index]
        menu = QMenu(self.queue_list)
        keep = menu.addAction(
            "Remove from journey" if entry.pinned else "Keep in journey"
        )
        lock = menu.addAction("Unlock track" if entry.locked else "Lock track")
        more_like = menu.addAction("More like this after it")
        toward_artist = menu.addAction("Head toward this artist")
        toward_region = menu.addAction("Explore this map area")
        remove = menu.addAction("Remove from queue")
        menu.addSeparator()
        earlier = menu.addAction("Move earlier")
        later = menu.addAction("Move later")
        upcoming = index > self._queue_index
        keep.setEnabled(upcoming)
        lock.setEnabled(upcoming)
        more_like.setEnabled(index >= self._queue_index)
        toward_artist.setEnabled(index >= self._queue_index)
        toward_region.setEnabled(index >= self._queue_index)
        remove.setEnabled(self.living_queue.can_remove(index))
        earlier.setEnabled(self.living_queue.can_move(index, index - 1))
        later.setEnabled(self.living_queue.can_move(index, index + 1))
        chosen = menu.exec(self.queue_list.mapToGlobal(position))
        if chosen is keep:
            self._queue_toggle_keep()
        elif chosen is lock:
            self._queue_toggle_lock()
        elif chosen is more_like:
            self._queue_more_like_selected()
        elif chosen is toward_artist:
            self._queue_toward_artist_selected()
        elif chosen is toward_region:
            self._queue_toward_region_selected()
        elif chosen is remove:
            self._queue_remove_selected()
        elif chosen is earlier:
            self._queue_move_selected(-1)
        elif chosen is later:
            self._queue_move_selected(1)

    def _update_queue_edit_buttons(self, _row=-1):
        if not hasattr(self, "queue_keep_button"):
            return
        index = self.queue_list.currentRow()
        upcoming = index > self._queue_index and index >= 0
        pinned = (
            upcoming
            and index < len(self.living_queue.entries)
            and self.living_queue.entries[index].pinned
        )
        self.queue_keep_button.setText("Unkeep" if pinned else "Keep")
        self.queue_keep_button.setEnabled(upcoming)
        self.queue_lock_button.setEnabled(
            any(index > self._queue_index for index in range(len(self._queue)))
        )
        self.queue_undo_button.setEnabled(self.living_queue.can_undo_replan)
        self.queue_remove_button.setEnabled(self.living_queue.can_remove(index))
        self.queue_up_button.setEnabled(self.living_queue.can_move(index, index - 1))
        self.queue_down_button.setEnabled(self.living_queue.can_move(index, index + 1))
        self.queue_more_like_button.setEnabled(
            0 <= index < len(self.living_queue.entries)
        )
        reason = ""
        if 0 <= index < len(self.living_queue.entries):
            reason = self._queue_reasons.get(
                queue_track_key(self.living_queue.entries[index].track), ""
            )
        self.queue_reason_label.setText(
            f"Why this track: {reason}"
            if reason
            else "Select an upcoming track to see why it was chosen."
        )

    def _queue_toggle_keep(self):
        index = self.queue_list.currentRow()
        if index <= self._queue_index or index >= len(self.living_queue.entries):
            return
        entry = self.living_queue.entries[index]
        if self.living_queue.pin(index, not entry.pinned):
            self.on_queue_changed(self._queue, self._queue_index)
            self.queue_list.setCurrentRow(index)

    def _queue_toggle_lock(self):
        index = self.queue_list.currentRow()
        if index <= self._queue_index or index >= len(self.living_queue.entries):
            return
        entry = self.living_queue.entries[index]
        if self.living_queue.set_locked(index, not entry.locked):
            self.on_queue_changed(self._queue, self._queue_index)
            self.queue_list.setCurrentRow(index)

    def _queue_lock_next(self):
        changed = self.living_queue.lock_next(3)
        if changed:
            selected = self.queue_list.currentRow()
            self.on_queue_changed(self._queue, self._queue_index)
            if selected >= 0:
                self.queue_list.setCurrentRow(selected)

    def _queue_undo_replan(self):
        if not self.living_queue.undo_replan():
            return
        start = max(0, self._queue_index + 1)
        self.replaceUpcomingRequested.emit(self.living_queue.tracks()[start:])
        self._update_queue_edit_buttons()

    def _queue_remove_selected(self):
        index = self.queue_list.currentRow()
        if self.living_queue.can_remove(index):
            self.removeQueueItemRequested.emit(index)

    def _queue_move_selected(self, direction: int):
        source = self.queue_list.currentRow()
        target = source + int(direction)
        if self.living_queue.can_move(source, target):
            self.moveQueueItemRequested.emit(source, target)

    def _queue_more_like_selected(self):
        index = self.queue_list.currentRow()
        if not (0 <= index < len(self.living_queue.entries)):
            return
        self.moreLikeRequested.emit(
            dict(self.living_queue.entries[index].track),
            index,
        )

    def keep_queue_track(self, index: int) -> None:
        index = int(index)
        if self.living_queue.pin(index, True):
            self.on_queue_changed(self._queue, self._queue_index)
            self.queue_list.setCurrentRow(index)

    def _queue_apply_steer(self):
        steering = str(self.queue_steering.currentData() or "")
        if not steering:
            self._status("Choose a direction for the live journey first", 3000)
            return
        self.steerJourneyRequested.emit(steering)
        self.queue_steering.setCurrentIndex(0)

    def _queue_toward_artist_selected(self):
        index = self.queue_list.currentRow()
        if 0 <= index < len(self.living_queue.entries):
            self.towardArtistRequested.emit(
                dict(self.living_queue.entries[index].track)
            )

    def _queue_toward_region_selected(self):
        index = self.queue_list.currentRow()
        if 0 <= index < len(self.living_queue.entries):
            self.towardRegionRequested.emit(
                dict(self.living_queue.entries[index].track)
            )

    # ------------------------------- LLM

    def _translate_lyrics(self, payload: dict[str, Any]) -> None:
        from .llm_bridge import LLMClient

        payload = dict(payload or {})
        text = str(payload.get("text") or "").strip()
        if not text:
            return

        settings = self._llm_settings_getter()
        if not str(settings.model or "").strip():
            answer = QMessageBox.question(
                self._dialog_parent(),
                "Connect an LLM",
                "Lyrics translation uses your optional configured LLM. "
                "No model is configured yet. Open LLM settings now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                return
            self._open_llm_settings()
            settings = self._llm_settings_getter()
            if not str(settings.model or "").strip():
                return

        target, ok = QInputDialog.getText(
            self._dialog_parent(),
            "Translate lyrics",
            "Translate into:",
            text=self.state.get_text("lyrics_translation_language", "English"),
        )
        target = str(target or "").strip()
        if not ok or not target:
            return

        endpoint = str(settings.endpoint or LLMClient.default_endpoint(settings.provider))
        answer = QMessageBox.question(
            self._dialog_parent(),
            "Send lyrics for translation?",
            "This sends the currently displayed lyric text to your configured LLM "
            f"endpoint for this one request:\n\n{endpoint}\n\n"
            "The translation is shown temporarily in Melodex and is not saved.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.state.set_text("lyrics_translation_language", target)
        artist = str(payload.get("artist") or "")
        title = str(payload.get("title") or "")
        prompt = (
            f"Translate the following song lyrics into {target}. "
            "Preserve the original line breaks and stanza structure. "
            "Return only the translation, with no commentary, analysis, title or quotation marks."
            f"\n\nTrack: {artist} — {title}\n\n{text}"
        )
        self._status(f"Translating lyrics into {target}…")
        self._run_async(
            lambda: self._llm_complete(settings, prompt, {}, []),
            lambda result: self._show_lyrics_translation(target, str(result or "")),
            priority="foreground",
            task_name="lyrics-translate",
        )

    def _show_lyrics_translation(self, language: str, text: str) -> None:
        dialog = QDialog(self._dialog_parent())
        dialog.setWindowTitle(f"Lyrics translation · {language}")
        dialog.resize(760, 720)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)

        note = QLabel(
            f"<b>Temporary translation · {_escape_html(language)}</b><br>"
            "<span style='color:#8f9bad'>Generated by your configured LLM. "
            "This translation is not saved by Melodex.</span>"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        browser = QTextEdit()
        browser.setReadOnly(True)
        browser.setPlainText(str(text or "").strip())
        layout.addWidget(browser, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.accept)
        layout.addWidget(buttons)
        self._status(f"Lyrics translated into {language}", 4000)
        dialog.exec()

    def _remember_now_playing_knowledge(self, track, bundle):
        from .music_knowledge import build_knowledge_graph

        if not isinstance(track, dict) or not isinstance(bundle, dict):
            return
        kwargs = {}
        if isinstance(bundle.get("identity"), dict):
            kwargs["identity"] = dict(bundle.get("identity") or {})
        if isinstance(bundle.get("artist"), dict):
            kwargs["artist"] = dict(bundle.get("artist") or {})
        if "credits" in bundle:
            kwargs["credits"] = [
                dict(x) for x in list(bundle.get("credits") or []) if isinstance(x, dict)
            ]
        if "context" in bundle:
            kwargs["context"] = [
                dict(x) for x in list(bundle.get("context") or []) if isinstance(x, dict)
            ]
        if kwargs:
            self.knowledge.remember(dict(track), **kwargs)
            self.knowledgeChanged.emit()
