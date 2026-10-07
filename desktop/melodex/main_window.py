Warning: truncated output (original token count: 51547)
Total output lines: 4705

from __future__ import annotations

import json
import os
import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QSettings, QSize, Qt, QTimer, Signal, Slot, QObject
from PySide6.QtGui import QAction, QColor, QDesktopServices, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QStackedWidget, QLineEdit, QComboBox, QFileDialog, QMessageBox,
    QSlider, QTextEdit, QInputDialog, QDialog, QFormLayout, QDialogButtonBox, QCheckBox,
    QTabWidget, QApplication, QPlainTextEdit, QFrame, QProgressBar,
)

from .paths import app_data_dir
from .window_geometry import contained_window_geometry
from .provider_manager import ProviderManager
from .flow import FlowEngine
from .user_state import UserState
from .player import FlowPlayer
from .bridge_server import ProviderBridge
from .responsiveness import UiResponsivenessMonitor
from .background_scheduler import BackgroundScheduler
from .motion import MotionController, FAST_MOTION_MS, STANDARD_MOTION_MS
from .library_scan_controller import LibraryScanController
from .first_music_metrics import FirstMusicTimeline
from .first_play_policy import light_shuffle
from .navigation_controller import NavigationController
from .source_policy_controller import SourcePolicyController
from .sources_feature import SourcesFeature
from .providers.local_files import AUDIO_EXTS
from .library_scan_status import (
    idle_scan_session,
    scan_activity_state,
    scan_change_suffix,
    scan_progress_message,
    scan_progress_patch,
    scan_roots_key,
    start_scan_session,
)
from .ux_components import (
    ActionCard,
    CommandPaletteDialog,
    CoverLabel,
    EmptyState,
    FeaturePresenceBar,
    set_help,
)
class _ViewportStack(QStackedWidget):
    """Page container that never exports feature-page minima to MainWindow."""

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)


class _UiCallbackDispatcher(QObject):
    """Long-lived queued bridge from worker threads back to the Qt UI thread.

    Per-task QObject signal bridges are unsafe here: a worker can finish and
    release its final Python reference while Qt still has a queued MetaCall
    event waiting for that wrapper. Keeping one QApplication-owned dispatcher
    alive for the process lifetime removes that use-after-free window.
    """

    invoke = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.invoke.connect(self._invoke, Qt.QueuedConnection)

    @Slot(object)
    def _invoke(self, callback) -> None:
        callback()


def _escape_html(value: Any) -> str:
    import html
    return html.escape(str(value or ""))


def _track_text(t: dict[str, Any]) -> str:
    artist = str(t.get("artist") or "Unknown artist")
    title = str(t.get("title") or "Unknown track")
    source = str(t.get("provider_id") or "")
    return f"{artist} — {title}" + (f"   ·   {source}" if source else "")


class MainWindow(QMainWindow):
    externalCommand = Signal(str, object, object)

    def _startup_mark(self, phase: str) -> None:
        timeline = getattr(self, "_startup_timeline", None)
        if timeline is not None:
            timeline.mark(phase)

    @property
    def mind(self):
        if self._mind is None:
            from .mind import MindEngine

            self._mind = MindEngine(self.state, self.flow)
            self._startup_mark("lazy_service:mind")
        return self._mind

    @property
    def local_intelligence(self):
        if self._local_intelligence is None:
            from .local_intelligence import LocalIntelligenceService

            self._local_intelligence = LocalIntelligenceService(
                self.state,
                self.flow,
                self.providers.capabilities,
            )
            self._startup_mark("lazy_service:local_intelligence")
        return self._local_intelligence

    @property
    def knowledge(self):
        if self._knowledge is None:
            from .music_knowledge import MusicKnowledgeStore

            self._knowledge = MusicKnowledgeStore(
                self.data_dir / "music-knowledge.sqlite3"
            )
            self._startup_mark("lazy_service:music_knowledge")
        return self._knowledge

    @property
    def llm(self):
        if self._llm is None:
            from .llm_bridge import LLMClient

            self._llm = LLMClient()
            self._startup_mark("lazy_service:llm")
        return self._llm

    @property
    def metadata(self):
        if self._metadata is None:
            from .metadata import RichMetadataService

            self._metadata = RichMetadataService(
                self.data_dir,
                capability_broker=self.providers.capabilities,
            )
            self._startup_mark("lazy_service:metadata")
        return self._metadata

    def __init__(self, *, startup_timeline=None, first_music_timeline=None):
        super().__init__()
        self._startup_timeline = startup_timeline
        self._first_music_timeline = first_music_timeline or FirstMusicTimeline()
        self._first_music_timeline.mark("window_created")
        self._first_music_scan_started = False
        self._first_music_scan_source_id: int | None = None
        self._progressive_local_tracks: list[dict[str, Any]] = []
        self._progressive_track_index: dict[str, int] = {}
        self._progressive_track_revision = 0
        self._progressive_browser_revision = -1
        self._shuffle_discovered_active = False
        self._shuffle_discovered_ids: tuple[str, ...] = ()
        self._first_discovery_preview_queue = False
        self._restored_playback_queue = False
        self._startup_mark("main_window_init_enter")
        self.setWindowTitle("Melodex")
        self.setAcceptDrops(True)
        self._window_settings = QSettings("Melodex", "Melodex")
        saved_geometry = self._window_settings.value("window/geometry")
        trusted_normal_geometry = self._window_settings.contains(
            "window/normal_geometry_trusted"
        )
        restored_geometry = bool(
            saved_geometry and self.restoreGeometry(saved_geometry)
        )
        if restored_geometry and not self.isMaximized() and not self.isFullScreen():
            available = [
                screen.availableGeometry()
                for screen in QApplication.screens()
            ]
            contained = contained_window_geometry(
                self.geometry(),
                available,
                edge_inset=24,
                recover_legacy_full_height=not trusted_normal_geometry,
            )
            if contained != self.geometry():
                self.setGeometry(contained)
        elif not restored_geometry:
            screen = QApplication.primaryScreen()
            available = screen.availableGeometry() if screen else None
            if available is not None:
                width = min(1280, max(1, int(available.width() * 0.94)))
                height = min(800, max(1, int(available.height() * 0.90)))
                self.resize(width, height)
                self.move(
                    available.x() + (available.width() - width) // 2,
                    available.y() + (available.height() - height) // 2,
                )
            else:
                self.resize(1100, 700)
        self.data_dir = app_data_dir()
        self.providers = ProviderManager(
            self.data_dir,
            startup_timeline=self._startup_timeline,
            defer_optional_plugins=True,
        )
        self._startup_mark("providers_ready")
        self.source_policy = SourcePolicyController(self.providers)
        self.state = UserState(self.data_dir / "taste.sqlite3")
        self._startup_mark("user_state_ready")
        self.motion = MotionController(
            self,
            reduced=self.state.get_bool("reduce_motion", False),
        )
        self.page_titles: dict[str, QLabel] = {}
        self.flow = FlowEngine(self.data_dir / "flow.sqlite3")
        # Cold launch only constructs services needed to render Home and play
        # audio.  Intelligence, metadata/network enrichment and the optional
        # LLM are instantiated on first real use.
        self._mind = None
        self._local_intelligence = None
        self._knowledge = None
        self._llm = None
        self._metadata = None
        self._startup_mark("core_services_ready")
        self.bridge: ProviderBridge | None = None
        self._bridge_start_pending = False
        self.current_page = "home"
        self._closing = False
        self._local_scan_started_at = 0.0
        self._local_scan_last_progress: dict[str, Any] = {}
        self._local_scan_session: dict[str, Any] = idle_scan_session()
        self.local_scan = LibraryScanController(self.data_dir, self)
        self.local_scan.progress.connect(self._local_scan_progress)
        self.local_scan.done.connect(self._local_scan_done)
        self.local_scan.failed.connect(self._local_scan_failed)
        self.navigation = NavigationController(
            self,
            refresh_delay_ms=16,
            settle_duration_ms=FAST_MOTION_MS,
            schedule=QTimer.singleShot,
        )
        # Compatibility aliases for focused GUI probes. The controller owns
        # these mutable collections and timing values.
        self._page_refresh_delay_ms = self.navigation.refresh_delay_ms
        self._built_lazy_pages = self.navigation.built_lazy_pages
        self.lazy_page_build_metrics = self.navigation.lazy_page_build_metrics
        self._search_sequence = 0
        self._search_pending_sequence = 0
        self._search_loading_delay_ms = 220
        self.background_scheduler = BackgroundScheduler(
            max_workers=4,
            reserved_foreground_slots=1,
        )
        # Parent the dispatcher to QApplication rather than MainWindow so
        # in-flight workers can safely post a final completion after the
        # window has begun closing. The callback itself observes _closing and
        # becomes a no-op.
        self._ui_callback_dispatcher = _UiCallbackDispatcher(
            QApplication.instance()
        )
        self._async_closing_event = threading.Event()
        self._async_generations: dict[str, int] = {}
        self._async_invalidations = 0
        self._async_stale_results_dropped = 0
        self._local_cache_hydration_pending = False
        self._optional_plugins_loading = False
        self.externalCommand.connect(self._on_external_command)

        self.player = FlowPlayer(
            self.providers.resolve, self._transition_for, self,
            playback_refresher=self.providers.refresh_playback,
            transition_submit=self.background_scheduler.submit,
            first_music_timeline=self._first_music_timeline,
        )
        from .playback_feature import PlaybackFeature

        self.playback_feature = PlaybackFeature(
            self.providers,
            self.state,
            self.flow,
            self.data_dir,
            metadata=lambda: self.metadata,
            knowledge=lambda: self.knowledge,
            llm_settings=lambda: self._llm_settings(),
            open_llm_settings=lambda: self._llm_settings_dialog(),
            llm_complete=lambda settings, prompt, context, tools:
                self.llm.complete(settings, prompt, context, tools),
            run_async=lambda *args, **kwargs: self._run_async(*args, **kwargs),
            invalidate_async=lambda scope: self._invalidate_async(scope),
            is_closing=lambda: self._closing,
            scan_active=lambda: self.local_scan.active,
            power_tools_enabled=lambda: self.state.get_bool("power_tools", False),
            motion=self.motion,
            page_titles=self.page_titles,
        )
        self.player.trackChanged.connect(self.playback_feature.on_track_changed)
        self.player.audioProcessingChanged.connect(
            self.playback_feature.on_audio_processing_changed
        )
        self.playback_feature.on_audio_processing_changed(
            self.player.audio_processing_snapshot()
        )
        self.player.positionChanged.connect(self.playback_feature.on_position)
        self.player.playingChanged.connect(self.playback_feature.on_playing_changed)
        self.player.queueChanged.connect(
            lambda queue: self.playback_feature.on_queue_changed(
                queue, self.player.index
            )
        )
        saved_queue = self.state.playback_queue()
        if saved_queue:
            self._restored_playback_queue = True
            self.player.set_queue(
                list(saved_queue["tracks"]),
                int(saved_queue["queue_index"]),
                False,
                intent="manual_queue",
            )
        self.player.queueChanged.connect(self._persist_playback_queue_async)
        self.player.error.connect(
            lambda message: self.statusBar().showMessage(message, 7000)
        )
        self.playback_feature.previousRequested.connect(self.player.previous)
        self.playback_feature.playPauseRequested.connect(self.player.play_pause)
        self.playback_feature.nextRequested.connect(self.player.next)
        self.playback_feature.seekRequested.connect(self.player.seek)
        self.playback_feature.setQueueRequested.connect(
            self._set_queue_from_playback_feature
        )
        self.playback_feature.appendQueueRequested.connect(
            lambda tracks, autoplay: self.player.append_queue(
                list(tracks or []), bool(autoplay)
            )
        )
        self.playback_feature.jumpQueueRequested.connect(
            lambda index: self.player.jump_to(int(index), autoplay=True)
        )
        self.playback_feature.replaceQueueItemRequested.connect(
            lambda index, track, autoplay: self.player.replace_queue_item(
                int(index), dict(track or {}), autoplay=bool(autoplay)
            )
        )
        self.playback_feature.currentTrackChanged.connect(
            self._playback_current_track_changed
        )
        self.playback_feature.currentTrackChanged.connect(
            self._checkpoint_track_changed
        )
        self.player.playingChanged.connect(self._checkpoint_playing_changed)
        self.player.positionChanged.connect(self._checkpoint_position_changed)
        self._checkpoint_position_ms = 0
        self._checkpoint_timer = QTimer(self)
        self._checkpoint_timer.setInterval(5000)
        self._checkpoint_timer.timeout.connect(self._persist_playback_checkpoint)
        self._checkpoint_timer.start()
        self._checkpoint_track_started = False
        self.playback_feature.knowledgeChanged.connect(
            self._playback_knowledge_changed
        )
        self.playback_feature.statusMessageRequested.connect(
            lambda message, timeout: self.statusBar().showMessage(message, timeout)
        )
        self._startup_mark("player_ready")

        self._build_ui()
        self._startup_mark("ui_built")
        self.responsiveness = UiResponsivenessMonitor(self)
        self.responsiveness.start()
        self.responsiveness.mark_action("startup:home")
        self._show_home()
        self._startup_mark("home_ready")
        # The local AI/control bridge is useful, but it is not part of the
        # first-screen contract. Some platform networking stacks can block
        # socket setup for many seconds, so never bind it on the Qt UI thread.
        self.responsiveness.mark_action("startup:bridge")
        self._startup_mark("bridge_start_scheduled")
        self._start_local_bridge()
        # Optional integrations can require package inspection, extraction or
        # descriptor parsing. Start them only after the player and shell exist.
        QTimer.singleShot(250, self._start_optional_plugin_loading)
        startup_roots=self.providers.local_roots()
        if startup_roots and not self.providers.local_index_ready(startup_roots):
            # One-time migration for existing users who have configured roots
            # but no persistent index yet.
            QTimer.singleShot(0, lambda: self._start_local_scan("initial index"))
        elif startup_roots and int(self.providers.local_catalog_count() or 0):
            roots_snapshot = [Path(root) for root in startup_roots]
            self._start_local_cache_hydration(roots_snapshot)
            # Restore cached rows first. Reconnect/verify and delta scan only
            # after the shell has been on screen for a moment.
            QTimer.singleShot(
                1200, lambda: self._start_local_scan("background refresh")
            )
        self._startup_mark("main_window_init_ready")

    def _start_local_cache_hydration(self, roots: list[Path]) -> None:
        if self._local_cache_hydration_pending or self.providers.local_catalog_is_loaded():
            return
        if not self.providers.local_catalog_count():
            return
        self._local_cache_hydration_pending = True
        roots_snapshot = [Path(root) for root in roots]
        source_status_snapshot = self.state.source_statuses()
        self._run_async(
            lambda: self._load_warm_catalog_cache(
                roots_snapshot, source_status_snapshot
            ),
            lambda result: self._apply_warm_catalog_cache(roots_snapshot, result),
            lambda error: self._warm_catalog_cache_failed(roots_snapshot, error),
            priority="visible",
            task_name="warm-local-catalog-cache",
            replace_key="warm-local-catalog-cache",
        )

    def _start_optional_plugin_loading(self) -> None:
        if (
            self._closing
            or self.providers.optional_plugins_loaded
            or self._optional_plugins_loading
        ):
            return
        self._optional_plugins_loading = True

        def apply(snapshot: object) -> None:
            self._optional_plugins_loading = False
            if not isinstance(snapshot, dict):
                return
            self.providers.apply_optional_plugins_snapshot(snapshot)
            self._refresh_plugin_presence()
            self._refresh_source_combo()
            if self.current_page == "sources" and hasattr(self, "sources_feature"):
                self.sources_feature.refresh()
                self.sources_feature.refresh_config_statuses_async()

        def failed(error: str) -> None:
            self._optional_plugins_loading = False
            self.statusBar().showMessage(
                f"Optional music sources are still unavailable: {error}", 6000
            )

        self._run_async(
            self.providers.load_optional_plugins_snapshot,
            apply,
            failed,
            priority="background",
            task_name="optional-plugin-startup",
            replace_key="optional-plugin-startup",
        )

    def _load_warm_catalog_cache(
        self,
        roots: list[Path],
        stored: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        availability: dict[str, str] = {}
        for root in roots:
            previous = str(
                dict(stored.get(str(root)) or {}).get("status") or ""
            )
            availability[str(root)] = (
                previous if previous in {"unavailable", "degraded"} else "cached"
            )
        tracks = self.providers.load_indexed_local_tracks(
            roots, source_availability=availability
        )
        return {"tracks": tracks, "availability": availability}

    def _apply_warm_catalog_cache(
        self, roots: list[Path], result: object
    ) -> None:
        self._local_cache_hydration_pending = False
        if self._closing:
            return
        if not isinstance(result, dict) or not isinstance(result.get("tracks"), list):
            self._warm_catalog_cache_failed(roots, "invalid cache snapshot")
            return
        current_roots = self.providers.local_roots()
        if current_roots != roots:
            return
        tracks = list(result["tracks"])
        availability = dict(result.get("availability") or {})
        self.providers.hydrate_local_catalog_cache(tracks, roots)
        if self.providers.local_catalog_is_loaded():
            self._first_music_timeline.mark("library_cache_visible")
            for root in roots:
                self.providers.set_local_source_availability(
                    root,
                    str(availability.get(str(root)) or "cached"),
                    update_tracks=False,
                )
            if hasattr(self, "library_browser"):
                self.library_browser.set_cache_restoring(False)
            if self.current_page == "library":
                self._refresh_library()

    def _warm_catalog_cache_failed(self, roots: list[Path], error: str) -> None:
        self._local_cache_hydration_pending = False
        if self._closing or self.providers.local_roots() != roots:
            return
        if self.providers.local_catalog_is_loaded():
            if self.current_page == "library":
                self._refresh_library()
            return
        if self.current_page == "library" and hasattr(self, "library_browser"):
            self.library_browser.set_cache_restoring(False, failed=True)
            self.statusBar().showMessage(
                "Could not restore cached music · playback remains available", 6000
            )

    def _checkpoint_track_changed(self, track: object) -> None:
        row = dict(track or {}) if isinstance(track, dict) else {}
        if not row:
            return
        self._checkpoint_position_ms = 0
        self._checkpoint_track = row
        self._checkpoint_track_started = False

    def _checkpoint_playing_changed(self, playing: bool) -> None:
        if playing:
            self._checkpoint_track_started = True
            self._persist_playback_checkpoint()

    def _checkpoint_position_changed(self, position_ms: int, _duration_ms: int) -> None:
        self._checkpoint_position_ms = max(0, int(position_ms))

    def _persist_playback_checkpoint(self, *, synchronous: bool = False) -> None:
        if self._closing:
            return
        if not getattr(self, "_checkpoint_track_started", False):
            return
        track = dict(
            self.playback_feature.current_track()
            or getattr(self, "_checkpoint_track", {})
            or {}
        )
        if track:
            position_ms = self._checkpoint_position_ms
            if synchronous:
                self.state.save_playback_checkpoint(track, position_ms)
                return
            self._run_async(
                lambda: self.state.save_playback_checkpoint(track, position_ms),
                lambda _result: None,
                lambda _error: None,
                priority="background",
                task_name="playback-checkpoint",
                replace_key="playback-checkpoint",
            )

    def _persist_playback_queue_async(self, tracks: object) -> None:
        if self._closing or not isinstance(tracks, list):
            return
        snapshot = [dict(row) for row in tracks[:5000] if isinstance(row, dict)]
        queue_index = int(self.player.index)
        self._run_async(
            lambda: self.state.save_playback_queue(snapshot, queue_index),
            lambda _result: None,
            lambda _error: None,
            priority="background",
            task_name="playback-queue-save",
            replace_key="playback-queue-save",
        )

    def _playback_current_track_changed(self, track: object) -> None:
        row = dict(track or {}) if isinstance(track, dict) else {}
        if not row:
            return
        if hasattr(self, "journey_workspace"):
            self.journey_workspace.on_track_changed(row)
        if hasattr(self, "album_wall"):
            self.album_wall.highlight_track(row)
        if self.current_page == "home":
            self._refresh_home_continue()

    def _playback_knowledge_changed(self) -> None:
        if (
            self.current_page == "music_map"
            and hasattr(self, "journey_workspace")
        ):
            self.journey_workspace.refresh_knowledge_graph()

    # ------------------------------- UI
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QWidget()
        body_l = QHBoxLayout(body)
        body_l.setContentsMargins(0, 0, 0, 0)
        body_l.setSpacing(0)
        outer.addWidget(body, 1)

        # ------------------------------------------------------------------
        # Navigation: user goals first. Advanced tools remain reachable
        # contextually and through Power tools rather than owning the sidebar.
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(206)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(14, 16, 14, 13)
        side.setSpacing(3)

        brand = QHBoxLayout()
        brand.setSpacing(9)
        mark = QLabel()
        mark_path = Path(__file__).resolve().parent / "assets" / "melodex-mark.png"
        pixmap = QPixmap(str(mark_path))
        if not pixmap.isNull():
            mark.setPixmap(
                pixmap.scaled(38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        mark.setFixedSize(40, 40)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        logo = QLabel("MELODEX")
        logo.setObjectName("brandName")
        tagline = QLabel("Don't shuffle. Flow.")
        tagline.setObjectName("brandTagline")
        titles.addWidget(logo)
        titles.addWidget(tagline)
        brand.addWidget(mark)
        brand.addLayout(titles, 1)
        side.addLayout(brand)
        side.addSpacing(14)

        self.nav_buttons: dict[str, QPushButton] = {}

        def add_nav(label: str, page: str) -> QPushButton:
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCursor(Qt.PointingHandCursor)
            button.setProperty("active", False)
            button.clicked.connect(lambda _checked=False, target=page: self.open_page(target))
            self.nav_buttons[page] = button
            side.addWidget(button)
            return button

        add_nav("Home", "home")
        add_nav("My Music", "library")
        add_nav("Explore", "explore")
        add_nav("Journeys", "journeys")
        add_nav("Playlists", "playlists")

        side.addStretch(1)

        sources_nav = add_nav("Sources && plugins", "sources")
        sources_nav.setObjectName("navUtilityButton")
        set_help(
            sources_nav,
            "Sources & plugins",
            "Choose where Melodex can find music. Everyday controls stay simple; technical provider controls appear when Power tools are enabled.",
        )

        self.power_toggle = QCheckBox("Power tools")
        self.power_toggle.setObjectName("powerToggle")
        self.power_toggle.setChecked(self.state.get_bool("power_tools", False))
        self.power_toggle.stateChanged.connect(self._power_changed)
        set_help(
            self.power_toggle,
            "Power tools",
            "Reveal provider diagnostics, routing controls and other expert features. Turning this off hides complexity; it does not remove or reset anything.",
        )
        side.addWidget(self.power_toggle)
        body_l.addWidget(self.sidebar)

        self.stack = _ViewportStack()
        body_l.addWidget(self.stack, 1)
        self.pages: dict[str, QWidget] = {}

        from .journey_workspace import JourneyWorkspace

        self.journey_workspace = JourneyWorkspace(
            self.providers,
            self.state,
            self.flow,
            local_intelligence=lambda: self.local_intelligence,
            knowledge=lambda: self.knowledge,
            metadata=lambda: self.metadata,
            run_async=self._run_async,
            current_track=self.playback_feature.current_track,
            page_titles=self.page_titles,
        )
        self.journey_workspace.navigationRequested.connect(self.open_page)
        self.journey_workspace.playTracksRequested.connect(
            lambda tracks:self.player.set_queue(list(tracks or []),0,True,intent="journey")
        )
        self.journey_workspace.queueTracksRequested.connect(
            lambda tracks:self.player.append_queue(list(tracks or []),autoplay=False,intent="journey")
        )
        self.journey_workspace.replaceUpcomingRequested.connect(
            lambda tracks: self.player.replace_upcoming(list(tracks or []))
        )
        self.journey_workspace.nextTrackRequested.connect(self.player.next)
        self.journey_workspace.sessionFromTrackRequested.connect(
            self._start_session_from_map_track
        )
        self.journey_workspace.statusMessageRequested.connect(
            lambda message, timeout: self.statusBar().showMessage(message, timeout)
        )
        self.player.manualAdvanced.connect(self.journey_workspace.on_manual_advance)
        for name in [
            "home",
            "library",
            "explore",
            "now_playing",
            "for_you",
            "discover",
            "album_wall",
            "music_map",
            "journeys",
            "playlists",
            "moments",
            "ask",
        ]:
            if name == "now_playing":
                page = self.playback_feature.now_playing_page
            elif name in self.journey_workspace.pages:
                page = self.journey_workspace.pages[name]
            else:
                page = QWidget()
            self.pages[name] = page
            self.stack.addWidget(page)

        self.sources_feature = SourcesFeature(
            self.providers,
            self.source_policy,
            self.state,
            run_async=self._run_async,
            diagnostics_metrics=self._diagnostics_ui_metrics,
            is_active=lambda: not self._closing and self.current_page == "sources",
            power_tools_enabled=self.power_toggle.isChecked(),
            parent=self,
        )
        self.sources_feature.musicFolderRequested.connect(self._choose_music_folder)
        self.sources_feature.providerSearchRequested.connect(self._open_provider_search)
        self.sources_feature.extensionUseRequested.connect(self._use_extension)
        self.sources_feature.bridgeRequested.connect(self._bridge_dialog)
        self.sources_feature.pluginPresenceChanged.connect(self._refresh_plugin_presence)
        self.sources_feature.sourceCatalogChanged.connect(self._refresh_source_combo)
        self.sources_feature.actionMarked.connect(
            lambda action: self.responsiveness.mark_action(action)
            if hasattr(self, "responsiveness")
            else None
        )
        self.sources_feature.statusMessageRequested.connect(
            lambda message, timeout: self.statusBar().showMessage(message, timeout)
        )
        self.playback_feature.pluginDirectoryRequested.connect(
            self.sources_feature.open_plugin_directory
        )
        self.pages["sources"] = self.sources_feature
        self.stack.addWidget(self.sources_feature)
        self.page_titles["sources"] = self.sources_feature.title_label

        # Heavy surfaces get only a tiny first-paint shell at startup. Their
        # modules and widgets are constructed on the first navigation to them.
        self.navigation.set_lazy_builders(
            {
                "library": self._build_library,
                "now_playing": self.playback_feature.build_now_playing,
                "album_wall": self._build_album_wall,
                "music_map": self.journey_workspace.build_music_map,
            }
        )
        for page, title, subtitle in (
            ("library", "My Music", "Preparing your collection…"),
            ("now_playing", "Now playing", "Preparing lyrics, artwork and visuals…"),
            ("album_wall", "Album Wall", "Preparing your visual collection…"),
            ("music_map", "Music Map", "Preparing your music landscape…"),
        ):
            self._prepare_lazy_page_shell(page, title, subtitle)

        self._build_home()
        self._build_explore()
        self._build_for_you()
        self._build_discover()
        self._build_playlists()
        self._build_moments()
        self._build_ask()

        # Queue is contextual and stays out of the primary navigation.
        body_l.addWidget(self.playback_feature.queue_panel)

        # ------------------------------------------------------------------
        # Long-running background work stays visible without taking over the UI.
        self.background_activity = QFrame()
        self.background_activity.setObjectName("artworkProgressPanel")
        activity_l = QHBoxLayout(self.background_activity)
        activity_l.setContentsMargins(14, 7, 14, 7)
        activity_l.setSpacing(10)

        self.background_activity_label = QLabel("")
        self.background_activity_label.setObjectName("artworkProgressDetail")
        self.background_activity_label.setWordWrap(False)
        activity_l.addWidget(self.background_activity_label, 1)

        self.background_activity_progress = QProgressBar()
        self.background_activity_progress.setFixedWidth(180)
        self.background_activity_progress.setTextVisible(True)
        self.background_activity_progress.setRange(0, 0)
        activity_l.addWidget(self.background_activity_progress)

        self.background_activity_view = QPushButton("View")
        self.background_activity_view.setObjectName("quietButton")
        self.background_activity_view.clicked.connect(
            lambda: self.open_page("library")
        )
        activity_l.addWidget(self.background_activity_view)

        self.background_activity_pause = QPushButton("Pause")
        self.background_activity_pause.setObjectName("quietButton")
        self.background_activity_pause.clicked.connect(
            self._toggle_local_scan_pause
        )
        activity_l.addWidget(self.background_activity_pause)

        self.background_activity_cancel = QPushButton("Cancel")
        self.background_activity_cancel.setObjectName("quietButton")
        self.background_activity_cancel.clicked.connect(
            self._cancel_local_scan
        )
        activity_l.addWidget(self.background_activity_cancel)

        self.background_activity.hide()
        outer.addWidget(self.background_activity)

        self._background_activity_timer = QTimer(self)
        self._background_activity_timer.setInterval(1000)
        self._background_activity_timer.timeout.connect(
            self._refresh_background_scan_activity
        )

        # ------------------------------------------------------------------
        # Persistent playback presentation belongs to PlaybackFeature.
        self.playback_feature.set_open_now_playing_handler(
            lambda: self.open_page("now_playing")
        )
        self.playback_feature.set_power_tools_visible(
            self.power_toggle.isChecked()
        )
        outer.addWidget(self.playback_feature.player_bar)

        # Expert speed: command palette without forcing more controls onto
        # everybody else's screen.
        self.shortcut_palette = QShortcut(QKeySequence("Ctrl+K"), self)
        self.shortcut_palette.activated.connect(self._open_command_palette)
        self.shortcut_palette_mac = QShortcut(QKeySequence("Meta+K"), self)
        self.shortcut_palette_mac.activated.connect(self._open_command_palette)

        self.setStyleSheet("""
            QMainWindow,QWidget{
                background:#0f1116;
                color:#f4f6fa;
                font-family:"SF Pro Text","Segoe UI",Arial;
                font-size:13px;
            }
            QLabel{background:transparent}
            QLabel#pageTitle{font-size:26px;font-weight:720}
            QLabel#pageSubtitle{color:#929eae;font-size:12px;margin-bottom:10px}
            QLabel#pageHint{
                color:#758297;
                margin-top:8px;
            }
            QLabel#heroTitle{
                font-size:20px;
                font-weight:720;
            }
            QLabel#sectionTitle{
                font-size:17px;
                font-weight:700;
                margin-top:12px;
            }
            QLabel#sectionTitleCompact{
                font-size:17px;
                font-weight:700;
            }
            QLabel#panelHeading{
                font-size:15px;
                font-weight:700;
            }
            QLabel#mutedText{color:#98a3b3}
            QLabel#subtleText{
                color:#7f8b9b;
                margin-top:6px;
            }
            QLabel#nowPlayingHeroTitle{font-size:30px;font-weight:750}
            QLabel#nowPlayingHeroArtist{font-size:18px;color:#c8ccd2}
            QLabel#nowPlayingHeroAlbum{font-size:14px;color:#aab0ba}
            QLabel#nowPlayingFacts{color:#8f96a1}
            QLabel#nowPlayingProgress{color:#7eb4ff;font-size:12px}
            QLabel#nowPlayingHeroArt{
                background:#181b20;border:1px solid #303640;border-radius:16px;
                font-size:80px;color:#596270;
            }
            QLabel#nowPlayingArtistPhoto{
                background:#15181d;border:1px solid #303640;border-radius:14px;color:#808894;
            }
            QLabel#nowPlayingArtSource{color:#777f8a;font-size:11px}
            QFrame#nativeLyricsToolbar{background:#0f1822;border:1px solid #26394e;border-radius:10px}
            QLabel#lyricsToolbarLabel{color:#8191a5;font-size:10px;font-weight:700}
            QLabel#lyricsStateBadge{
                background:#182a3d;border:1px solid #31516f;border-radius:8px;padding:3px 7px;
                color:#b9d5f1;font-size:9px;font-weight:700;
            }
            QLabel#lyricsSourceText{color:#7f90a5;font-size:10px;padding:0 3px}
            QTextBrowser#nativeLyricsView{
                background:#101923;color:#edf3fa;border:1px solid #30465e;border-radius:11px;
                padding:20px;selection-background-color:#315f8f;selection-color:#ffffff;
            }
            QLabel#wallSelection{color:#e7ebf2;font-size:13px;padding:4px 2px}
            QLabel#searchStatus{
                color:#98a4b4;
                padding:6px 2px 4px 2px;
                font-size:12px;
            }
            QWidget#sidebar{background:#0a0d12;border-right:1px solid #1e2632}
            QLabel#brandName{font-size:19px;font-weight:760;letter-spacing:1.8px}
            QLabel#brandTagline{color:#717d90;font-size:10px}
            QPushButton#navButton,QPushButton#navUtilityButton{
                background:transparent;border:1px solid transparent;border-radius:9px;
                padding:9px 11px;text-align:left;color:#cfd6e0;
            }
            QPushButton#navButton:hover,QPushButton#navUtilityButton:hover{
                background:#131a24;border-color:#202c3b;color:#f0f3f7;
            }
            QPushButton#navButton[active="true"],QPushButton#navUtilityButton[active="true"]{
                background:#172438;border-color:#294563;color:#ffffff;font-weight:650;
            }
            QPushButton#navUtilityButton{color:#8f9bad}
            QCheckBox#powerToggle{background:transparent;color:#8793a5;padding:8px 9px}
            QPushButton{
                background:#181e28;
                border:1px solid #2a3443;
                border-radius:9px;
                padding:9px 13px;
            }
            QPushButton:hover{
                background:#222b38;
                border-color:#…31547 tokens truncated… != self._search_sequence
            or sequence != self._search_pending_sequence
            or self._closing
        ):
            return
        # Preserve stale-but-useful results while revalidating.
        if self._search_has_useful_results():
            return
        self.results.clear()
        item=QListWidgetItem(f"Searching {target}…")
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        item.setForeground(QColor("#8793a4"))
        self.results.addItem(item)

    def _search(self):
        q=self.search_box.text().strip()
        pid=str(self.search_source.currentData() or "all")
        if not q:
            return

        interaction = (
            self.responsiveness.begin_interaction("discover:search")
            if hasattr(self, "responsiveness")
            else None
        )
        self._search_sequence += 1
        sequence=self._search_sequence
        self._search_pending_sequence=sequence
        had_results=self._search_has_useful_results()

        target=(
            self.search_source.currentText()
            if pid!="all"
            else "your connected sources"
        )
        if hasattr(self,"search_button"):
            self.search_button.setText("Searching…")
            self.search_button.setEnabled(False)
        if hasattr(self,"search_status"):
            if had_results:
                self.search_status.setText(
                    f"Updating {target}… · showing previous results"
                )
            else:
                self.search_status.setText(f"Searching {target}…")
            self.search_status.setToolTip("")

        # Avoid a loading-state flash for fast searches. If useful results are
        # already visible, keep them in place throughout the refresh.
        QTimer.singleShot(
            self._search_loading_delay_ms,
            lambda token=sequence, label=target: self._show_delayed_search_loading(
                token,
                label,
            ),
        )

        if interaction is not None:
            self.responsiveness.end_interaction(interaction)

        self._run_async(
            lambda:self.providers.search_report(q,pid,100),
            lambda report, token=sequence: self._show_search_report(
                report,
                token,
            ),
            lambda error, token=sequence: self._search_report_failed(
                error,
                token,
            ),
        priority="foreground", task_name="search", replace_key="search")

    def _search_report_failed(
        self,
        error: str,
        sequence: int | None = None,
    ) -> None:
        if sequence is not None and sequence != self._search_sequence:
            return
        if sequence is not None and self._search_pending_sequence == sequence:
            self._search_pending_sequence=0
        if hasattr(self,"search_button"):
            self.search_button.setText("Search")
            self.search_button.setEnabled(True)

        if self._search_has_useful_results():
            if hasattr(self,"search_status"):
                self.search_status.setText(
                    "Search refresh failed · showing previous results"
                )
                self.search_status.setToolTip(str(error or ""))
            return

        self.results.clear()
        item=QListWidgetItem("Search could not be completed. Try again in a moment.")
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        item.setForeground(QColor("#d9a441"))
        self.results.addItem(item)
        if hasattr(self,"search_status"):
            self.search_status.setText("Search temporarily unavailable")
            self.search_status.setToolTip(str(error or ""))

    def _show_search_report(
        self,
        report,
        sequence: int | None = None,
    ):
        if sequence is not None and sequence != self._search_sequence:
            return
        if sequence is not None and self._search_pending_sequence == sequence:
            self._search_pending_sequence=0
        if hasattr(self,"search_button"):
            self.search_button.setText("Search")
            self.search_button.setEnabled(True)

        data=dict(report or {})
        tracks=[dict(x) for x in list(data.get("items") or []) if isinstance(x,dict)]
        failures=[dict(x) for x in list(data.get("failures") or []) if isinstance(x,dict)]
        searched=int(data.get("searched") or 0)
        available=int(data.get("available") or 0)

        self.results.clear()
        for t in tracks:
            it=QListWidgetItem(_track_text(t))
            it.setData(Qt.UserRole,t)
            self.results.addItem(it)

        failure_labels=[
            f"{row.get('name') or row.get('provider_id')}: {row.get('reason') or 'Unavailable'}"
            for row in failures
        ]
        technical="\n".join(
            f"{row.get('name') or row.get('provider_id')}: {row.get('error') or row.get('reason') or 'Unavailable'}"
            for row in failures
        )

        if failures:
            shown=failure_labels[:3]
            suffix=f" · +{len(failure_labels)-3} more" if len(failure_labels)>3 else ""
            note=QListWidgetItem(
                "Some sources were unavailable · " + " · ".join(shown) + suffix
            )
            note.setFlags(note.flags() & ~Qt.ItemIsSelectable)
            note.setForeground(QColor("#d9a441"))
            note.setToolTip(technical)
            self.results.addItem(note)

        if not tracks and not failures:
            empty=QListWidgetItem("No matches found. Try a broader search.")
            empty.setFlags(empty.flags() & ~Qt.ItemIsSelectable)
            empty.setForeground(QColor("#8793a4"))
            self.results.addItem(empty)

        if hasattr(self,"search_status"):
            if failures and tracks:
                self.search_status.setText(
                    f"{len(tracks)} results · {available} of {searched} sources responded · "
                    f"{len(failures)} temporarily unavailable"
                )
            elif failures:
                names=", ".join(
                    str(row.get("name") or row.get("provider_id") or "Source")
                    for row in failures[:3]
                )
                more=f" and {len(failures)-3} more" if len(failures)>3 else ""
                self.search_status.setText(
                    f"No results yet · {names}{more} unavailable"
                )
            else:
                source_word="source" if searched==1 else "sources"
                self.search_status.setText(
                    f"{len(tracks)} results · {searched} {source_word} searched"
                )
            self.search_status.setToolTip(technical)

    def _show_results(self, tracks):
        # Kept for older call sites; search itself now uses _show_search_report.
        self._show_search_report(
            {
                "items": list(tracks or []),
                "failures": [],
                "searched": 1,
                "available": 1,
            }
        )

    def _play_result(self,item):
        if hasattr(self, "responsiveness"):
            self.responsiveness.mark_action("discover:play-result")
        t=dict(item.data(Qt.UserRole) or {}); self.player.set_queue([t],0,True,intent="provider")

    def _open_selected_source(self):
        item=self.results.currentItem()
        if not item:return
        t=dict(item.data(Qt.UserRole) or {})
        url=str(t.get("source_page") or "")
        if url: QDesktopServices.openUrl(url)
        else: self.statusBar().showMessage("This source did not provide a content page",3000)

    def _play_library(self,item):
        t = dict(item.data(Qt.UserRole) or {})
        if not t:
            return
        if not self.providers.local_catalog_is_loaded():
            self.player.set_queue([t], 0, True, intent="manual_queue")
            return
        tracks = self.providers.local_catalog()
        idx = next(
            (i for i, row in enumerate(tracks) if row.get("track_id") == t.get("track_id")),
            0,
        )
        self.player.set_queue(tracks, idx, True, intent="manual_queue")

    def _add_selected_to_queue(self):
        item=self.results.currentItem()
        if not item:return
        t=dict(item.data(Qt.UserRole) or {})
        self.player.append_queue([t],autoplay=False)

    # ------------------------------- local intelligence
    def _intelligence_seeds(self, intent: str) -> list[dict[str, Any]]:
        if intent == "rediscover":
            return []
        current = dict(self.playback_feature.current_track() or {})
        if not current or not current.get("local_path"):
            return []
        if intent in {"similar", "detour"}:
            return [current]
        if intent == "bridge":
            idx = self.playback_feature.queue_index()
            queue = self.playback_feature.queue_snapshot()
            if idx < 0 or idx + 1 >= len(queue):
                return []
            nxt = dict(queue[idx + 1] or {})
            if not nxt.get("local_path"):
                return []
            return [current, nxt]
        return []

    def _run_local_intelligence(self, intent: str) -> None:
        catalog = self.providers.local_catalog()
        if not catalog:
            QMessageBox.information(
                self, "Add music first",
                "Local intelligence needs your local library. Add a folder, then try again."
            )
            return
        seeds = self._intelligence_seeds(intent)
        if intent in {"similar", "detour"} and len(seeds) != 1:
            message = (
                "Find a detour needs the current track to be local."
                if intent == "detour"
                else "More like current needs a local track as the seed."
            )
            QMessageBox.information(self, "Play a local track first", message)
            return
        if intent == "bridge" and len(seeds) != 2:
            QMessageBox.information(
                self, "Queue two local tracks",
                "Bridge current → next needs the current track and the next queued track to be local."
            )
            return
        self.intelligence_results.clear()
        self.statusBar().showMessage("Asking local intelligence plugins…")
        adventure = self.adventure.value() / 100.0
        self._run_async(
            lambda: self.local_intelligence.suggest(
                intent, catalog, seeds, limit=16, adventure=adventure
            ),
            self._show_intelligence_results,
        priority="foreground", task_name="local-intelligence", replace_key="local-intelligence")

    def _show_intelligence_results(self, result: dict[str, Any]) -> None:
        self.intelligence_results.clear()
        tracks = [dict(x) for x in list(result.get("tracks") or []) if isinstance(x, dict)]
        for track in tracks:
            reason = str(track.get("_intelligence_reason") or "")
            score = float(track.get("_intelligence_score") or 0.0)
            badges = ", ".join(str(x) for x in list(track.get("_intelligence_badges") or []) if x)
            suffix = " · ".join(x for x in (reason, badges, f"{score:.0%}") if x)
            item = QListWidgetItem(_track_text(track) + (f"\n{suffix}" if suffix else ""))
            item.setData(Qt.UserRole, track)
            self.intelligence_results.addItem(item)
        if tracks:
            self.statusBar().showMessage(
                f"{len(tracks)} local suggestions · {int(result.get('analysed') or 0)} of {int(result.get('profiles') or 0)} profiles have Flow analysis",
                7000,
            )
            return
        errors = [str(x) for x in list(result.get("errors") or []) if x]
        analysed = int(result.get("analysed") or 0)
        if errors:
            message = errors[0]
        elif analysed == 0 and result.get("intent") in {"similar", "bridge", "detour"}:
            message = "No analysed comparison tracks yet. Use ‘Analyse my library’, then try again."
        else:
            message = "No local-intelligence plugin returned suggestions. Install one from Explore plugins."
        self.intelligence_results.addItem(message)
        self.statusBar().showMessage(message, 7000)

    def _selected_intelligence_track(self) -> dict[str, Any]:
        item = self.intelligence_results.currentItem()
        data = item.data(Qt.UserRole) if item else None
        return dict(data) if isinstance(data, dict) else {}

    def _play_intelligence_result(self, item) -> None:
        data = item.data(Qt.UserRole)
        if isinstance(data, dict):
            self.player.set_queue([dict(data)],0,True,intent="manual_queue")

    def _play_selected_intelligence(self) -> None:
        track = self._selected_intelligence_track()
        if track:
            self.player.set_queue([track],0,True,intent="manual_queue")

    def _queue_selected_intelligence(self) -> None:
        track = self._selected_intelligence_track()
        if not track:
            return
        self.player.append_queue([track],autoplay=False)
        self.statusBar().showMessage("Added local-intelligence suggestion to queue", 3000)

    def _analyse_library_for_intelligence(self) -> None:
        catalog = self.providers.local_catalog()
        if not catalog:
            QMessageBox.information(
                self, "Add music first",
                "Add a local music folder before analysing your library."
            )
            return
        if not self.flow.analysis_available:
            QMessageBox.information(
                self, "Audio analysis unavailable",
                "Deep local analysis needs ffmpeg and NumPy. Melodex can still use taste-only rediscovery."
            )
            return
        self.statusBar().showMessage("Analysing local library for Flow and local intelligence…")
        self._run_async(
            lambda: self.local_intelligence.analyse_catalog(catalog),
            self._library_analysis_finished,
        priority="background", task_name="library-analysis")

    def _library_analysis_finished(self, result: dict[str, Any]) -> None:
        self.statusBar().showMessage(
            f"Library analysis ready · {int(result.get('analysed') or 0)}/{int(result.get('total') or 0)} analysed · {int(result.get('newly_analysed') or 0)} new",
            8000,
        )

    # ------------------------------- Music Map
    def _build_album_wall_payload(self):
        from .album_wall_model import build_album_wall
        from .music_map_model import build_music_map

        catalog=self.providers.local_catalog()
        profiles, _seed_refs, ref_map, _analysed = self.local_intelligence.build_snapshot(
            catalog,
            [],
            max_tracks=5000,
            analyse_seeds=False,
        )
        projection=build_music_map(profiles,max_nodes=5000,neighbours=0)
        projected_refs={
            str(node.get("ref") or "")
            for node in list(projection.get("nodes") or [])
            if isinstance(node,dict) and str(node.get("ref") or "")
        }
        projected_ref_map={
            ref:dict(track)
            for ref,track in ref_map.items()
            if ref in projected_refs
        }
        return build_album_wall(
            catalog,
            projection,
            projected_ref_map,
            max_albums=1200,
        )

    def _refresh_album_wall(self):
        catalog=self.providers.local_catalog()
        if not catalog:
            self.album_wall.set_model(
                {}, self.playback_feature.current_track()
            )
            self.statusBar().showMessage("Add local music to build an Album Wall",4000)
            return
        self.statusBar().showMessage("Building Album Wall from local metadata and cached Flow analysis…")
        self._run_async(self._build_album_wall_payload,self._apply_album_wall_payload, priority="visible", task_name="album-wall-model", replace_key="page:album-wall-model")

    def _apply_album_wall_payload(self,payload):
        payload=dict(payload or {})
        self.album_wall.set_model(
            payload, self.playback_feature.current_track()
        )
        albums=int(payload.get("album_count") or 0)
        analysed=int(payload.get("analysed_albums") or 0)
        if analysed:
            message=f"Album Wall ready · {albums} albums · {analysed} positioned from Flow analysis"
        else:
            message=f"Album Wall ready · {albums} albums · analyse your library for sonic neighbourhoods"
        self.statusBar().showMessage(message,6000)

    def _analyse_library_for_album_wall(self):
        catalog=self.providers.local_catalog()
        if not catalog:
            QMessageBox.information(self,"Add music first","Add a local music folder before analysing your Album Wall.")
            return
        if not self.flow.analysis_available:
            QMessageBox.information(
                self,
                "Audio analysis unavailable",
                "Album Wall sonic layout needs ffmpeg and NumPy. The wall still works in metadata mode; install/enable them for sonic neighbourhoods.",
            )
            return
        self.statusBar().showMessage("Analysing local library for Album Wall…")
        self._run_async(
            lambda:self.local_intelligence.analyse_catalog(catalog),
            self._album_wall_analysis_finished,
        priority="background", task_name="album-wall-analysis")

    def _album_wall_analysis_finished(self,result):
        self.statusBar().showMessage(
            f"Album Wall analysis ready · {int(result.get('analysed') or 0)}/{int(result.get('total') or 0)} analysed",
            5000,
        )
        self._refresh_album_wall()

    def _album_wall_selected(self):
        return self.album_wall.selected_album() if hasattr(self,"album_wall") else {}

    def _play_album_wall_album(self,album):
        tracks=[dict(x) for x in list((album or {}).get("tracks") or []) if isinstance(x,dict)]
        if tracks:
            self._shuffle_discovered_active = False
            self._prioritize_tracks(tracks)
            self.player.set_queue(tracks,0,True,intent="album")
            self.statusBar().showMessage(
                f"Playing {album.get('artist') or 'Unknown artist'} — {album.get('title') or 'Unknown album'}",
                4500,
            )

    def _play_album_wall_selected(self):
        album=self._album_wall_selected()
        if album:
            self._play_album_wall_album(album)

    def _queue_album_wall_selected(self):
        album=self._album_wall_selected()
        tracks=[dict(x) for x in list(album.get("tracks") or []) if isinstance(x,dict)] if album else []
        if not tracks:
            self.statusBar().showMessage("Select an album on the wall first",3000)
            return
        if not self.player.queue:
            self.player.set_queue(tracks,0,False,intent="album")
        else:
            self.player.append_queue(tracks,autoplay=False)
        self.statusBar().showMessage(f"Queued {len(tracks)} tracks from {album.get('title') or 'album'}",4000)

    def _album_wall_artwork_requested(self,requests):
        rows=[dict(x) for x in list(requests or []) if isinstance(x,dict)]
        if not rows:return
        prefetch=all(bool(row.get("prefetch")) for row in rows)
        def load():
            result={}
            for row in rows:
                key=str(row.get("key") or ""); track=dict(row.get("track") or {})
                if key and track:
                    path=str(self.metadata.local_artwork(track).get("path") or "")
                    result[key]=self.metadata.prepared_artwork_payload(
                        path,int(row.get("generation") or 0),228
                    )
                    result[key]["prefetch"]=bool(row.get("prefetch"))
            return result
        self._run_async(
            load,
            self.album_wall.set_artwork,
            priority="prefetch" if prefetch else "visible",
            task_name="album-wall-art-prefetch" if prefetch else "album-wall-cached-artwork",
        )

    def _album_wall_online_artwork_requested(self,requests):
        rows=[dict(x) for x in list(requests or []) if isinstance(x,dict)]
        if not rows:return
        def load():
            result={}
            for row in rows:
                key=str(row.get("key") or ""); track=dict(row.get("track") or {})
                if not key or not track:continue
                path=""
                try:
                    local=self.metadata.local_artwork(track); path=str(local.get("path") or "")
                    if not path:
                        identity=self.metadata.identify(track)
                        path=str(self.metadata.artwork(track,identity).get("path") or "")
                except Exception:path=""
                result[key]=self.metadata.prepared_artwork_payload(
                    path,int(row.get("generation") or 0),228
                )
            return result
        self._run_async(load,self.album_wall.set_artwork, priority="background", task_name="album-wall-online-artwork")

    def _start_session_from_map_track(self, track: object) -> None:
        seed = dict(track or {}) if isinstance(track, dict) else {}
        if not seed:
            return
        catalog = self.providers.local_catalog()
        self.statusBar().showMessage("Building a journey from this part of your map…")
        self._run_async(
            lambda: self.mind.build_session(
                catalog,
                self._path_for,
                minutes=int(self.minutes.currentText()),
                adventure=self.adventure.value() / 100,
                mode=str(self.mode.currentData() or "balanced"),
                start_track=seed,
            ),
            lambda plan: self._apply_mind(plan),
            priority="foreground",
            task_name="journey-build",
            replace_key="journey-build",
        )

    # ------------------------------- Flow / Mind
    def _path_for(self,t):
        p=str(t.get("local_path") or ""); return Path(p) if p else None

    def _transition_for(self,a,b):
        aa=self.flow.cached_analysis_for(self._path_for(a)); bb=self.flow.cached_analysis_for(self._path_for(b)); return self.flow.transition(aa,bb).as_dict()

    def _play_for_me(self,mode,minutes,adventure):
        catalog=self.providers.local_catalog()
        if not catalog:
            QMessageBox.information(self,"Add music first","Play for Me needs at least some local music. Add a folder, then try again."); return
        self.statusBar().showMessage("Building your journey…")
        self._run_async(lambda:self.mind.build_session(catalog,self._path_for,minutes=minutes,adventure=adventure,mode=mode),lambda plan:self._apply_mind(plan), priority="foreground", task_name="play-for-me", replace_key="play-for-me")

    def _apply_mind(self,plan):
        tracks=list(plan.get("tracks",[]));
        if tracks:self.player.set_queue(tracks,0,True,intent="journey")
        self.statusBar().showMessage(f"Journey ready · {len(tracks)} tracks · {plan.get('new_to_you',0)} new to you",6000)

    def _llm_settings(self):
        from .llm_bridge import LLMClient, LLMSettings
        return LLMSettings(
            provider=self.state.get_text("llm_provider","openwebui"),
            endpoint=self.state.get_text("llm_endpoint",LLMClient.default_endpoint(self.state.get_text("llm_provider","openwebui"))),
            model=self.state.get_text("llm_model",""), api_key=self.state.get_text("llm_api_key","")
        )

    def _llm_settings_dialog(self):
        from .llm_bridge import LLMClient
        d=QDialog(self); d.setWindowTitle("Connect an LLM"); f=QFormLayout(d)
        provider=QComboBox(); provider.addItems(["openwebui","ollama","openai","custom"]); provider.setCurrentText(self.state.get_text("llm_provider","openwebui"))
        endpoint=QLineEdit(self.state.get_text("llm_endpoint",LLMClient.default_endpoint(provider.currentText()))); model=QLineEdit(self.state.get_text("llm_model","")); key=QLineEdit(self.state.get_text("llm_api_key","")); key.setEchoMode(QLineEdit.Password)
        provider.currentTextChanged.connect(lambda p:endpoint.setText(LLMClient.default_endpoint(p)))
        f.addRow("Provider",provider); f.addRow("Endpoint",endpoint); f.addRow("Model",model); f.addRow("API key",key)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(d.accept); buttons.rejected.connect(d.reject); f.addRow(buttons)
        if d.exec():
            self.state.set_text("llm_provider",provider.currentText()); self.state.set_text("llm_endpoint",endpoint.text().strip()); self.state.set_text("llm_model",model.text().strip()); self.state.set_text("llm_api_key",key.text().strip())

    def _llm_context(self):
        from .llm_bridge import llm_track_summary
        queue = (
            self.player.queue[self.player.index:self.player.index + 12]
            if self.player.index >= 0
            else []
        )
        return {
            "current_track": llm_track_summary(
                self.playback_feature.current_track()
            ),
            "queue": [llm_track_summary(track) for track in queue],
            "current_page": self.current_page,
            "taste": self.state.taste_summary(),
            "recent": [
                llm_track_summary(track)
                for track in self.state.recent_tracks(15)
            ],
            "vibes": self.state.vibes(10),
        }

    def _ask(self):
        prompt=self.ask_box.text().strip();
        if not prompt:return
        self.ask_box.clear(); self.chat.append(f"You: {prompt}")
        settings=self._llm_settings(); self._run_async(lambda:self.llm.complete(settings,prompt,self._llm_context(),[]),lambda text:self._handle_llm(text), priority="foreground", task_name="llm-ask")

    def _handle_llm(self,text):
        reply,actions=self.llm.parse_action_response(str(text)); self.chat.append(f"Melodex: {reply}")
        for a in actions:self._execute_action(a)

    def _execute_action(self,a):
        typ=str(a.get("type") or ""); args=dict(a.get("args") or {})
        if typ=="play_for_me":self._play_for_me(args.get("mode","balanced"),int(args.get("minutes",60)),float(args.get("adventure",0.35)))
        elif typ=="search": self.open_page("discover"); self.search_box.setText(str(args.get("query", ""))); self._search()
        elif typ=="play_pause":self.player.play_pause()
        elif typ=="next":self.player.next()
        elif typ=="previous":self.player.previous()
        elif typ=="flow_queue":self.playback_feature.refine_queue()
        elif typ=="save_moment":
            current=self.playback_feature.current_track()
            if current:
                self.state.save_moment(
                    current,
                    self.playback_feature.current_position_ms(),
                    str(args.get("label", "")),
                )
        elif typ=="open_view":self.open_page(str(args.get("view","home")) if str(args.get("view","home")) in self.pages else "home")
        elif typ=="import_playlist":self._import_ai_playlist(args)

    def _import_ai_playlist(self,args,source="llm"):
        requested=[dict(x) for x in list(args.get("tracks") or []) if isinstance(x,dict)]
        if not requested:
            self.statusBar().showMessage("The AI playlist did not contain any tracks",4000); return
        playlist_id=str(uuid.uuid4()); name=str(args.get("name","AI playlist")); description=str(args.get("description",""))
        self.statusBar().showMessage(f"Matching {len(requested)} playlist tracks across your sources…")
        self._run_async(
            lambda:self.providers.resolve_playlist(requested),
            lambda result:self._finish_ai_playlist(playlist_id,name,description,result,requested,source),
        priority="foreground", task_name="ai-playlist-resolve")

    def _finish_ai_playlist(self,playlist_id,name,description,result,requested=None,source="llm"):
        from .playlist_io import save_playlist
        tracks=list(result.get("tracks") or []); unresolved=list(result.get("unresolved") or [])
        payload={"tracks":tracks,"unresolved":unresolved,"requested":int(result.get("requested") or len(tracks)+len(unresolved))}
        if requested is not None:payload["requested_tracks"]=[dict(x) for x in requested]
        self.state.save_playlist(playlist_id,name,description,source,payload); self._refresh_playlists()
        if tracks:self.player.set_queue(tracks,0,True,intent="playlist")
        msg=f"{name}: matched {len(tracks)} track{'s' if len(tracks)!=1 else ''}"
        if unresolved:msg+=f" · {len(unresolved)} unresolved"
        self.statusBar().showMessage(msg,7000)

    # ------------------------------- bridge / external control
    def _control_request(self, action, args):
        event=threading.Event(); box={}
        self.externalCommand.emit(str(action),dict(args or {}),(event,box))
        if not event.wait(12):raise RuntimeError("Melodex GUI did not answer the control request")
        if box.get("error"):raise RuntimeError(str(box["error"]))
        return box.get("result")

    def _on_external_command(self,action,args,reply):
        event,box=reply
        try:
            action=str(action or ""); args=dict(args or {})
            if action=="status":
                result=self.player.status(); result["page"]=self.current_page; result["taste"]=self.state.taste_summary()
            elif action=="set_queue":
                tracks=[dict(x) for x in list(args.get("tracks") or []) if isinstance(x,dict)]; self.player.set_queue(tracks,int(args.get("start",0)),bool(args.get("autoplay",True)),intent=str(args.get("intent") or "manual_queue")); result=self.player.status()
            elif action=="append_queue":
                tracks=[dict(x) for x in list(args.get("tracks") or []) if isinstance(x,dict)]; self.player.append_queue(tracks,bool(args.get("autoplay",False))); result=self.player.status()
            elif action=="play_pause":self.player.play_pause(); result=self.player.status()
            elif action=="next":self.player.next(); result=self.player.status()
            elif action=="previous":self.player.previous(); result=self.player.status()
            elif action=="stop":self.player.stop(); result=self.player.status()
            elif action=="clear_queue":self.player.clear_queue(); result=self.player.status()
            elif action=="seek_ms":self.player.seek(int(args.get("value",0))); result=self.player.status()
            elif action=="set_volume":self.player.set_volume(float(args.get("value",1.0))); result=self.player.status()
            elif action=="flow_queue":
                self.playback_feature.refine_queue()
                result={"started":True,"queue_length":len(self.player.queue)}
            elif action=="love_current":
                current=self.playback_feature.current_track()
                self.playback_feature.record_feedback(True)
                result={"recorded":bool(current)}
            elif action=="dislike_current":
                current=self.playback_feature.current_track()
                self.playback_feature.record_feedback(False)
                result={"recorded":bool(current)}
            elif action=="keep_current":
                current=self.playback_feature.current_track()
                self.playback_feature.keep_current()
                result={"recorded":bool(current)}
            elif action=="save_moment":
                current=self.playback_feature.current_track()
                if current:
                    moment_id=self.state.save_moment(
                        current,
                        self.playback_feature.current_position_ms(),
                        str(args.get("label", "")),
                    )
                    result={"saved":True,"id":moment_id}
                else:
                    result={"saved":False,"reason":"nothing playing"}
            elif action=="open_view":
                view=str(args.get("view","home")); self.open_page(view if view in self.pages else "home"); result={"page":self.current_page}
            else:raise RuntimeError(f"Unsupported control action: {action}")
            box["result"]=result
        except Exception as exc:box["error"]=str(exc)
        finally:event.set()

    def _start_local_bridge(self):
        if self.bridge or self._bridge_start_pending or self._closing:
            return
        self._bridge_start_pending = True

        def create_bridge():
            bridge = ProviderBridge(
                self.providers,
                "127.0.0.1",
                0,
                controller=self._control_request,
                state_path=self.data_dir / "bridge.json",
            )
            bridge.start()
            if self._closing:
                bridge.stop()
                return None
            return bridge

        def bridge_ready(result):
            self._bridge_start_pending = False
            if result is None or self._closing:
                return
            self.bridge = result
            self._startup_mark("bridge_ready")

        def bridge_failed(error: str):
            self._bridge_start_pending = False
            if self._closing:
                return
            self.statusBar().showMessage(
                f"AI control bridge could not start: {error}",
                7000,
            )

        self._run_async(
            create_bridge,
            bridge_ready,
            bridge_failed,
            priority="background",
            task_name="local-control-bridge",
            replace_key="local-control-bridge",
        )

    def _restart_bridge(self,host):
        token=self.bridge.token if self.bridge else ""; port=self.bridge.port if self.bridge else 0
        if self.bridge:self.bridge.stop()
        self.bridge=ProviderBridge(self.providers,host,port,token=token,controller=self._control_request,state_path=self.data_dir/"bridge.json"); self.bridge.start()

    def _bridge_dialog(self):
        if not self.bridge:
            self._start_local_bridge()
            if self._bridge_start_pending:
                self.statusBar().showMessage(
                    "AI control bridge is starting in the background…",
                    3000,
                )
            return
        if self.bridge.host=="127.0.0.1":
            choice=QMessageBox.question(self,"Provider Bridge",f"The private AI control bridge is running locally on port {self.bridge.port}.\n\nAllow phones/computers on your LAN to use the provider bridge too?\n\nChoose No to keep it local-only.",QMessageBox.Yes|QMessageBox.No)
            if choice==QMessageBox.Yes:
                try:self._restart_bridge("0.0.0.0"); QMessageBox.information(self,"Provider Bridge",f"LAN bridge enabled on port {self.bridge.port}.\n\nBearer token:\n{self.bridge.token}\n\nKeep this token private.")
                except Exception as exc:self.statusBar().showMessage(str(exc),7000)
        else:
            choice=QMessageBox.question(self,"Provider Bridge",f"The bridge currently accepts LAN connections on port {self.bridge.port}.\n\nRestrict it to this computer only?",QMessageBox.Yes|QMessageBox.No)
            if choice==QMessageBox.Yes:
                try:self._restart_bridge("127.0.0.1"); self.statusBar().showMessage("Provider bridge restricted to this computer",4000)
                except Exception as exc:self.statusBar().showMessage(str(exc),7000)

    # ------------------------------- helpers
    def _invalidate_async(self, replace_key: str) -> int:
        key = str(replace_key or "").strip()
        if not key:
            return 0
        self._async_generations[key] = self._async_generations.get(key, 0) + 1
        self._async_invalidations += 1
        return self.background_scheduler.cancel_pending(key)

    def _run_async(
        self,
        fn,
        done,
        on_error=None,
        *,
        priority: str = "foreground",
        task_name: str = "",
        replace_key: str = "",
    ):
        scope = str(replace_key or "").strip()
        generation = 0
        if scope:
            generation = self._async_generations.get(scope, 0) + 1
            self._async_generations[scope] = generation

        def is_current() -> bool:
            return (
                not scope
                or self._async_generations.get(scope, 0) == generation
            )

        dispatcher = self._ui_callback_dispatcher
        closing_event = self._async_closing_event

        def deliver_done(result: object) -> None:
            # This check deliberately touches no QObject-backed wrapper. A
            # completion can arrive after Qt has destroyed MainWindow's C++
            # object but while Python closures still retain the wrapper.
            if closing_event.is_set():
                return
            if not is_current():
                self._async_stale_results_dropped += 1
                return
            done(result)

        def deliver_error(error: str) -> None:
            if closing_event.is_set():
                return
            if not is_current():
                self._async_stale_results_dropped += 1
                return
            if on_error is None:
                QMessageBox.warning(self,"Melodex",error)
            else:
                on_error(error)

        def post_to_ui(callback) -> None:
            # A single process-lived QObject owns all queued MetaCall events.
            # Do not create a temporary QObject per task: on macOS/PySide that
            # can leave a posted event pointing at a wrapper that Python has
            # already collected.
            dispatcher.invoke.emit(callback)

        def work():
            try:
                result=fn()
            except Exception as exc:
                error=str(exc)
                post_to_ui(
                    lambda message=error: deliver_error(message)
                )
                raise
            else:
                post_to_ui(
                    lambda value=result: deliver_done(value)
                )

        submitted=self.background_scheduler.submit(
            work,
            priority=priority,
            name=task_name,
            replace_key=scope,
        )
        if not submitted and not closing_event.is_set():
            post_to_ui(
                lambda: deliver_error("Background work is shutting down")
            )

    def closeEvent(self,event):
        self._window_settings.setValue("window/geometry", self.saveGeometry())
        self._window_settings.setValue("window/normal_geometry_trusted", True)
        self._invalidate_async("playback-queue-save")
        self.state.save_playback_queue(
            list(self.player.queue[:5000]),
            int(self.player.index),
        )
        self._persist_playback_checkpoint(synchronous=True)
        if hasattr(self, "_checkpoint_timer"):
            self._checkpoint_timer.stop()
        # Set the plain-Python gate before any Qt-owned children are torn down.
        if hasattr(self, "_async_closing_event"):
            self._async_closing_event.set()
        if hasattr(self, "journey_workspace"):
            self.journey_workspace.shutdown()
        if hasattr(self, "responsiveness"):
            self.responsiveness.stop()
        self._closing = True
        if hasattr(self, "background_scheduler"):
            self.background_scheduler.shutdown(wait=False)
        self.local_scan.shutdown()
        if self.bridge:self.bridge.stop()
        self.player.close()
        if self._metadata is not None:
            self._metadata.close()
        self.providers.close()
        self.flow.close()
        if self._knowledge is not None:
            self._knowledge.close()
        self.state.close()
        super().closeEvent(event)
