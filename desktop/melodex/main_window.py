from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QColor, QDesktopServices, QKeySequence, QPixmap, QShortcut
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QStackedWidget, QLineEdit, QComboBox, QFileDialog, QMessageBox,
    QSlider, QTextEdit, QInputDialog, QDialog, QFormLayout, QDialogButtonBox, QCheckBox,
    QTabWidget, QApplication, QPlainTextEdit, QFrame, QProgressBar,
)

from .paths import app_data_dir
from .provider_manager import ProviderManager
from .flow import FlowEngine
from .mind import MindEngine
from .local_intelligence import LocalIntelligenceService
from .music_map import MusicMapWidget
from .music_map_model import build_music_map
from .album_wall import AlbumWallWidget
from .album_wall_model import build_album_wall
from .music_knowledge import MusicKnowledgeStore, build_knowledge_graph
from .music_pathfinder import find_music_path
from .music_journey import STAGE_LABELS, build_music_journey
from .music_journey_live import replan_live_journey
from .journey_recipe import (
    load_journey_recipe,
    make_journey_recipe,
    materialize_recipe_stages,
    save_journey_recipe,
)
from .journey_replay import (
    materialize_route_snapshot,
    portable_route_snapshot,
    summarize_journey_run,
)
from .user_state import UserState
from .player import FlowPlayer
from .llm_bridge import LLMClient, LLMSettings, llm_track_summary
from .bridge_server import ProviderBridge
from .playlist_io import load_playlist, parse_playlist_text, save_playlist
from .metadata import RichMetadataService
from .rich_now_playing import RichNowPlayingWidget
from .living_canvas import LivingCanvasView
from .visualization_models import build_constellation, build_visual_memory
from .plugin_directory import PluginDirectoryDialog
from .plugin_configuration_dialog import configure_plugin
from .plugin_onboarding import plugin_needs_setup
from .plugin_health import health_badge, health_summary
from .diagnostics import write_diagnostics
from .responsiveness import UiResponsivenessMonitor
from .motion import MotionController, FAST_MOTION_MS, STANDARD_MOTION_MS
from .background_scheduler import BackgroundScheduler
from .library_browser import LibraryBrowser
from .library_scan_process import LibraryScanProcess
from .ux_components import (
    ActionCard,
    CommandPaletteDialog,
    CoverLabel,
    EmptyState,
    FeaturePresenceBar,
    SourceCard,
    set_help,
)


class WorkerSignals(QObject):
    done = Signal(object)
    error = Signal(str)
    progress = Signal(object)


class _VisualAnalysisSignals(QObject):
    ready = Signal(str, object)


class _VisualContextSignals(QObject):
    ready = Signal(int, str, object)


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

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Melodex")
        self.resize(1280, 800)
        self.data_dir = app_data_dir()
        self.providers = ProviderManager(self.data_dir)
        self.state = UserState(self.data_dir / "taste.sqlite3")
        self.motion = MotionController(
            self,
            reduced=self.state.get_bool("reduce_motion", False),
        )
        self.page_titles: dict[str, QLabel] = {}
        self.background = BackgroundScheduler(
            max_workers=4,
            lane_limits={
                "default": 4,
                "disk": 2,
                "network": 2,
                "analysis": 1,
                "prefetch": 1,
                "idle": 1,
            },
        )
        self.flow = FlowEngine(self.data_dir / "flow.sqlite3")
        self.mind = MindEngine(self.state, self.flow)
        self.local_intelligence = LocalIntelligenceService(
            self.state, self.flow, self.providers.capabilities
        )
        self.knowledge = MusicKnowledgeStore(
            self.data_dir / "music-knowledge.sqlite3"
        )
        self.llm = LLMClient()
        self.metadata = RichMetadataService(self.data_dir, capability_broker=self.providers.capabilities)
        self.bridge: ProviderBridge | None = None
        self.current_history_id = 0
        self.current_track_started = 0.0
        self.current_track: dict[str, Any] | None = None
        self._visual_position_ms = 0
        self._visual_duration_ms = 0
        self._visual_analysis_signals = _VisualAnalysisSignals(self)
        self._visual_analysis_signals.ready.connect(self._visual_analysis_loaded)
        self._visual_context_signals = _VisualContextSignals(self)
        self._visual_context_signals.ready.connect(self._visual_context_loaded)
        self._visual_context_sequence = 0
        self._visual_neighbour_tracks: dict[int, dict[str, Any]] = {}
        self.music_path_start_ref = ""
        self.music_path_end_ref = ""
        self.music_path_result: dict[str, Any] = {}
        self.music_journey_stages_data: list[dict[str, Any]] = []
        self.music_live_active = False
        self.music_live_route: dict[str, Any] = {}
        self.music_live_original_route: dict[str, Any] = {}
        self.music_live_destination_ref = ""
        self.music_live_avoid_refs: set[str] = set()
        self.music_live_avoid_artists: set[str] = set()
        self.music_live_replanning = False
        self.music_live_run_id = ""
        self.music_live_played_refs: list[str] = []
        self.music_active_recipe_id = ""
        self.music_active_recipe: dict[str, Any] = {}
        self.pending_journey_recipe: dict[str, Any] | None = None
        self.pending_journey_replay: tuple[dict[str, Any], str] | None = None
        self.current_page = "home"
        self._closing = False
        self._local_scan_in_progress = False
        self._local_scan_pending = False
        self._local_scan_sequence = 0
        self._local_scan_started_at = 0.0
        self._local_scan_last_progress: dict[str, Any] = {}
        self._prefetched_track_assets: dict[str, dict[str, Any]] = {}
        self._prefetch_sequence = 0
        self._prefetch_delay_ms = 350
        self._local_scan_runner: LibraryScanProcess | None = None
        self._local_scan_signals: WorkerSignals | None = None
        self._source_config_refresh_in_progress = False
        self._navigation_generation = 0
        self._page_refresh_delay_ms = 16
        self._search_sequence = 0
        self._search_pending_sequence = 0
        self._search_loading_delay_ms = 220
        self.externalCommand.connect(self._on_external_command)

        self.player = FlowPlayer(
            self.providers.resolve, self._transition_for, self,
            playback_refresher=self.providers.refresh_playback,
        )
        self.player.trackChanged.connect(self._on_track_changed)
        self.player.positionChanged.connect(self._on_position)
        self.player.error.connect(lambda s: self.statusBar().showMessage(s, 7000))
        self.player.queueChanged.connect(self._refresh_queue)
        self.player.queueChanged.connect(
            lambda _queue: self._schedule_next_track_prefetch()
        )
        self.player.manualAdvanced.connect(self._on_manual_advance)

        self._build_ui()
        self.responsiveness = UiResponsivenessMonitor(self)
        self.responsiveness.start()
        self.responsiveness.mark_action("startup:home")
        self._show_home()
        self.responsiveness.mark_action("startup:bridge")
        self._start_local_bridge()
        startup_roots=self.providers.local_roots()
        if startup_roots and not self.providers.local_index_ready(startup_roots):
            # One-time migration for existing users who have configured roots
            # but no persistent index yet. Once indexed, later launches load the
            # cache immediately and do not walk the NAS automatically.
            QTimer.singleShot(0, lambda: self._start_local_scan("initial index"))

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
        self.sidebar.setFixedWidth(210)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(15, 18, 15, 14)
        side.setSpacing(4)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        mark = QLabel()
        mark_path = Path(__file__).resolve().parent / "assets" / "melodex-mark.png"
        pixmap = QPixmap(str(mark_path))
        if not pixmap.isNull():
            mark.setPixmap(
                pixmap.scaled(42, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        mark.setFixedSize(44, 44)
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
        side.addSpacing(18)

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

        self.stack = QStackedWidget()
        body_l.addWidget(self.stack, 1)
        self.pages: dict[str, QWidget] = {}
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
            "sources",
        ]:
            page = QWidget()
            self.pages[name] = page
            self.stack.addWidget(page)

        self._build_home()
        self._build_library()
        self._build_explore()
        self._build_now_playing()
        self._build_for_you()
        self._build_discover()
        self._build_album_wall()
        self._build_music_map()
        self._build_journeys()
        self._build_playlists()
        self._build_moments()
        self._build_ask()
        self._build_sources()

        # Queue is contextual and stays out of the primary navigation.
        self.queue_panel = QWidget()
        self.queue_panel.setObjectName("queuePanel")
        self.queue_panel.setFixedWidth(330)
        ql = QVBoxLayout(self.queue_panel)
        ql.setContentsMargins(14, 14, 14, 14)
        qhead = QHBoxLayout()
        qtitle = QLabel("Up next")
        qtitle.setObjectName("panelTitle")
        qhead.addWidget(qtitle)
        qhead.addStretch(1)
        flow_btn = QPushButton("Refine with Flow")
        flow_btn.setObjectName("quietButton")
        flow_btn.clicked.connect(self._flow_queue)
        set_help(
            flow_btn,
            "Refine with Flow",
            "Reorders upcoming music to make transitions feel more coherent while preserving the current track.",
        )
        qhead.addWidget(flow_btn)
        ql.addLayout(qhead)
        self.queue_list = QListWidget()
        self.queue_list.itemDoubleClicked.connect(self._queue_jump)
        ql.addWidget(self.queue_list, 1)
        self.queue_panel.hide()
        body_l.addWidget(self.queue_panel)

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
        # Persistent player. It behaves as the gateway to Now Playing rather
        # than requiring a permanent sidebar destination.
        bar = QWidget()
        bar.setObjectName("playerBar")
        bar.setFixedHeight(92)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 10, 18, 10)
        bl.setSpacing(9)

        prev = QPushButton("⏮")
        prev.setObjectName("transportButton")
        prev.clicked.connect(self.player.previous)
        self.play_button = QPushButton("▶")
        self.play_button.setObjectName("transportButton")
        self.play_button.clicked.connect(self.player.play_pause)
        nxt = QPushButton("⏭")
        nxt.setObjectName("transportButton")
        nxt.clicked.connect(self.player.next)
        self.player.playingChanged.connect(self._update_play_button)
        set_help(prev, "Previous", "Restart the current track or return to the previous track.")
        set_help(self.play_button, "Play / pause", "Pause or continue the current music.")
        set_help(nxt, "Next", "Move to the next track in the queue.")
        bl.addWidget(prev)
        bl.addWidget(self.play_button)
        bl.addWidget(nxt)

        self.player_cover = CoverLabel(56)
        self.player_cover.set_cover("", title="Melodex", key="melodex")
        self.player_cover.setToolTip("Now playing artwork")
        bl.addWidget(self.player_cover)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        self.now_title = QPushButton("Nothing playing")
        self.now_title.setObjectName("nowPlayingTitle")
        self.now_title.clicked.connect(lambda: self.open_page("now_playing"))
        set_help(
            self.now_title,
            "Open Now Playing",
            "See large artwork, lyrics, track information and visualisations for the current music.",
        )
        self.now_meta = QLabel("")
        self.now_meta.setObjectName("nowPlayingMeta")
        self.now_meta.setOpenExternalLinks(True)
        text_col.addWidget(self.now_title)
        text_col.addWidget(self.now_meta)
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setRange(0, 1000)
        self.seek.sliderReleased.connect(self._seek_released)
        text_col.addWidget(self.seek)
        bl.addLayout(text_col, 1)

        self.keep_button = QPushButton("Keep")
        self.keep_button.setObjectName("playerAction")
        self.keep_button.clicked.connect(self._keep)
        self.love_button = QPushButton("♥")
        self.love_button.setObjectName("playerAction")
        self.love_button.clicked.connect(lambda: self._feedback(True))
        queue = QPushButton("Queue")
        queue.setObjectName("playerAction")
        queue.clicked.connect(
            lambda: self.queue_panel.setVisible(not self.queue_panel.isVisible())
        )
        set_help(self.keep_button, "Keep", "Teach Melodex that this track is worth keeping around in future listening.")
        set_help(self.love_button, "Love", "Mark this as a strong positive preference.")
        set_help(queue, "Queue", "Show or hide the music that is coming next.")
        bl.addWidget(self.keep_button)
        bl.addWidget(self.love_button)
        bl.addWidget(queue)

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
        set_help(match, "Inspect match", "Show how Melodex resolved this track to its playable source.")
        set_help(more, "More actions", "Open technical and less frequently used actions for the current track.")
        power_row.addWidget(match)
        power_row.addWidget(more)
        self.player_power_actions.setVisible(self.power_toggle.isChecked())
        bl.addWidget(self.player_power_actions)
        outer.addWidget(bar)

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
            QWidget#sidebar{
                background:#0a0d12;
                border-right:1px solid #202733;
            }
            QLabel#brandName{
                font-size:20px;
                font-weight:760;
                letter-spacing:2px;
            }
            QLabel#brandTagline{
                color:#778397;
                font-size:10px;
            }
            QPushButton#navButton{
                background:transparent;
                border:0;
                border-radius:9px;
                padding:11px 12px;
                text-align:left;
                color:#dfe4ec;
            }
            QPushButton#navButton:hover{background:#151b25}
            QPushButton#navButton[active="true"]{
                background:#1b2739;
                color:#ffffff;
                font-weight:650;
            }
            QCheckBox#powerToggle{
                background:transparent;
                color:#9ca7b8;
                padding:10px 7px;
            }
            QPushButton{
                background:#181e28;
                border:1px solid #2a3443;
                border-radius:9px;
                padding:9px 13px;
            }
            QPushButton:hover{
                background:#222b38;
                border-color:#3a4a60;
            }
            QPushButton#primaryButton{
                background:#1875e8;
                border-color:#2582f2;
                color:white;
                font-weight:700;
                padding:11px 17px;
            }
            QPushButton#secondaryButton{font-weight:650}
            QPushButton#quietButton{
                background:transparent;
                border-color:#28313e;
                color:#c7ced9;
            }
            QPushButton#miniButton{
                padding:6px 8px;
                font-size:11px;
            }
            QPushButton#segmentButton{
                background:transparent;
                border-color:#28313e;
                color:#aab3c1;
                padding:8px 12px;
            }
            QPushButton#segmentButton:checked{
                background:#1c2d46;
                border-color:#31527a;
                color:white;
                font-weight:650;
            }
            QPushButton#transportButton{
                min-width:38px;
                min-height:38px;
                max-width:38px;
                border-radius:11px;
            }
            QPushButton#transportButtonWide{
                min-height:38px;
                border-radius:11px;
            }
            QPushButton#playerAction{min-height:36px}
            QPushButton#nowPlayingTitle{
                background:transparent;
                border:0;
                padding:0;
                text-align:left;
                font-weight:700;
                font-size:15px;
            }
            QPushButton#nowPlayingTitle:hover{color:#72aefb}
            QLabel#nowPlayingMeta{color:#9da7b7}
            QWidget#playerBar{
                background:#0c1016;
                border-top:1px solid #202733;
            }
            QWidget#queuePanel{
                background:#0d1118;
                border-left:1px solid #202733;
            }
            QLabel#panelTitle{font-size:17px;font-weight:700}
            QLineEdit,QComboBox,QTextEdit,QPlainTextEdit,QListWidget{
                background:#131923;
                border:1px solid #293443;
                border-radius:10px;
                padding:8px;
                selection-background-color:#274f7a;
            }
            QLineEdit:focus,QComboBox:focus,QTextEdit:focus,QListWidget:focus{
                border-color:#3c78b8;
            }
            QListWidget::item{
                padding:11px;
                border-bottom:1px solid #202733;
            }
            QListWidget::item:selected{background:#1e3552}
            QListWidget#sourcesList{
                background:transparent;
                border:0;
                padding:0;
            }
            QListWidget#sourcesList::item{
                background:transparent;
                border:1px solid transparent;
                border-radius:12px;
                padding:4px;
            }
            QListWidget#sourcesList::item:hover{
                background:#131c28;
                border-color:#26384d;
            }
            QListWidget#sourcesList::item:selected{
                background:#17263a;
                border-color:#31547d;
            }
            QFrame#actionCard{
                background:#141b25;
                border:1px solid #293544;
                border-radius:14px;
            }
            QFrame#actionCard:hover{
                background:#182231;
                border-color:#3d5571;
            }
            QLabel#cardEyebrow{
                color:#6fa9ef;
                font-size:10px;
                font-weight:700;
            }
            QLabel#cardTitle{font-size:18px;font-weight:720}
            QLabel#cardBody{color:#9fa9b8}
            QLabel#cardAction{color:#72aefb;font-weight:650}
            QFrame#albumCard{
                background:transparent;
                border:1px solid transparent;
                border-radius:12px;
            }
            QFrame#albumCard:hover{
                background:#151c26;
                border-color:#29384a;
            }
            QLabel#albumCardTitle{font-weight:700;font-size:12px}
            QLabel#albumCardMeta{color:#8995a7;font-size:11px}
            QListView#visualTrackList{
                background:transparent;
                border:0;
                padding:0;
            }
            QListView#visualTrackList::item{
                background:transparent;
                border:0;
                padding:0;
            }
            QListView#visualTrackList::item:selected{
                background:transparent;
            }
            QFrame#trackRow{
                background:#121923;
                border:1px solid #222e3d;
                border-radius:10px;
            }
            QFrame#trackRow:hover{
                background:#161f2b;
                border-color:#33465e;
            }
            QLabel#trackTitle{font-size:14px;font-weight:700}
            QLabel#trackMeta{color:#8f9bad;font-size:12px}
            QLabel#warningPill{
                background:#3a2a16;
                border:1px solid #6e5126;
                border-radius:8px;
                color:#e2bd77;
                padding:4px 7px;
                font-size:10px;
            }
            QLabel#coverArt{
                background:#111722;
                border:1px solid #253040;
                border-radius:8px;
            }
            QFrame#emptyState{
                background:#121821;
                border:1px dashed #313d4e;
                border-radius:15px;
            }
            QLabel#emptyTitle{font-size:20px;font-weight:720}
            QLabel#emptyBody{color:#97a2b2;font-size:13px}
            QFrame#homeHero{
                background:#131c29;
                border:1px solid #2a3d56;
                border-radius:16px;
            }
            QFrame#continueCard{
                background:#121923;
                border:1px solid #273343;
                border-radius:13px;
            }
            QFrame#powerPanel{
                background:#111821;
                border:1px solid #2b3747;
                border-radius:12px;
            }
            QFrame#sourceOverview{
                background:#121b26;
                border:1px solid #2a3a4d;
                border-radius:14px;
            }
            QFrame#sourceFirstRun{
                background:#102033;
                border:1px solid #345a82;
                border-radius:12px;
            }
            QLabel#sourceFirstRunTitle{
                font-size:16px;
                font-weight:740;
                color:#e8f2ff;
            }
            QLabel#sourceFirstRunBody{
                color:#aebed1;
                font-size:11px;
            }

            QFrame#pluginFeaturePicker{
                background:#101720;
                border:1px solid #253346;
                border-radius:12px;
            }
            QFrame#featurePresenceBar{
                background:#101821;
                border:1px solid #26384c;
                border-radius:10px;
            }
            QFrame#artworkProgressPanel{
                background:#101821;
                border:1px solid #2a3d53;
                border-radius:11px;
            }
            QLabel#artworkProgressTitle{
                font-size:12px;
                font-weight:720;
                color:#d8e6f6;
            }
            QLabel#artworkProgressSummary{
                font-size:10px;
                color:#93a7bd;
            }
            QLabel#artworkProgressDetail{
                font-size:10px;
                color:#8492a3;
            }
            QProgressBar{
                min-height:14px;
                max-height:14px;
                border:1px solid #2b3a4c;
                border-radius:7px;
                background:#0c121a;
                text-align:center;
                color:#d6e5f5;
                font-size:9px;
            }
            QProgressBar::chunk{
                border-radius:6px;
                background:#365f8d;
            }

            QFrame#featurePresenceBar[active="true"]{
                background:#111f2c;
                border-color:#315274;
            }
            QLabel#featurePresenceIcon{
                color:#7fb7f1;
                background:#172a3e;
                border:1px solid #2f4e6c;
                border-radius:7px;
                font-size:12px;
                font-weight:800;
            }
            QLabel#featurePresenceText{color:#c7d1de;font-size:11px}
            QPushButton#featurePresenceAction{
                background:transparent;
                border:1px solid #30445b;
                border-radius:8px;
                padding:5px 8px;
                color:#9ebfe4;
                font-size:10px;
                font-weight:650;
            }
            QPushButton#featurePresenceAction:hover{
                background:#182536;
                border-color:#45688e;
                color:#e5f1ff;
            }

            QLabel#pluginFeatureTitle{font-size:13px;font-weight:700}
            QLabel#pluginFeatureSubtitle{color:#7f8b9c;font-size:10px}
            QPushButton#featureChip{
                background:#151f2c;
                border:1px solid #2d4057;
                border-radius:9px;
                padding:7px 10px;
                color:#b9cce2;
                font-weight:650;
            }
            QPushButton#featureChip:hover{
                background:#1b2b3e;
                border-color:#42658c;
                color:#e5f0ff;
            }
            QFrame#sourceSummaryCard{
                background:#0f1620;
                border:1px solid #263547;
                border-radius:11px;
            }
            QLabel#sourceSummaryIcon{
                background:#18283c;
                border:1px solid #2f4c6d;
                border-radius:9px;
                color:#7eb8ff;
                font-size:16px;
                font-weight:800;
            }
            QLabel#sourceSummaryValue{
                color:#8f9bad;
                font-size:11px;
            }
            QLabel#overviewIcon{
                background:#193354;
                border:1px solid #2f5d8f;
                border-radius:12px;
                color:#d8eaff;
                font-size:21px;
                font-weight:700;
            }
            QFrame#sourceCard{
                background:#101720;
                border:1px solid #223045;
                border-radius:10px;
            }
            QLabel#sourceBadge{
                background:#1c2a3e;
                color:#dce9fb;
                border:1px solid #34506f;
                border-radius:10px;
                font-size:17px;
                font-weight:750;
            }
            QLabel#sourceTitle{font-size:15px;font-weight:700}
            QLabel#originPill{
                background:#17202c;
                border:1px solid #2a394b;
                border-radius:7px;
                padding:2px 6px;
                color:#8fa7c3;
                font-size:9px;
                font-weight:650;
            }
            QLabel#sourceDescription{color:#8f9bad}
            QLabel#sourceKind{color:#7d899b;font-size:11px}
            QLabel#statusPill{
                background:#1a2634;
                border:1px solid #30445b;
                border-radius:9px;
                padding:5px 8px;
                color:#bfd4eb;
                font-size:11px;
            }
            QTabWidget::pane{
                border:0;
                background:transparent;
            }
            QTabBar::tab{
                background:transparent;
                color:#aeb7c5;
                border:0;
                border-radius:8px;
                padding:8px 14px;
                margin-right:4px;
            }
            QTabBar::tab:selected{
                background:#1875e8;
                color:white;
            }
            QScrollBar:vertical{
                background:transparent;
                width:10px;
                margin:2px;
            }
            QScrollBar::handle:vertical{
                background:#334154;
                min-height:32px;
                border-radius:5px;
            }
            QScrollBar::handle:vertical:hover{background:#43566f}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{
                height:0;
                background:transparent;
            }
            QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{
                background:transparent;
            }
            QScrollBar:horizontal{
                background:transparent;
                height:10px;
                margin:2px;
            }
            QScrollBar::handle:horizontal{
                background:#334154;
                min-width:32px;
                border-radius:5px;
            }
            QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{
                width:0;
                background:transparent;
            }
            QStatusBar{
                background:#0b0f15;
                color:#7f8b9b;
                border-top:1px solid #202733;
                font-size:11px;
            }
            QToolTip{
                background:#18202c;
                color:#f4f6fa;
                border:1px solid #3a4658;
                padding:7px;
            }
        """)
        self._update_nav_state("home")
        self._refresh_plugin_presence()

    def _update_play_button(self, playing: bool) -> None:
        if hasattr(self,"play_button"):
            self.play_button.setText("❚❚" if playing else "▶")

    def _page_layout(self, page: str, title: str, subtitle: str=""):
        lay=QVBoxLayout(self.pages[page]); lay.setContentsMargins(28,24,28,24)
        t=QLabel(title); t.setStyleSheet("font-size:28px;font-weight:700"); lay.addWidget(t)
        self.page_titles[page]=t
        if subtitle:
            s=QLabel(subtitle); s.setWordWrap(True); s.setStyleSheet("color:#aab0ba"); lay.addWidget(s)
        return lay

    def _build_home(self):
        l=self._page_layout(
            "home",
            "What do you feel like hearing?",
            "Start with an intention. Melodex can stay familiar, help you rediscover something, or take you somewhere less expected.",
        )

        hero=QFrame()
        hero.setObjectName("homeHero")
        hero_l=QVBoxLayout(hero)
        hero_l.setContentsMargins(22,20,22,20)
        hero_l.setSpacing(10)
        prompt=QLabel("Start listening")
        prompt.setStyleSheet("font-size:20px;font-weight:720")
        hero_l.addWidget(prompt)
        explanation=QLabel(
            "One click builds a listening session from your own library. "
            "You can fine-tune it later if you want."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color:#9fa9b8")
        hero_l.addWidget(explanation)

        self.home_primary_button=QPushButton("▶  Play something")
        self.home_primary_button.setObjectName("primaryButton")
        self.home_primary_button.setMinimumHeight(48)
        self.home_primary_button.clicked.connect(self._home_primary_action)
        set_help(
            self.home_primary_button,
            "Play something",
            "Builds a balanced one-hour session from your local library using your listening history and Flow when available.",
        )
        hero_l.addWidget(self.home_primary_button)

        moods=QHBoxLayout()
        comfort=QPushButton("Comfort")
        explore=QPushButton("Explore")
        rediscover=QPushButton("Rediscover")
        tune=QPushButton("Tune it…")
        comfort.clicked.connect(lambda:self._play_for_me("comfort",60,0.14))
        explore.clicked.connect(lambda:self._play_for_me("explore",60,0.72))
        rediscover.clicked.connect(lambda:self._play_for_me("rediscover",60,0.42))
        tune.clicked.connect(lambda:self.open_page("for_you"))
        set_help(comfort,"Comfort","Stay close to music Melodex already knows you respond well to.")
        set_help(explore,"Explore","Move further from the familiar while keeping the session musically coherent.")
        set_help(rediscover,"Rediscover","Favour music from your library that you once played but have not heard recently.")
        set_help(tune,"Fine-tune listening","Open duration, familiarity and local-intelligence controls.")
        moods.addWidget(comfort)
        moods.addWidget(explore)
        moods.addWidget(rediscover)
        moods.addStretch(1)
        moods.addWidget(tune)
        hero_l.addLayout(moods)
        l.addWidget(hero)

        continue_title=QLabel("Continue listening")
        continue_title.setStyleSheet("font-size:18px;font-weight:700;margin-top:10px")
        l.addWidget(continue_title)

        self.home_continue=QFrame()
        self.home_continue.setObjectName("continueCard")
        continue_l=QHBoxLayout(self.home_continue)
        continue_l.setContentsMargins(14,14,14,14)
        continue_l.setSpacing(15)
        self.home_continue_cover=CoverLabel(92)
        continue_l.addWidget(self.home_continue_cover)
        continue_text=QVBoxLayout()
        self.home_continue_title=QLabel("Nothing played yet")
        self.home_continue_title.setStyleSheet("font-size:17px;font-weight:700")
        self.home_continue_meta=QLabel("Play something and it will be easy to return here.")
        self.home_continue_meta.setWordWrap(True)
        self.home_continue_meta.setStyleSheet("color:#98a3b3")
        continue_text.addStretch(1)
        continue_text.addWidget(self.home_continue_title)
        continue_text.addWidget(self.home_continue_meta)
        continue_text.addStretch(1)
        continue_l.addLayout(continue_text,1)
        self.home_continue_button=QPushButton("▶ Continue")
        self.home_continue_button.setObjectName("secondaryButton")
        self.home_continue_button.clicked.connect(self._home_continue_play)
        self.home_continue_button.setEnabled(False)
        set_help(
            self.home_continue_button,
            "Continue listening",
            "Starts the most recent track again. Your listening history stays private on this computer.",
        )
        continue_l.addWidget(self.home_continue_button)
        l.addWidget(self.home_continue)

        explore_title=QLabel("Explore your music")
        explore_title.setStyleSheet("font-size:18px;font-weight:700;margin-top:10px")
        l.addWidget(explore_title)
        cards=QHBoxLayout()
        library_card=ActionCard(
            "Browse your collection",
            "Albums, artists and tracks with artwork instead of file-system detail.",
            eyebrow="My Music",
            action_text="Browse",
        )
        library_card.clicked.connect(lambda:self.open_page("library"))
        wall_card=ActionCard(
            "Album Wall",
            "Explore your records spatially and move between sonic, time and familiarity views.",
            eyebrow="Visual",
            action_text="Explore",
        )
        wall_card.clicked.connect(lambda:self.open_page("album_wall"))
        map_card=ActionCard(
            "Music Map",
            "See relationships between tracks and plan a route when you want deeper exploration.",
            eyebrow="Deep explore",
            action_text="Open map",
        )
        map_card.clicked.connect(lambda:self.open_page("music_map"))
        cards.addWidget(library_card,1)
        cards.addWidget(wall_card,1)
        cards.addWidget(map_card,1)
        l.addLayout(cards)

        self.home_status=QLabel()
        self.home_status.setWordWrap(True)
        self.home_status.setStyleSheet("color:#7f8b9b;margin-top:8px")
        l.addWidget(self.home_status)
        l.addStretch(1)


    def _build_now_playing(self):
        l=self._page_layout(
            "now_playing",
            "Now playing",
            "Stay with the music first. Artwork, lyrics and context are primary; visualisations are there when you want them.",
        )
        self.now_views = QTabWidget()
        self.rich_now = RichNowPlayingWidget(
            self.metadata,
            self,
            auto_online_lyrics=self.state.get_bool("auto_online_lyrics", False),
        )
        self.living_canvas = LivingCanvasView(self, self.data_dir / "visualizers")
        self.rich_now.knowledgeChanged.connect(self._remember_now_playing_knowledge)
        self.rich_now.accentChanged.connect(self.living_canvas.set_accent_color)
        self.rich_now.paletteChanged.connect(self.living_canvas.set_palette)
        self.rich_now.lyricsChanged.connect(self.living_canvas.set_lyrics)
        self.rich_now.lyricsSeekRequested.connect(self.player.seek)
        self.rich_now.lyricsTranslationRequested.connect(self._translate_lyrics)
        self.rich_now.lyricsPluginRequested.connect(
            lambda: self._plugin_directory("lyrics")
        )
        self.rich_now.contextPluginRequested.connect(
            lambda: self._plugin_directory("context")
        )
        self.rich_now.onlineLyricsPreferenceChanged.connect(
            lambda enabled: self.state.set_bool("auto_online_lyrics", bool(enabled))
        )
        self.living_canvas.seekRequested.connect(self.player.seek)
        self.living_canvas.modeDataRequested.connect(self._request_visual_mode_data)
        self.living_canvas.neighbourActivated.connect(self._queue_visual_neighbour)
        self.player.playingChanged.connect(self.living_canvas.set_playing)
        self.now_views.addTab(self.rich_now, "Now Playing")
        self.now_views.addTab(self.living_canvas, "Visuals")
        l.addWidget(self.now_views, 1)


    def _build_for_you(self):
        l=self._page_layout(
            "for_you",
            "Tune your listening",
            "These controls are optional. Start simple, then adjust how long the session lasts and how far Melodex should move from familiar music.",
        )

        row=QHBoxLayout()
        self.mode=QComboBox()
        self.mode.addItem("Balanced","balanced")
        self.mode.addItem("Comfort","comfort")
        self.mode.addItem("Rediscover","rediscover")
        self.mode.addItem("Explore","explore")
        self.minutes=QComboBox()
        self.minutes.addItems(["30","60","90","120"])
        self.adventure=QSlider(Qt.Horizontal)
        self.adventure.setRange(0,100)
        self.adventure.setValue(35)

        set_help(
            self.mode,
            "Listening style",
            "Balanced mixes familiarity and discovery. Comfort stays close to known preferences. Rediscover favours neglected music. Explore moves further away.",
        )
        set_help(
            self.minutes,
            "Session length",
            "Choose approximately how long Melodex should plan for.",
        )
        set_help(
            self.adventure,
            "Familiar to adventurous",
            "Move left to stay close to music Melodex already knows you respond well to; move right to allow more unexpected choices.",
        )

        row.addWidget(QLabel("Style"))
        row.addWidget(self.mode)
        row.addWidget(QLabel("Minutes"))
        row.addWidget(self.minutes)
        row.addWidget(QLabel("Familiar"))
        row.addWidget(self.adventure,1)
        row.addWidget(QLabel("Adventurous"))
        l.addLayout(row)

        go=QPushButton("▶ Build this session")
        go.setObjectName("primaryButton")
        go.clicked.connect(
            lambda:self._play_for_me(
                str(self.mode.currentData() or "balanced"),
                int(self.minutes.currentText()),
                self.adventure.value()/100,
            )
        )
        set_help(
            go,
            "Build this session",
            "Creates a queue from your local library using these preferences. The exact tracks can still change as you listen.",
        )
        l.addWidget(go)

        self.taste_label=QLabel()
        self.taste_label.setWordWrap(True)
        self.taste_label.setStyleSheet("color:#8490a1")
        l.addWidget(self.taste_label)

        intel_title=QLabel("More ways to explore")
        intel_title.setStyleSheet("font-size:18px;font-weight:650;margin-top:10px")
        l.addWidget(intel_title)

        intel_help=QLabel(
            "These suggestions use your own library and listening history. Audio analysis stays on this computer."
        )
        intel_help.setWordWrap(True)
        intel_help.setStyleSheet("color:#aab0ba")
        l.addWidget(intel_help)

        self.recommendation_plugin_presence=FeaturePresenceBar(
            "Recommendation helpers",
            baseline="Melodex local intelligence is active",
            action_text="Add recommendation helper…",
        )
        self.recommendation_plugin_presence.actionRequested.connect(
            lambda:self._plugin_directory("library_suggestions")
        )
        l.addWidget(self.recommendation_plugin_presence)

        intel_row=QHBoxLayout()
        similar=QPushButton("More like current")
        similar.clicked.connect(lambda:self._run_local_intelligence("similar"))
        rediscover=QPushButton("Forgotten favourites")
        rediscover.clicked.connect(lambda:self._run_local_intelligence("rediscover"))
        bridge=QPushButton("Bridge current → next")
        bridge.clicked.connect(lambda:self._run_local_intelligence("bridge"))
        detour=QPushButton("Find a detour")
        detour.clicked.connect(lambda:self._run_local_intelligence("detour"))
        analyse=QPushButton("Improve suggestions")
        analyse.clicked.connect(self._analyse_library_for_intelligence)

        set_help(similar,"More like current","Find music in your local library that is sonically near the track playing now.")
        set_help(rediscover,"Forgotten favourites","Look for music you once played or kept but have not heard recently.")
        set_help(bridge,"Bridge current to next","Find music that can make the transition between the current track and the next queued track feel more natural.")
        set_help(detour,"Find a detour","Keep part of the current musical character while deliberately changing other qualities.")
        set_help(
            analyse,
            "Improve suggestions",
            "Analyse sonic features locally so similarity, detours and map placement can become more accurate. Your audio is not uploaded.",
        )

        intel_row.addWidget(similar)
        intel_row.addWidget(rediscover)
        intel_row.addWidget(bridge)
        intel_row.addWidget(detour)
        intel_row.addWidget(analyse)
        intel_row.addStretch(1)
        l.addLayout(intel_row)

        self.intelligence_results=QListWidget()
        self.intelligence_results.itemDoubleClicked.connect(self._play_intelligence_result)
        l.addWidget(self.intelligence_results,1)

        intel_actions=QHBoxLayout()
        play_pick=QPushButton("▶ Play selected")
        play_pick.clicked.connect(self._play_selected_intelligence)
        queue_pick=QPushButton("+ Queue selected")
        queue_pick.clicked.connect(self._queue_selected_intelligence)
        intel_actions.addWidget(play_pick)
        intel_actions.addWidget(queue_pick)
        intel_actions.addStretch(1)
        l.addLayout(intel_actions)

    def _build_discover(self):
        l=self._page_layout(
            "discover",
            "Discover",
            "Search all connected music sources. One slow or unavailable source will no longer stop the rest of your search.",
        )
        row=QHBoxLayout()
        self.search_box=QLineEdit()
        self.search_box.setPlaceholderText("Artist, track or album…")
        self.search_source=QComboBox()
        self.search_button=QPushButton("Search")
        self.search_button.clicked.connect(self._search)
        row.addWidget(self.search_box,1)
        row.addWidget(self.search_source)
        row.addWidget(self.search_button)
        l.addLayout(row)
        self.search_box.returnPressed.connect(self._search)

        self.search_plugin_presence=FeaturePresenceBar(
            "Search sources",
            baseline="Your local library is always searchable",
            action_text="Add music source…",
        )
        self.search_plugin_presence.actionRequested.connect(
            lambda:self._plugin_directory("search")
        )
        l.addWidget(self.search_plugin_presence)

        self.search_status=QLabel("Ready to search")
        self.search_status.setWordWrap(True)
        self.search_status.setStyleSheet(
            "color:#9aa7b7;padding:6px 2px 4px 2px;font-size:13px"
        )
        l.addWidget(self.search_status)

        self.results=QListWidget()
        self.results.itemDoubleClicked.connect(self._play_result)
        l.addWidget(self.results,1)

        row2=QHBoxLayout()
        addq=QPushButton("Add selected to queue")
        addq.clicked.connect(self._add_selected_to_queue)
        source_btn=QPushButton("Open source page")
        source_btn.clicked.connect(self._open_selected_source)
        row2.addWidget(addq)
        row2.addWidget(source_btn)
        row2.addStretch(1)
        l.addLayout(row2)

    def _build_library(self):
        l=self._page_layout(
            "library",
            "My Music",
            "Browse the collection you chose to keep on this device. Album artwork and musical identity come first; file details stay out of the way.",
        )
        self.artwork_plugin_presence=FeaturePresenceBar(
            "Artwork helpers",
            baseline="Built-in artwork matching is active",
            action_text="Add artwork helper…",
        )
        self.artwork_plugin_presence.actionRequested.connect(
            lambda:self._plugin_directory("artwork")
        )
        l.addWidget(self.artwork_plugin_presence)

        self.library_browser=LibraryBrowser(self)
        self.library_browser.playAlbumRequested.connect(self._play_album_wall_album)
        self.library_browser.queueAlbumRequested.connect(self._queue_album_data)
        self.library_browser.playArtistRequested.connect(self._play_library_artist)
        self.library_browser.playTrackRequested.connect(self._play_library_track)
        self.library_browser.queueTrackRequested.connect(self._queue_library_track)
        self.library_browser.editMetadataRequested.connect(self._edit_local_metadata)
        self.library_browser.addFolderRequested.connect(self._choose_music_folder)
        self.library_browser.rescanRequested.connect(self._rescan)
        self.library_browser.scanPauseRequested.connect(self._toggle_local_scan_pause)
        self.library_browser.scanCancelRequested.connect(self._cancel_local_scan)
        self.library_browser.albumWallRequested.connect(lambda:self.open_page("album_wall"))
        self.library_browser.momentsRequested.connect(lambda:self.open_page("moments"))
        self.library_browser.artworkRequested.connect(self._library_artwork_requested)
        self.library_browser.onlineArtworkRequested.connect(self._library_online_artwork_requested)
        self.library_browser.artistImageRequested.connect(self._library_artist_images_requested)
        self.library_browser.artistImageCacheRequested.connect(self._library_cached_artist_images_requested)
        self.library_browser.artistPhotoFileRequested.connect(self._choose_artist_photo_file)
        l.addWidget(self.library_browser,1)


    def _build_explore(self):
        l=self._page_layout(
            "explore",
            "Explore",
            "Choose the kind of exploration you want. Search is direct; Album Wall is visual; Music Map goes deeper into relationships and routes.",
        )

        cards=QHBoxLayout()
        search_card=ActionCard(
            "Search everything",
            "Find artists, albums or tracks across all the music sources you have connected.",
            eyebrow="Search",
            action_text="Search",
        )
        search_card.clicked.connect(lambda:self.open_page("discover"))
        wall_card=ActionCard(
            "Album Wall",
            "Browse your own collection as a stable visual place built from album covers.",
            eyebrow="Browse",
            action_text="Open wall",
        )
        wall_card.clicked.connect(lambda:self.open_page("album_wall"))
        map_card=ActionCard(
            "Music Map",
            "Explore sonic relationships between tracks. Advanced route-planning appears when you need it.",
            eyebrow="Relationships",
            action_text="Open map",
        )
        map_card.clicked.connect(lambda:self.open_page("music_map"))
        cards.addWidget(search_card,1)
        cards.addWidget(wall_card,1)
        cards.addWidget(map_card,1)
        l.addLayout(cards)

        help_title=QLabel("Not sure where to start?")
        help_title.setStyleSheet("font-size:18px;font-weight:700;margin-top:18px")
        l.addWidget(help_title)
        help_row=QHBoxLayout()
        similar=QPushButton("More like what is playing")
        similar.clicked.connect(lambda:self._run_local_intelligence("similar"))
        rediscover=QPushButton("Find a forgotten favourite")
        rediscover.clicked.connect(lambda:self._run_local_intelligence("rediscover"))
        ask=QPushButton("Ask Melodex…")
        ask.clicked.connect(lambda:self.open_page("ask"))
        set_help(similar,"More like this","Uses local intelligence to look for nearby music in your own library.")
        set_help(rediscover,"Forgotten favourite","Looks for music you used to play but have not heard for a while.")
        set_help(ask,"Ask Melodex","Use an optional connected LLM for natural-language listening requests. Melodex still works without one.")
        help_row.addWidget(similar)
        help_row.addWidget(rediscover)
        help_row.addWidget(ask)
        help_row.addStretch(1)
        l.addLayout(help_row)

        note=QLabel(
            "Tip: Album Wall is designed for visual browsing. Music Map is the power tool for understanding and shaping routes between tracks."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#8793a4;margin-top:12px")
        l.addWidget(note)
        l.addStretch(1)

    def _build_album_wall(self):
        l=self._page_layout(
            "album_wall",
            "Album Wall",
            "Browse your collection as a visual place. Drag or two-finger scroll to pan, zoom when you need it, and double-click an album to play.",
        )

        actions=QHBoxLayout()
        self.album_wall_options_button=QPushButton("Wall options…")
        self.album_wall_options_button.clicked.connect(self._toggle_album_wall_tools)
        self.album_wall_play_button=QPushButton("▶ Play selected")
        self.album_wall_play_button.clicked.connect(self._play_album_wall_selected)
        self.album_wall_play_button.setEnabled(False)
        self.album_wall_queue_button=QPushButton("+ Queue selected")
        self.album_wall_queue_button.clicked.connect(self._queue_album_wall_selected)
        self.album_wall_queue_button.setEnabled(False)
        set_help(
            self.album_wall_options_button,
            "Wall options",
            "Reveal occasional maintenance actions such as sonic analysis, rebuilding the wall and recovering missing covers.",
        )
        set_help(
            self.album_wall_play_button,
            "Play selected album",
            "Starts the selected album from track one in disc and track order.",
        )
        set_help(
            self.album_wall_queue_button,
            "Queue selected album",
            "Adds every track from the selected album after the music already in your queue.",
        )
        actions.addWidget(self.album_wall_options_button)
        actions.addStretch(1)
        actions.addWidget(self.album_wall_play_button)
        actions.addWidget(self.album_wall_queue_button)
        l.addLayout(actions)

        self.album_wall_power_panel=QFrame()
        self.album_wall_power_panel.setObjectName("powerPanel")
        power=QHBoxLayout(self.album_wall_power_panel)
        power.setContentsMargins(12,8,12,8)
        refresh=QPushButton("Rebuild wall")
        refresh.clicked.connect(self._refresh_album_wall)
        raw_analyse=QPushButton("Improve sonic layout")
        raw_analyse.clicked.connect(self._analyse_library_for_album_wall)
        recover_covers=QPushButton("Find missing covers")
        recover_covers.clicked.connect(
            lambda:self.album_wall.request_missing_covers()
            if hasattr(self,"album_wall") else None
        )
        power.addWidget(QLabel("Wall options"))
        power.addWidget(refresh)
        power.addWidget(raw_analyse)
        power.addWidget(recover_covers)
        power.addStretch(1)
        self.album_wall_power_panel.hide()
        l.addWidget(self.album_wall_power_panel)

        self.album_wall=AlbumWallWidget(self)
        self.album_wall.albumSelected.connect(self._album_wall_selection_changed)
        self.album_wall.albumActivated.connect(self._play_album_wall_album)
        self.album_wall.artworkRequested.connect(self._album_wall_artwork_requested)
        self.album_wall.onlineArtworkRequested.connect(self._album_wall_online_artwork_requested)
        l.addWidget(self.album_wall,1)

    def _album_wall_selection_changed(self, album: object) -> None:
        enabled=isinstance(album,dict) and bool(album)
        self.album_wall_play_button.setEnabled(enabled)
        self.album_wall_queue_button.setEnabled(enabled)


    def _build_music_map(self):
        l=self._page_layout(
            "music_map",
            "Music Map",
            "Explore your music as a landscape. Pan and zoom freely; select a track to reveal its closest relationships. Routes and technical tools stay out of the way until requested.",
        )

        simple=QHBoxLayout()
        self.music_map_options_button=QPushButton("Map options…")
        self.music_map_options_button.clicked.connect(self._toggle_music_map_options)
        self.music_map_play_button=QPushButton("▶ Play selected")
        self.music_map_play_button.clicked.connect(self._play_music_map_selected)
        self.music_map_play_button.setEnabled(False)
        self.music_map_queue_button=QPushButton("+ Queue selected")
        self.music_map_queue_button.clicked.connect(self._queue_music_map_selected)
        self.music_map_queue_button.setEnabled(False)
        self.music_map_plan_button=QPushButton("Plan a route…")
        self.music_map_plan_button.clicked.connect(self._toggle_music_map_tools)
        set_help(
            self.music_map_options_button,
            "Map options",
            "Reveal occasional analysis, refresh and knowledge-enrichment actions without shrinking the map while you browse.",
        )
        set_help(
            self.music_map_plan_button,
            "Plan a route",
            "Reveal only the start, destination and route controls. Journey shaping stays hidden until you request it.",
        )
        simple.addWidget(self.music_map_options_button)
        simple.addStretch(1)
        simple.addWidget(self.music_map_play_button)
        simple.addWidget(self.music_map_queue_button)
        simple.addWidget(self.music_map_plan_button)
        l.addLayout(simple)

        self.music_map_options_panel=QFrame()
        self.music_map_options_panel.setObjectName("powerPanel")
        map_options=QHBoxLayout(self.music_map_options_panel)
        map_options.setContentsMargins(12,8,12,8)
        improve=QPushButton("Improve map")
        improve.clicked.connect(self._analyse_library_for_map)
        refresh_map=QPushButton("Refresh")
        refresh_map.clicked.connect(self._refresh_music_map)
        enrich_selected=QPushButton("Find selected details")
        enrich_selected.clicked.connect(self._enrich_selected_map_knowledge)
        enrich_map=QPushButton("Find map details (+8)")
        enrich_map.clicked.connect(self._enrich_map_knowledge_batch)
        map_options.addWidget(QLabel("Map options"))
        map_options.addWidget(improve)
        map_options.addWidget(refresh_map)
        map_options.addWidget(enrich_selected)
        map_options.addWidget(enrich_map)
        map_options.addStretch(1)
        self.music_map_options_panel.hide()
        l.addWidget(self.music_map_options_panel)

        self.music_map_power_panel=QFrame()
        self.music_map_power_panel.setObjectName("powerPanel")
        power=QVBoxLayout(self.music_map_power_panel)
        power.setContentsMargins(13,11,13,11)
        power.setSpacing(8)

        top=QHBoxLayout()
        power_title=QLabel("Route planner")
        power_title.setStyleSheet("font-size:15px;font-weight:700")
        start_here=QPushButton("Start listening here")
        start_here.clicked.connect(self._journey_from_music_map)
        journey_options=QPushButton("Journey options…")
        journey_options.clicked.connect(self._toggle_music_journey_options)
        close_tools=QPushButton("Hide route tools")
        close_tools.clicked.connect(self._toggle_music_map_tools)
        top.addWidget(power_title)
        top.addStretch(1)
        top.addWidget(start_here)
        top.addWidget(journey_options)
        top.addWidget(close_tools)
        power.addLayout(top)

        path_row=QHBoxLayout()
        self.music_path_mode=QComboBox()
        self.music_path_mode.addItem("Balanced", "balanced")
        self.music_path_mode.addItem("Sonic", "sonic")
        self.music_path_mode.addItem("Knowledge-first", "knowledge")
        self.music_path_mode.currentIndexChanged.connect(
            lambda *_:self._journey_recipe_mark_modified()
        )
        set_start=QPushButton("Use selected as start")
        set_start.clicked.connect(self._music_path_set_start)
        set_end=QPushButton("Use selected as destination")
        set_end.clicked.connect(self._music_path_set_end)
        find_path=QPushButton("Find route")
        find_path.clicked.connect(self._music_path_find)
        play_path=QPushButton("▶ Play route")
        play_path.clicked.connect(self._music_path_play)
        queue_path=QPushButton("+ Queue route")
        queue_path.clicked.connect(self._music_path_queue)
        clear_path=QPushButton("Clear")
        clear_path.clicked.connect(self._music_path_clear)
        self.music_path_label=QLabel("Start —  →  Destination —")
        self.music_path_label.setStyleSheet("color:#aab0ba")
        path_row.addWidget(QLabel("Route"))
        path_row.addWidget(self.music_path_mode)
        path_row.addWidget(set_start)
        path_row.addWidget(set_end)
        path_row.addWidget(find_path)
        path_row.addWidget(play_path)
        path_row.addWidget(queue_path)
        path_row.addWidget(clear_path)
        path_row.addWidget(self.music_path_label,1)
        power.addLayout(path_row)

        self.music_map_journey_panel=QFrame()
        self.music_map_journey_panel.setObjectName("subtlePanel")
        journey_box=QVBoxLayout(self.music_map_journey_panel)
        journey_box.setContentsMargins(10,8,10,8)
        journey_box.setSpacing(7)

        journey_edit=QHBoxLayout()
        self.music_journey_preset=QComboBox()
        self.music_journey_preset.addItem(
            "Calm → Darker → Forgotten → Energetic",
            ["calm","dark","forgotten","energetic"],
        )
        self.music_journey_preset.addItem(
            "Calm → Rhythmic → Energetic",
            ["calm","rhythmic","energetic"],
        )
        self.music_journey_preset.addItem(
            "Familiar → Forgotten → Bright",
            ["familiar","forgotten","bright"],
        )
        self.music_journey_preset.addItem(
            "Surprising → Darker → Bright",
            ["surprising","dark","bright"],
        )
        load_preset=QPushButton("Load shape")
        load_preset.clicked.connect(self._music_journey_load_preset)
        self.music_journey_constraint=QComboBox()
        for key in ("calm","dark","forgotten","energetic","bright","rhythmic","familiar","surprising"):
            self.music_journey_constraint.addItem(STAGE_LABELS[key],key)
        add_constraint=QPushButton("Add direction")
        add_constraint.clicked.connect(self._music_journey_add_constraint)
        add_track=QPushButton("Add selected track")
        add_track.clicked.connect(self._music_journey_add_track)
        remove_stage=QPushButton("Remove")
        remove_stage.clicked.connect(self._music_journey_remove_stage)
        clear_stages=QPushButton("Clear shape")
        clear_stages.clicked.connect(self._music_journey_clear_stages)
        journey_edit.addWidget(QLabel("Shape journey"))
        journey_edit.addWidget(self.music_journey_preset,1)
        journey_edit.addWidget(load_preset)
        journey_edit.addWidget(self.music_journey_constraint)
        journey_edit.addWidget(add_constraint)
        journey_edit.addWidget(add_track)
        journey_edit.addWidget(remove_stage)
        journey_edit.addWidget(clear_stages)
        journey_box.addLayout(journey_edit)

        journey_actions=QHBoxLayout()
        build_journey=QPushButton("Build journey")
        build_journey.clicked.connect(self._music_journey_build)
        play_journey=QPushButton("▶ Play")
        play_journey.clicked.connect(self._music_path_play)
        queue_journey=QPushButton("+ Queue")
        queue_journey.clicked.connect(self._music_path_queue)
        journey_help=QLabel("Start and destination come from the route above.")
        journey_help.setStyleSheet("color:#aab0ba")
        journey_actions.addWidget(build_journey)
        journey_actions.addWidget(play_journey)
        journey_actions.addWidget(queue_journey)
        journey_actions.addWidget(journey_help,1)
        journey_box.addLayout(journey_actions)

        self.music_journey_stages=QListWidget()
        self.music_journey_stages.setMaximumHeight(92)
        self.music_journey_stages.addItem(
            "Choose a shape or add directions after setting a start and destination."
        )
        journey_box.addWidget(self.music_journey_stages)

        live_row=QHBoxLayout()
        self.music_live_steering=QComboBox()
        self.music_live_steering.addItem("No extra steer", "")
        for key,label in (
            ("calmer","Calmer next"),
            ("more_energy","More energy next"),
            ("darker","Darker next"),
            ("brighter","Brighter next"),
            ("more_rhythmic","More rhythmic next"),
            ("more_familiar","More familiar next"),
            ("more_surprising","More surprising next"),
            ("rediscover","Rediscover next"),
        ):
            self.music_live_steering.addItem(label,key)
        play_live=QPushButton("Play live journey")
        play_live.clicked.connect(self._journey_live_start)
        apply_steer=QPushButton("Apply steer")
        apply_steer.clicked.connect(self._journey_live_apply_steer)
        avoid_artist=QPushButton("Avoid current artist")
        avoid_artist.clicked.connect(self._journey_live_avoid_current_artist)
        skip_replan=QPushButton("Skip + replan")
        skip_replan.clicked.connect(self.player.next)
        replan=QPushButton("Replan")
        replan.clicked.connect(lambda:self._journey_live_replan("",reason="manual replan"))
        restore=QPushButton("Restore design")
        restore.clicked.connect(self._journey_live_restore)
        stop_live=QPushButton("Stop live")
        stop_live.clicked.connect(self._journey_live_stop)
        self.music_live_label=QLabel("Live journey inactive")
        self.music_live_label.setStyleSheet("color:#aab0ba")
        live_row.addWidget(QLabel("While listening"))
        live_row.addWidget(play_live)
        live_row.addWidget(self.music_live_steering)
        live_row.addWidget(apply_steer)
        live_row.addWidget(avoid_artist)
        live_row.addWidget(skip_replan)
        live_row.addWidget(replan)
        live_row.addWidget(restore)
        live_row.addWidget(stop_live)
        live_row.addWidget(self.music_live_label,1)
        journey_box.addLayout(live_row)
        self.music_map_journey_panel.hide()
        power.addWidget(self.music_map_journey_panel)

        self.music_map_power_panel.hide()
        l.addWidget(self.music_map_power_panel)

        self.music_map=MusicMapWidget(self)
        self.music_map.trackSelected.connect(self._music_map_selection_changed)
        self.music_map.trackActivated.connect(self._play_music_map_track)
        l.addWidget(self.music_map,1)

        self.music_path_steps=QListWidget()
        self.music_path_steps.setMaximumHeight(116)
        self.music_path_steps.addItem("Route explanations will appear here after you plan one.")
        self.music_path_steps.hide()
        l.addWidget(self.music_path_steps)

    def _toggle_album_wall_tools(self) -> None:
        visible=not self.album_wall_power_panel.isVisible()
        self.album_wall_power_panel.setVisible(visible)

    def _toggle_music_map_options(self) -> None:
        visible=not self.music_map_options_panel.isVisible()
        self.music_map_options_panel.setVisible(visible)

    def _toggle_music_map_tools(self) -> None:
        visible=not self.music_map_power_panel.isVisible()
        self.music_map_power_panel.setVisible(visible)
        self.music_path_steps.setVisible(visible)
        if not visible and hasattr(self,"music_map_journey_panel"):
            self.music_map_journey_panel.hide()
        if visible:
            self.statusBar().showMessage(
                "Route planner ready · select a track, set start and destination, then Find route",
                5000,
            )

    def _toggle_music_journey_options(self) -> None:
        if not self.music_map_power_panel.isVisible():
            self.music_map_power_panel.show()
            self.music_path_steps.show()
        visible=not self.music_map_journey_panel.isVisible()
        self.music_map_journey_panel.setVisible(visible)

    def _music_map_selection_changed(self, track: object) -> None:
        enabled=isinstance(track,dict) and bool(track)
        self.music_map_play_button.setEnabled(enabled)
        self.music_map_queue_button.setEnabled(enabled)


    def _build_journeys(self):
        l=self._page_layout(
            "journeys",
            "Journeys",
            "A journey is a listening route that develops gradually instead of shuffling randomly. Save designs you want to reuse; run history stays private on this computer.",
        )

        top=QHBoxLayout()
        design=QPushButton("Design a journey")
        design.setObjectName("primaryButton")
        design.clicked.connect(self._open_journey_designer)
        import_recipe=QPushButton("Import journey…")
        import_recipe.clicked.connect(self._journey_recipe_import)
        set_help(
            design,
            "Design a journey",
            "Open Music Map with route tools revealed so you can choose a start, destination and the shape of the listening route.",
        )
        set_help(
            import_recipe,
            "Import journey",
            "Open a portable .mdxjourney recipe. Recipes store intent and waypoints without exposing your private listening history.",
        )
        top.addWidget(design)
        top.addWidget(import_recipe)
        top.addStretch(1)
        l.addLayout(top)

        self.journey_tabs=QTabWidget()
        l.addWidget(self.journey_tabs,1)

        saved=QWidget()
        saved_l=QVBoxLayout(saved)
        saved_l.setContentsMargins(0,10,0,0)
        saved_help=QLabel(
            "Saved journeys remember the route idea. When you reuse one, Melodex can resolve it against the music available now."
        )
        saved_help.setWordWrap(True)
        saved_help.setStyleSheet("color:#8f9bad")
        saved_l.addWidget(saved_help)
        self.journey_recipes_stack=QStackedWidget()
        self.journey_recipes_list=QListWidget()
        self.journey_recipes_list.itemDoubleClicked.connect(
            lambda _item:self._journey_recipe_load_selected()
        )
        self.journey_recipes_empty=EmptyState(
            "No saved journeys yet",
            "Design a journey to remember a route you may want to reuse later.",
            "Design a journey",
        )
        self.journey_recipes_empty.actionRequested.connect(self._open_journey_designer)
        self.journey_recipes_stack.addWidget(self.journey_recipes_list)
        self.journey_recipes_stack.addWidget(self.journey_recipes_empty)
        saved_l.addWidget(self.journey_recipes_stack,1)
        recipe_buttons=QHBoxLayout()
        load_selected=QPushButton("Open selected")
        load_selected.clicked.connect(self._journey_recipe_load_selected)
        save_current=QPushButton("Save current design")
        save_current.clicked.connect(self._journey_recipe_save_current)
        export_recipe=QPushButton("Export…")
        export_recipe.clicked.connect(self._journey_recipe_export)
        delete_recipe=QPushButton("Delete")
        delete_recipe.clicked.connect(self._journey_recipe_delete)
        set_help(
            save_current,
            "Save current design",
            "Stores the route shape currently prepared in Music Map as a reusable journey recipe.",
        )
        for button in (load_selected,save_current,export_recipe,delete_recipe):
            recipe_buttons.addWidget(button)
        recipe_buttons.addStretch(1)
        saved_l.addLayout(recipe_buttons)
        self.journey_tabs.addTab(saved,"Saved journeys")

        runs=QWidget()
        runs_l=QVBoxLayout(runs)
        runs_l.setContentsMargins(0,10,0,0)
        runs_help=QLabel(
            "Recent runs show what actually happened after skips, steering and live replanning. This history is local to Melodex."
        )
        runs_help.setWordWrap(True)
        runs_help.setStyleSheet("color:#8f9bad")
        runs_l.addWidget(runs_help)
        self.journey_runs_stack=QStackedWidget()
        self.journey_runs_list=QListWidget()
        self.journey_runs_list.itemDoubleClicked.connect(
            lambda _item:self._journey_run_inspect()
        )
        self.journey_runs_empty=EmptyState(
            "No journey runs yet",
            "When you play a journey, Melodex keeps a private local record of how the route changed while you listened.",
        )
        self.journey_runs_stack.addWidget(self.journey_runs_list)
        self.journey_runs_stack.addWidget(self.journey_runs_empty)
        runs_l.addWidget(self.journey_runs_stack,1)
        run_buttons=QHBoxLayout()
        inspect=QPushButton("Inspect")
        inspect.clicked.connect(self._journey_run_inspect)
        replay_original=QPushButton("Replay designed")
        replay_original.clicked.connect(lambda:self._journey_run_replay("original"))
        replay_final=QPushButton("Replay final")
        replay_final.clicked.connect(lambda:self._journey_run_replay("final"))
        run_buttons.addWidget(inspect)
        run_buttons.addWidget(replay_original)
        run_buttons.addWidget(replay_final)
        run_buttons.addStretch(1)
        runs_l.addLayout(run_buttons)
        self.journey_tabs.addTab(runs,"Recent runs")

    def _open_journey_designer(self) -> None:
        self.open_page("music_map")
        self.music_map_power_panel.show()
        self.music_map_journey_panel.show()
        self.music_path_steps.show()
        self.statusBar().showMessage(
            "Journey design ready · select a track for the start, another for the destination, then shape the route",
            6000,
        )


    def _build_playlists(self):
        l=self._page_layout(
            "playlists",
            "Playlists",
            "Keep ordinary playlists alongside AI-generated or imported ones. Melodex stores them locally and resolves tracks through the sources you have connected.",
        )

        top=QHBoxLayout()
        imp=QPushButton("Import playlist…")
        imp.clicked.connect(self._import_playlist_file)
        ai=QPushButton("Paste from AI…")
        ai.setObjectName("primaryButton")
        ai.clicked.connect(self._open_ai_playlist_import)
        set_help(
            imp,
            "Import playlist",
            "Import XSPF, M3U or M3U8. Melodex keeps unmatched requests so they can be resolved later.",
        )
        set_help(
            ai,
            "Paste from AI",
            "Paste a playlist generated in ChatGPT, Claude, Gemini or another AI. No AI account is connected and the pasted text is not sent back to an AI service.",
        )
        top.addWidget(ai)
        top.addWidget(imp)
        top.addStretch(1)
        l.addLayout(top)

        self.playlists_stack=QStackedWidget()
        self.playlists_list=QListWidget()
        self.playlists_list.itemDoubleClicked.connect(self._play_saved_playlist)
        self.playlists_list.itemSelectionChanged.connect(self._playlist_selection_changed)
        self.playlists_empty=EmptyState(
            "No playlists yet",
            "Paste one from an AI chat, import an existing playlist, or export the music already in your queue.",
            "Paste from AI",
        )
        self.playlists_empty.actionRequested.connect(self._open_ai_playlist_import)
        self.playlists_stack.addWidget(self.playlists_list)
        self.playlists_stack.addWidget(self.playlists_empty)
        l.addWidget(self.playlists_stack,1)

        row=QHBoxLayout()
        self.playlist_export_button=QPushButton("Export selected…")
        self.playlist_export_button.clicked.connect(self._export_selected_playlist)
        self.playlist_export_button.setEnabled(False)
        expq=QPushButton("Export current queue…")
        expq.clicked.connect(self._export_queue)
        row.addWidget(self.playlist_export_button)
        row.addWidget(expq)
        row.addStretch(1)
        l.addLayout(row)

    def _playlist_selection_changed(self) -> None:
        item=self.playlists_list.currentItem() if hasattr(self,"playlists_list") else None
        record=item.data(Qt.UserRole) if item else None
        if hasattr(self,"playlist_export_button"):
            self.playlist_export_button.setEnabled(isinstance(record,dict))


    def _build_moments(self):
        l=self._page_layout(
            "moments",
            "Moments",
            "Bookmarks inside songs — the exact musical moments you wanted to remember, not just a list of favourite tracks.",
        )
        note=QLabel(
            "While something is playing, use the current-track actions to remember a moment. Double-click a saved moment to play from that point."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#8f9bad")
        l.addWidget(note)
        self.moments_stack=QStackedWidget()
        self.moments_list=QListWidget()
        self.moments_list.itemDoubleClicked.connect(self._play_saved_moment)
        self.moments_empty=EmptyState(
            "No moments saved yet",
            "When a song reaches a part you want to remember, save that exact point and it will appear here.",
            "Open Now Playing",
        )
        self.moments_empty.actionRequested.connect(lambda:self.open_page("now_playing"))
        self.moments_stack.addWidget(self.moments_list)
        self.moments_stack.addWidget(self.moments_empty)
        l.addWidget(self.moments_stack,1)


    def _build_ask(self):
        l=self._page_layout("ask","Ask Melodex","Optional. Connect OpenWebUI, Ollama or another compatible model. The player still works without any LLM.")
        self.chat=QTextEdit(); self.chat.setReadOnly(True); l.addWidget(self.chat,1)
        row=QHBoxLayout(); self.ask_box=QLineEdit(); self.ask_box.setPlaceholderText("e.g. Keep this mood but make the next hour stranger"); self.ask_box.returnPressed.connect(self._ask); ask=QPushButton("Ask"); ask.clicked.connect(self._ask); cfg=QPushButton("Connect LLM…"); cfg.clicked.connect(self._llm_settings_dialog); row.addWidget(self.ask_box,1); row.addWidget(ask); row.addWidget(cfg); l.addLayout(row)

    def _dismiss_sources_intro(self) -> None:
        self.state.set_bool("sources_intro_seen",True)
        if hasattr(self,"source_welcome"):
            self.source_welcome.hide()

    def _build_sources(self):
        l=self._page_layout(
            "sources",
            "Sources & plugins",
            "See what Melodex includes, what you have connected, and which optional enhancements are installed. Technical details stay under Power tools.",
        )

        self.source_welcome=QFrame()
        self.source_welcome.setObjectName("sourceFirstRun")
        welcome_l=QHBoxLayout(self.source_welcome)
        welcome_l.setContentsMargins(16,13,16,13)
        welcome_l.setSpacing(12)

        welcome_text=QVBoxLayout()
        welcome_text.setSpacing(3)
        welcome_title=QLabel("You are already ready to listen")
        welcome_title.setObjectName("sourceFirstRunTitle")
        welcome_body=QLabel(
            "Your own library and the sources included with Melodex work without extra setup. "
            "Plugins are optional: add them only when you want more music, artwork, lyrics, "
            "recommendations or context."
        )
        welcome_body.setObjectName("sourceFirstRunBody")
        welcome_body.setWordWrap(True)
        welcome_text.addWidget(welcome_title)
        welcome_text.addWidget(welcome_body)
        welcome_l.addLayout(welcome_text,1)

        welcome_plugins=QPushButton("Browse optional features")
        welcome_plugins.setObjectName("secondaryButton")
        welcome_plugins.clicked.connect(self._plugin_directory)
        welcome_done=QPushButton("Got it")
        welcome_done.setObjectName("quietButton")
        welcome_done.clicked.connect(self._dismiss_sources_intro)
        welcome_l.addWidget(welcome_plugins)
        welcome_l.addWidget(welcome_done)

        self.source_welcome.setVisible(
            not self.state.get_bool("sources_intro_seen",False)
        )
        l.addWidget(self.source_welcome)

        overview=QFrame()
        overview.setObjectName("sourceOverview")
        overview_l=QVBoxLayout(overview)
        overview_l.setContentsMargins(18,16,18,16)
        overview_l.setSpacing(12)

        overview_head=QHBoxLayout()
        overview_title=QLabel("Your Melodex ecosystem")
        overview_title.setStyleSheet("font-size:18px;font-weight:720")
        overview_head.addWidget(overview_title)
        overview_head.addStretch(1)
        self.source_check_all=QPushButton("Check connections")
        self.source_check_all.clicked.connect(self._test_all_plugins)
        set_help(
            self.source_check_all,
            "Check installed sources and plugins",
            "Runs bounded connection/runtime checks for installed plugins. It does not change your setup.",
        )
        overview_head.addWidget(self.source_check_all)
        overview_l.addLayout(overview_head)

        self.sources_overview=QLabel(
            "Your own music works without plugins. Included sources and optional enhancements can add more places to listen, artwork, lyrics and discovery."
        )
        self.sources_overview.setWordWrap(True)
        self.sources_overview.setStyleSheet("color:#93a0b2")
        overview_l.addWidget(self.sources_overview)

        summary=QHBoxLayout()
        summary.setSpacing(10)
        def summary_card(glyph: str, title: str):
            card=QFrame()
            card.setObjectName("sourceSummaryCard")
            row=QHBoxLayout(card)
            row.setContentsMargins(12,10,12,10)
            row.setSpacing(9)
            icon=QLabel(glyph)
            icon.setObjectName("sourceSummaryIcon")
            icon.setAlignment(Qt.AlignCenter)
            icon.setFixedSize(34,34)
            row.addWidget(icon)
            col=QVBoxLayout()
            col.setSpacing(0)
            label=QLabel(title)
            label.setStyleSheet("font-weight:700")
            value=QLabel("—")
            value.setObjectName("sourceSummaryValue")
            col.addWidget(label)
            col.addWidget(value)
            row.addLayout(col,1)
            summary.addWidget(card,1)
            return value

        self.source_summary_library=summary_card("♫","Your music")
        self.source_summary_included=summary_card("＋","Included")
        self.source_summary_enhancements=summary_card("✦","Enhancements")
        overview_l.addLayout(summary)
        l.addWidget(overview)

        actions=QHBoxLayout()
        local=QPushButton("+ Add my music")
        local.setObjectName("primaryButton")
        local.clicked.connect(self._choose_music_folder)
        directory=QPushButton("Add features…")
        directory.setObjectName("secondaryButton")
        directory.clicked.connect(self._plugin_directory)
        streams=QPushButton("My streams")
        streams.clicked.connect(self._user_streams_dialog)
        self.source_primary_button=QPushButton("Use selected")
        self.source_primary_button.clicked.connect(self._source_primary_action)
        self.source_primary_button.setEnabled(False)
        set_help(
            local,
            "Add local music",
            "Choose a folder of music on this computer. Your files stay local.",
        )
        set_help(
            directory,
            "Add features",
            "Open the Plugin Centre to add optional music sources, recommendations, artwork, lyrics, metadata or context enhancements.",
        )
        set_help(
            streams,
            "My streams",
            "Add direct radio or stream URLs that you already know and trust.",
        )
        set_help(
            self.source_primary_button,
            "Use selected",
            "Opens the place in Melodex where the selected source or plugin is actually used. If setup is required, this button opens setup instead.",
        )
        actions.addWidget(local)
        actions.addWidget(directory)
        actions.addWidget(streams)
        actions.addStretch(1)
        actions.addWidget(self.source_primary_button)
        l.addLayout(actions)

        feature_picker=QFrame()
        feature_picker.setObjectName("pluginFeaturePicker")
        feature_l=QHBoxLayout(feature_picker)
        feature_l.setContentsMargins(14,10,14,10)
        feature_l.setSpacing(8)
        feature_text=QVBoxLayout()
        feature_text.setSpacing(1)
        feature_title=QLabel("What would you like to add?")
        feature_title.setObjectName("pluginFeatureTitle")
        feature_subtitle=QLabel(
            "Jump straight to plugins for a particular job."
        )
        feature_subtitle.setObjectName("pluginFeatureSubtitle")
        feature_text.addWidget(feature_title)
        feature_text.addWidget(feature_subtitle)
        feature_l.addLayout(feature_text,1)

        self.source_feature_buttons={}
        for label,capability in (
            ("More music","search"),
            ("Lyrics","lyrics"),
            ("Artwork","artwork"),
            ("Recommendations","recommendations"),
            ("Context","context"),
        ):
            button=QPushButton(label)
            button.setObjectName("featureChip")
            button.clicked.connect(
                lambda _checked=False, value=capability:self._plugin_directory(value)
            )
            self.source_feature_buttons[capability]=button
            feature_l.addWidget(button)
        l.addWidget(feature_picker)

        self.sources_list=QListWidget()
        self.sources_list.setObjectName("sourcesList")
        self.sources_list.setSpacing(5)
        self.sources_list.itemSelectionChanged.connect(self._source_selection_changed)
        l.addWidget(self.sources_list,1)

        self.source_hint=QLabel(
            "Select a source to see what you can do with it. Technical controls are hidden unless Power tools is enabled."
        )
        self.source_hint.setWordWrap(True)
        self.source_hint.setStyleSheet("color:#8793a4")
        l.addWidget(self.source_hint)

        self.legacy_source_notice=QLabel()
        self.legacy_source_notice.setWordWrap(True)
        self.legacy_source_notice.setStyleSheet(
            "color:#d5b26f;background:#241d12;border:1px solid #4f3d1d;"
            "border-radius:8px;padding:8px"
        )
        self.legacy_source_notice.hide()
        l.addWidget(self.legacy_source_notice)

        self.source_power_panel = QFrame()
        self.source_power_panel.setObjectName("powerPanel")
        power=QVBoxLayout(self.source_power_panel)
        power.setContentsMargins(14,12,14,12)
        power.setSpacing(8)

        title=QLabel("Power tools")
        title.setStyleSheet("font-size:15px;font-weight:700")
        power.addWidget(title)

        provider_row=QHBoxLayout()
        jam=QPushButton("Jamendo settings…")
        jam.clicked.connect(self._jamendo_settings)
        inst=QPushButton("Install .mdxprovider…")
        inst.clicked.connect(self._install_provider)
        ext=QPushButton("Install .mdxplugin…")
        ext.clicked.connect(self._install_extension)
        bridge=QPushButton("Provider Bridge…")
        bridge.clicked.connect(self._bridge_dialog)
        diagnostics=QPushButton("Export diagnostics…")
        diagnostics.clicked.connect(self._export_diagnostics)
        provider_row.addWidget(jam)
        provider_row.addWidget(inst)
        provider_row.addWidget(ext)
        provider_row.addWidget(bridge)
        provider_row.addWidget(diagnostics)
        provider_row.addStretch(1)
        power.addLayout(provider_row)

        priority=QHBoxLayout()
        up=QPushButton("Prefer source ↑")
        down=QPushButton("Prefer source ↓")
        configure=QPushButton("Configure selected…")
        configure.clicked.connect(self._configure_selected_plugin)
        toggle_ext=QPushButton("Enable / disable extension")
        toggle_ext.clicked.connect(self._toggle_extension)
        remove_ext=QPushButton("Remove extension")
        remove_ext.clicked.connect(self._remove_extension)
        test_plugin=QPushButton("Test selected")
        test_plugin.clicked.connect(self._test_selected_plugin)
        up.clicked.connect(lambda:self._move_source(-1))
        down.clicked.connect(lambda:self._move_source(1))
        priority.addWidget(up)
        priority.addWidget(down)
        priority.addWidget(configure)
        priority.addWidget(test_plugin)
        priority.addWidget(toggle_ext)
        priority.addStretch(1)
        power.addLayout(priority)

        provider_actions=QHBoxLayout()
        remove_provider=QPushButton("Remove selected provider")
        remove_provider.clicked.connect(self._remove_provider)
        restore_bundled=QPushButton("Restore bundled sources")
        restore_bundled.clicked.connect(self._restore_bundled_sources)
        provider_actions.addWidget(remove_provider)
        provider_actions.addWidget(remove_ext)
        provider_actions.addWidget(restore_bundled)
        provider_actions.addStretch(1)
        power.addLayout(provider_actions)

        self.source_power_panel.setVisible(self.power_toggle.isChecked())
        l.addWidget(self.source_power_panel)


    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange and hasattr(self, "living_canvas"):
            self.living_canvas.set_window_minimized(self.isMinimized())

    def open_page(self, name: str):
        if name not in self.pages:
            return
        interaction = (
            self.responsiveness.begin_interaction(f"navigate:{name}")
            if hasattr(self, "responsiveness")
            else None
        )
        self._navigation_generation += 1
        generation = self._navigation_generation
        self.current_page=name
        self.stack.setCurrentWidget(self.pages[name])
        self._update_nav_state(name)
        self.pages[name].update()
        self.motion.settle(
            self.page_titles.get(name),
            duration_ms=FAST_MOTION_MS,
            start_opacity=0.88,
        )
        if interaction is not None:
            self.responsiveness.end_interaction(interaction)

        # Navigation acknowledgement and page population are separate phases.
        # Give Qt one short frame to paint the destination shell before any
        # refresh work starts. Rapid navigation invalidates stale callbacks.
        QTimer.singleShot(
            self._page_refresh_delay_ms,
            lambda page=name, token=generation: self._populate_page_if_current(
                page,
                token,
            ),
        )

    def _populate_page_if_current(self, name: str, generation: int) -> None:
        if (
            self._closing
            or generation != self._navigation_generation
            or name != self.current_page
        ):
            return

        if name=="home":
            self._show_home()
        elif name=="library":
            self._refresh_library()
            self._refresh_plugin_presence()
        elif name=="album_wall":
            self._refresh_album_wall()
        elif name=="music_map":
            self._refresh_music_map()
        elif name=="sources":
            self._refresh_sources()
            QTimer.singleShot(0, self._refresh_source_config_statuses_async)
        elif name=="moments":
            self._refresh_moments()
        elif name=="journeys":
            self._refresh_journeys()
        elif name=="playlists":
            self._refresh_playlists()
        elif name=="for_you":
            self._refresh_taste()
            self._refresh_plugin_presence()
        elif name=="discover":
            self._refresh_source_combo()
            self._refresh_plugin_presence()
        elif name=="now_playing":
            self._refresh_plugin_presence()

    def _update_nav_state(self, page: str) -> None:
        parent = {
            "home":"home",
            "for_you":"home",
            "now_playing":"home",
            "library":"library",
            "moments":"library",
            "explore":"explore",
            "discover":"explore",
            "album_wall":"explore",
            "music_map":"explore",
            "ask":"explore",
            "journeys":"journeys",
            "playlists":"playlists",
            "sources":"sources",
        }.get(str(page or ""), "")
        for key,button in getattr(self,"nav_buttons",{}).items():
            active = key == parent
            if bool(button.property("active")) == active:
                continue
            button.setProperty("active",active)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _show_home(self):
        self._refresh_taste()
        count=len(self.providers.local_catalog())
        src=len(self.providers.providers)
        ext=len(self.providers.extensions())
        flow_text = (
            "Flow analysis ready"
            if self.flow.analysis_available
            else "metadata mode; install ffmpeg for deeper sonic analysis"
        )
        self.home_status.setText(
            f"{count:,} local tracks · {src} music sources · {ext} plugin"
            f"{'s' if ext != 1 else ''} · {flow_text}"
        )
        if hasattr(self,"home_primary_button"):
            if count:
                self.home_primary_button.setText("▶  Play something")
                set_help(
                    self.home_primary_button,
                    "Play something",
                    "Builds a balanced one-hour session from your local library using your listening history and Flow when available.",
                )
            else:
                self.home_primary_button.setText("+  Add my music")
                set_help(
                    self.home_primary_button,
                    "Add your music",
                    "Choose a folder of music on this computer. Melodex indexes it locally and does not upload your audio.",
                )
        self._refresh_home_continue()

    def _home_primary_action(self) -> None:
        if self.providers.local_catalog():
            self._play_for_me("balanced",60,0.35)
        else:
            self._choose_music_folder()

    def _refresh_home_continue(self) -> None:
        if not hasattr(self,"home_continue_cover"):
            return
        recent = self.state.recent_tracks(1)
        track = dict(self.current_track or (recent[0] if recent else {}))
        self.home_recent_track = track
        if not track:
            self.home_continue_cover.set_cover("",title="Your music",key="empty-home")
            self.home_continue_title.setText("Nothing played yet")
            self.home_continue_meta.setText(
                "Choose Play something or browse My Music. Your recent listening will appear here."
            )
            self.home_continue_button.setEnabled(False)
            return
        title=str(track.get("title") or "Unknown track")
        artist=str(track.get("artist") or "Unknown artist")
        album=str(track.get("album") or "")
        self.home_continue_title.setText(title)
        self.home_continue_meta.setText(artist + (f"  ·  {album}" if album else ""))
        self.home_continue_button.setEnabled(True)
        self.home_continue_cover.set_cover("",title=album or title,key=UserState.track_key(track))
        token=UserState.track_key(track)
        self._run_async(
            lambda:self.metadata.local_artwork(track),
            lambda result:self._home_continue_art_loaded(token,result),
        )

    def _home_continue_art_loaded(self, token: str, result: object) -> None:
        current=UserState.track_key(dict(getattr(self,"home_recent_track",{}) or {}))
        if token!=current or not isinstance(result,dict):
            return
        path=str(result.get("path") or "")
        self.home_continue_cover.set_cover(
            path,
            title=str(self.home_recent_track.get("album") or self.home_recent_track.get("title") or ""),
            key=token,
        )
        current=dict(self.current_track or {})
        if current and token==UserState.track_key(current) and hasattr(self,"player_cover"):
            self.player_cover.set_cover(
                path,
                title=str(current.get("album") or current.get("title") or ""),
                key=token,
            )

    def _home_continue_play(self) -> None:
        track=dict(getattr(self,"home_recent_track",{}) or {})
        if track:
            self.player.set_queue([track],0,True)

    def _power_changed(self, _, announce: bool = True):
        enabled = self.power_toggle.isChecked()
        self.state.set_bool("power_tools",enabled)
        if hasattr(self, "source_power_panel"):
            self.source_power_panel.setVisible(enabled)
        if hasattr(self, "player_power_actions"):
            self.player_power_actions.setVisible(enabled)
        # Spatial browsing uses its own progressive disclosures. Global Power
        # tools must not cover Album Wall or Music Map with controls.
        if announce:
            self.statusBar().showMessage(
                "Power tools enabled" if enabled else "Power tools hidden",
                2500,
            )

    def _open_command_palette(self) -> None:
        actions=[
            ("Home","Start listening and see recent music.",lambda:self.open_page("home")),
            ("My Music","Browse albums, artists and tracks.",lambda:self.open_page("library")),
            ("Explore","Search, Album Wall and Music Map.",lambda:self.open_page("explore")),
            ("Search everything","Search all connected music sources.",lambda:self.open_page("discover")),
            ("Album Wall","Browse your collection spatially.",lambda:self.open_page("album_wall")),
            ("Music Map","Explore track relationships and routes.",lambda:self.open_page("music_map")),
            ("Now Playing","Open artwork, lyrics and visuals.",lambda:self.open_page("now_playing")),
            ("Journeys","Open saved listening journeys.",lambda:self.open_page("journeys")),
            ("Playlists","Open saved and imported playlists.",lambda:self.open_page("playlists")),
            ("Sources & plugins","Manage where Melodex finds music.",lambda:self.open_page("sources")),
            ("Ask Melodex","Open optional natural-language control.",lambda:self.open_page("ask")),
            ("Add music folder","Choose a local music folder.",self._choose_music_folder),
            ("Analyse local library","Analyse sonic features locally for Flow and maps.",self._analyse_library_for_intelligence),
        ]
        CommandPaletteDialog(actions,self).exec()

    def _refresh_source_combo(self):
        current=self.search_source.currentData(); self.search_source.clear(); self.search_source.addItem("All sources","all")
        for pid in self.providers.searchable_provider_ids():
            p=self.providers.providers[pid]
            self.search_source.addItem(p.info.name,pid)
        idx=self.search_source.findData(current); self.search_source.setCurrentIndex(idx if idx>=0 else 0)

    def _refresh_sources(self):
        self.sources_list.clear()

        def heading(text: str) -> None:
            item=QListWidgetItem(str(text).upper())
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(QColor("#718096"))
            self.sources_list.addItem(item)

        def add_provider(pid: str, *, origin: str, section_kind: str) -> None:
            p=self.providers.providers[pid]
            name=p.info.name.replace(" (reference provider)","")
            if pid=="local":
                count=len(self.providers.local_catalog())
                status=f"{count:,} tracks" if count else "Add music"
                kind="Your library"
                icon_key="local"
            elif pid=="jamendo":
                configured=bool(str(self.providers.settings.get("jamendo_client_id","")).strip())
                status="Ready" if configured else "Setup needed"
                kind="Optional catalogue"
                icon_key="provider"
            elif pid=="streams":
                count=len(self.providers.user_streams())
                status=f"{count} stream" if count==1 else f"{count} streams"
                kind="Your links"
                icon_key="stream"
            else:
                installation=self.providers.installation_record(pid)
                config_status=(
                    self.providers.plugin_config.cached_status(
                        pid, p.info.configuration
                    )
                    if p.info.configuration else {"ready":True}
                )
                health=self.providers.plugin_health(pid, cached_config=True)
                health_state=str(health.get("status") or "untested")
                config_ready=config_status.get("ready",True)
                if config_ready is None:
                    status="Checking…"
                elif config_ready is False:
                    status="Setup needed"
                elif health_state in {"error","stopped","unhealthy","unavailable"}:
                    status="Needs attention"
                elif health_state in {"ready","ok"}:
                    status="Ready"
                elif health_state=="disabled":
                    status="Disabled"
                else:
                    status="Not tested"
                caps=[str(x) for x in list(p.info.capabilities or []) if x]
                if "recommendations" in caps and "search" not in caps:
                    kind="Recommendations"
                    icon_key="recommendation"
                elif "search" in caps:
                    kind="Music source"
                    icon_key="radio" if any(
                        token in name.casefold() for token in ("radio","somafm")
                    ) else "provider"
                else:
                    kind=section_kind
                    icon_key="provider"

            friendly_descriptions={
                "local":"Your own music on this computer. Nothing is uploaded.",
                "streams":"Direct radio or audio links that you add yourself.",
                "jamendo":"Optional connection to Jamendo's independent-music catalogue.",
            }
            lower_name=name.casefold()
            if "internet archive" in lower_name:
                description="Explore recordings, live music and spoken audio from Internet Archive."
            elif "librivox" in lower_name:
                description="Public-domain audiobooks read by volunteers."
            elif "radio browser" in lower_name:
                description="Search a worldwide community directory of internet radio stations."
            elif "somafm" in lower_name:
                description="Curated listener-supported internet radio from SomaFM."
            elif "wikimedia" in lower_name:
                description="Openly licensed and public-domain audio from Wikimedia Commons."
            elif "ccmixter" in lower_name:
                description="Creative Commons music, samples and remixes."
            else:
                description=friendly_descriptions.get(pid,str(p.info.description or ""))

            item=QListWidgetItem()
            item.setData(Qt.UserRole,pid)
            card=SourceCard(
                name,
                description,
                status,
                kind=kind,
                icon_key=icon_key,
                origin=origin,
            )
            item.setSizeHint(card.sizeHint())
            self.sources_list.addItem(item)
            self.sources_list.setItemWidget(item,card)

        order=self.providers.provider_order()
        builtins=[pid for pid in ("local","streams","jamendo") if pid in self.providers.providers]
        bundled=[
            pid for pid in order
            if pid not in builtins and self.providers.is_bundled_provider(pid)
        ]
        optional=[
            pid for pid in order
            if pid not in builtins and pid not in bundled
        ]

        heading("Your music & connections")
        for pid in builtins:
            add_provider(
                pid,
                origin="Built in" if pid!="jamendo" else "Optional",
                section_kind="Built in",
            )

        if bundled:
            heading("Included with Melodex")
            for pid in bundled:
                add_provider(pid,origin="Included",section_kind="Included source")

        if optional:
            heading("Installed music plugins")
            for pid in optional:
                installation=self.providers.installation_record(pid)
                method=str(installation.get("method") or "")
                origin="Registry" if method=="registry" else "Manual" if method=="manual" else "Installed"
                add_provider(pid,origin=origin,section_kind="Plugin source")

        if hasattr(self,"source_summary_library"):
            local_count=len(self.providers.local_catalog())
            self.source_summary_library.setText(
                f"{local_count:,} track{'s' if local_count != 1 else ''}"
            )
            self.source_summary_included.setText(
                f"{len(bundled)} source{'s' if len(bundled) != 1 else ''}"
            )

        extensions=self.providers.extensions(cached_config=True)
        if hasattr(self,"source_summary_enhancements"):
            self.source_summary_enhancements.setText(
                f"{len(extensions)} installed" if extensions else "None installed"
            )

        if extensions:
            heading("Installed enhancements")
            for extension in extensions:
                extension_id=str(extension.get("id") or "")
                enabled=bool(extension.get("enabled",True))
                config_status=dict(extension.get("configuration_status") or {})
                health=self.providers.plugin_health(
                    extension_id,
                    cached_config=True,
                )
                health_state=str(health.get("status") or "untested")
                config_ready=config_status.get("ready",True)
                if not enabled:
                    status="Disabled"
                elif config_status.get("declared") and config_ready is None:
                    status="Checking…"
                elif config_status.get("declared") and config_ready is False:
                    status="Setup needed"
                elif health_state in {"error","stopped","unhealthy","unavailable"}:
                    status="Needs attention"
                elif health_state in {"ready","ok"}:
                    status="Ready"
                else:
                    status="Not tested"

                raw_capabilities=[str(x) for x in list(extension.get("capabilities") or []) if x]
                capabilities=", ".join(self._capability_label(x) for x in raw_capabilities) or "Adds extra Melodex capabilities"
                description=str(extension.get("description") or capabilities)
                if "library_suggestions" in raw_capabilities:
                    kind="Recommendations"; icon_key="recommendation"
                elif "artwork" in raw_capabilities:
                    kind="Artwork"; icon_key="artwork"
                elif "lyrics" in raw_capabilities:
                    kind="Lyrics"; icon_key="lyrics"
                elif "context" in raw_capabilities:
                    kind="Context"; icon_key="context"
                elif any(x in raw_capabilities for x in ("metadata","identity")):
                    kind="Metadata"; icon_key="metadata"
                else:
                    kind="Enhancement"; icon_key="plugin"

                installation=self.providers.installation_record(extension_id)
                method=str(installation.get("method") or "")
                origin="Registry" if method=="registry" else "Manual" if method=="manual" else "Installed"

                item=QListWidgetItem()
                item.setData(Qt.UserRole,"extension:"+extension_id)
                card=SourceCard(
                    str(extension.get("name") or extension_id),
                    description,
                    status,
                    kind=kind,
                    icon_key=icon_key,
                    origin=origin,
                )
                item.setSizeHint(card.sizeHint())
                self.sources_list.addItem(item)
                self.sources_list.setItemWidget(item,card)

        if hasattr(self,"sources_overview"):
            active_included=len(bundled)
            optional_count=len(optional)+len(extensions)
            setup_needed=0
            for pid in optional+bundled:
                provider=self.providers.providers.get(pid)
                if provider is not None and provider.info.configuration:
                    state=self.providers.plugin_config.cached_status(
                        pid,
                        provider.info.configuration,
                    )
                    if state.get("ready") is False:
                        setup_needed+=1
            for extension in extensions:
                state=dict(extension.get("configuration_status") or {})
                if state.get("declared") and state.get("ready") is False:
                    setup_needed+=1
            summary=(
                f"{len(builtins)} built-in connections · "
                f"{active_included} included sources · "
                f"{optional_count} installed optional plugin{'s' if optional_count!=1 else ''}"
            )
            if setup_needed:
                summary+=f" · {setup_needed} need setup"
            self.sources_overview.setText(summary)

        legacy=self.providers.quarantined_legacy_providers()
        if hasattr(self,"legacy_source_notice"):
            if legacy:
                names=", ".join(str(row.get("name") or row.get("id") or "legacy provider") for row in legacy)
                self.legacy_source_notice.setText(
                    "Legacy development provider disabled: "
                    + names
                    + ". It is not part of public Melodex and will not be searched or played. "
                    "Its old local files have been left untouched."
                )
                self.legacy_source_notice.show()
            else:
                self.legacy_source_notice.hide()

        self._refresh_source_combo()
        self._source_selection_changed()


    def _refresh_source_config_statuses_async(self) -> None:
        """Validate plugin configuration off the Qt thread, then refresh badges."""
        if self._source_config_refresh_in_progress or self._closing:
            return
        self._source_config_refresh_in_progress = True

        def load() -> None:
            for pid in self.providers.provider_order():
                provider=self.providers.providers.get(pid)
                if (
                    provider is not None
                    and pid not in {"local","jamendo","streams"}
                    and provider.info.configuration
                ):
                    self.providers.plugin_config.status(
                        pid,
                        provider.info.configuration,
                    )
            # Extensions share the same configuration broker. Calling the full
            # status path here warms secret-presence state without blocking Qt.
            self.providers.extensions(cached_config=False)

        def done(_result) -> None:
            self._source_config_refresh_in_progress = False
            if self.current_page == "sources":
                self._refresh_sources()
                self._refresh_plugin_presence()

        def failed(_error: str) -> None:
            self._source_config_refresh_in_progress = False
            if self.current_page == "sources":
                self.statusBar().showMessage(
                    "Some source configuration checks are still unavailable",
                    4000,
                )

        self._run_async(load, done, failed)

    @staticmethod
    def _capability_label(capability: str) -> str:
        return {
            "library_suggestions":"recommendations",
            "artwork":"artwork",
            "lyrics":"lyrics",
            "context":"context",
            "metadata":"metadata",
            "identity":"identity",
        }.get(str(capability or ""), str(capability or "").replace("_"," "))

    def _extension_record(self, extension_id: str) -> dict[str,Any]:
        return next(
            (
                dict(row)
                for row in self.providers.extensions(cached_config=True)
                if str(row.get("id") or "") == str(extension_id or "")
            ),
            {},
        )

    def _plugin_needs_setup_here(self, plugin_id: str) -> bool:
        if not plugin_id:
            return False
        if plugin_id.startswith("extension:"):
            row=self._extension_record(plugin_id.split(":",1)[1])
            status=dict(row.get("configuration_status") or {})
            return bool(
                status.get("declared")
                and status.get("ready") is False
            )
        provider=self.providers.providers.get(plugin_id)
        if provider is None or not provider.info.configuration:
            return False
        status=self.providers.plugin_config.cached_status(
            plugin_id,
            provider.info.configuration,
        )
        return status.get("ready") is False

    def _source_selection_changed(self) -> None:
        if hasattr(self, "responsiveness"):
            self.responsiveness.mark_action("sources:selection")
        item=self.sources_list.currentItem() if hasattr(self,"sources_list") else None
        key=str(item.data(Qt.UserRole) or "") if item else ""
        enabled=bool(key)
        if hasattr(self,"source_primary_button"):
            self.source_primary_button.setEnabled(enabled)
        if not hasattr(self,"source_hint"):
            return
        if not key:
            self.source_primary_button.setText("Use selected")
            self.source_hint.setText(
                "Select a source or plugin. The main button will show where it is actually used in Melodex; technical controls stay under Power tools."
            )
            return

        if key=="local":
            self.source_primary_button.setText("Add music")
            self.source_hint.setText(
                "This computer · add another folder here, or browse the collection in My Music."
            )
            return
        if key=="jamendo":
            if self._plugin_needs_setup_here(key) or not str(self.providers.settings.get("jamendo_client_id","")).strip():
                self.source_primary_button.setText("Set up Jamendo")
                self.source_hint.setText(
                    "Jamendo is an optional online source. Set it up once, then use it from Explore → Search everything."
                )
            else:
                self.source_primary_button.setText("Search Jamendo")
                self.source_hint.setText(
                    "Jamendo is a music source. Use it in Explore → Search everything; Melodex will open Search already filtered to Jamendo."
                )
            return
        if key=="streams":
            self.source_primary_button.setText("Manage streams")
            self.source_hint.setText(
                "My streams contains direct radio/audio URLs you add yourself."
            )
            return

        if key.startswith("extension:"):
            extension_id=key.split(":",1)[1]
            row=self._extension_record(extension_id)
            capabilities=[str(x) for x in list(row.get("capabilities") or []) if x]
            if self._plugin_needs_setup_here(key):
                self.source_primary_button.setText("Set up plugin")
                self.source_hint.setText(
                    "This plugin is installed but needs setup before Melodex can use it."
                )
                return
            self.source_primary_button.setText("Use plugin")
            labels=", ".join(self._capability_label(x) for x in capabilities) or "extra capabilities"
            self.source_hint.setText(
                f"This plugin provides {labels}. Choose Use plugin and Melodex will open the feature where it participates."
            )
            return

        provider=self.providers.providers.get(key)
        if self._plugin_needs_setup_here(key):
            self.source_primary_button.setText("Set up source")
            self.source_hint.setText(
                "This provider is installed but needs setup before it can search or play."
            )
        elif provider is not None and "search" in list(provider.info.capabilities or []):
            self.source_primary_button.setText("Search this source")
            self.source_hint.setText(
                "This provider is used from Explore → Search everything. The button will open Search already filtered to this source."
            )
        else:
            self.source_primary_button.setText("Use source")
            self.source_hint.setText(
                "This provider is active. Choose Use source to open the closest matching Melodex feature."
            )

    def _open_provider_search(self, provider_id: str) -> None:
        self.open_page("discover")
        self._refresh_source_combo()
        index=self.search_source.findData(str(provider_id or ""))
        if index >= 0:
            self.search_source.setCurrentIndex(index)
        self.search_box.setFocus()
        provider=self.providers.providers.get(provider_id)
        name=provider.info.name if provider is not None else provider_id
        self.statusBar().showMessage(
            f"Search ready · results will come from {name}",
            4500,
        )

    def _use_extension(self, extension_id: str) -> None:
        row=self._extension_record(extension_id)
        capabilities=[str(x) for x in list(row.get("capabilities") or []) if x]
        name=str(row.get("name") or extension_id)

        if "library_suggestions" in capabilities:
            self.open_page("for_you")
            self.statusBar().showMessage(
                f"{name} participates here · use More like current, Forgotten favourites, Bridge current → next or Find a detour",
                7000,
            )
            return
        if "artwork" in capabilities:
            self.open_page("library")
            self.statusBar().showMessage(
                f"{name} is used by artwork enrichment · choose Find missing artwork in My Music",
                6500,
            )
            return
        if any(cap in capabilities for cap in ("lyrics","context","metadata","identity")):
            self.open_page("now_playing")
            labels=", ".join(self._capability_label(x) for x in capabilities)
            self.statusBar().showMessage(
                f"{name} provides {labels} automatically for the current track",
                6500,
            )
            return

        QMessageBox.information(
            self,
            "Plugin is active",
            f"{name} is enabled. It does not declare a separate user-facing action; Melodex will call it when one of its capabilities is needed.",
        )

    def _source_primary_action(self) -> None:
        item=self.sources_list.currentItem() if hasattr(self,"sources_list") else None
        key=str(item.data(Qt.UserRole) or "") if item else ""
        if not key:
            return
        if key=="local":
            self._choose_music_folder()
            return
        if key=="jamendo":
            if self._plugin_needs_setup_here(key) or not str(self.providers.settings.get("jamendo_client_id","")).strip():
                self._jamendo_settings()
            else:
                self._open_provider_search(key)
            return
        if key=="streams":
            self._user_streams_dialog()
            return
        if key.startswith("extension:"):
            extension_id=key.split(":",1)[1]
            if self._plugin_needs_setup_here(key):
                self._configure_selected_plugin()
            else:
                self._use_extension(extension_id)
            return

        if self._plugin_needs_setup_here(key):
            self._configure_selected_plugin()
            return
        provider=self.providers.providers.get(key)
        if provider is not None and "search" in list(provider.info.capabilities or []):
            self._open_provider_search(key)
        else:
            self._test_selected_plugin()

    def _move_source(self, delta):
        item=self.sources_list.currentItem()
        if not item:return
        pid=str(item.data(Qt.UserRole) or ""); order=self.providers.provider_order()
        if pid not in order:return
        i=order.index(pid); j=max(0,min(len(order)-1,i+int(delta)))
        if i==j:return
        order[i],order[j]=order[j],order[i]; self.providers.set_provider_order(order); self._refresh_sources(); self.sources_list.setCurrentRow(j)
        self.statusBar().showMessage("Source priority updated",2500)

    def _refresh_library(self):
        if hasattr(self,"library_browser"):
            self.library_browser.set_catalog(
                self.providers.local_catalog(),
                revision=self.providers.local_catalog_revision(),
            )

    def _play_library_track(self, track: object) -> None:
        if not isinstance(track,dict):
            return
        tracks=self.providers.local_catalog()
        tid=str(track.get("track_id") or "")
        index=next(
            (i for i,item in enumerate(tracks) if str(item.get("track_id") or "")==tid),
            0,
        )
        self.player.set_queue(tracks,index,True)

    def _play_library_artist(self, artist: object) -> None:
        if not isinstance(artist,dict):
            return
        tracks=[dict(x) for x in list(artist.get("tracks") or []) if isinstance(x,dict)]
        if tracks:
            self.player.set_queue(tracks,0,True)

    def _queue_library_track(self, track: object) -> None:
        if not isinstance(track,dict):
            return
        if not self.player.queue:
            self.player.set_queue([dict(track)],0,False)
        else:
            self.player.append_queue([dict(track)],autoplay=False)
        self.statusBar().showMessage(
            f"Queued {track.get('title') or 'track'}",
            3000,
        )

    def _edit_local_metadata(self, track: object) -> None:
        if not isinstance(track,dict) or not str(track.get("local_path") or "").strip():
            QMessageBox.information(
                self,
                "Local music only",
                "Metadata corrections are currently available for music stored on this computer.",
            )
            return

        original=dict(track)
        dialog=QDialog(self)
        dialog.setWindowTitle("Correct track details")
        dialog.resize(520,360)
        layout=QVBoxLayout(dialog)
        layout.setContentsMargins(22,20,22,18)
        title=QLabel("Correct track details")
        title.setStyleSheet("font-size:20px;font-weight:700")
        layout.addWidget(title)
        note=QLabel(
            "These corrections are stored by Melodex and survive rescans. "
            "Your original audio file and its embedded tags are not changed."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#9aa4b8")
        layout.addWidget(note)

        form=QFormLayout()
        fields={}
        for key,label in (
            ("artist","Artist"),
            ("title","Track title"),
            ("album","Album"),
            ("album_artist","Album artist"),
            ("year","Year"),
            ("genre","Genre"),
        ):
            edit=QLineEdit()
            value=str(original.get(key) or "")
            if key=="artist" and value.casefold().strip()=="unknown artist":
                value=""
            edit.setText(value)
            fields[key]=edit
            form.addRow(label+":",edit)
        layout.addLayout(form)

        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        reset=buttons.addButton("Use file tags again",QDialogButtonBox.ResetRole)
        set_help(
            reset,
            "Remove Melodex correction",
            "Forget the local correction for this file and use its embedded/file metadata again.",
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        reset.clicked.connect(lambda:self._reset_local_metadata_dialog(dialog,original))
        layout.addWidget(buttons)

        if dialog.exec()!=QDialog.Accepted:
            return

        changes={key:edit.text().strip() for key,edit in fields.items()}
        try:
            updated=self.providers.update_local_metadata(original,changes)
        except Exception as exc:
            QMessageBox.warning(self,"Could not save correction",str(exc))
            return
        self._apply_local_metadata_update(original,updated)
        self.statusBar().showMessage(
            f"Saved Melodex metadata correction for {updated.get('title') or original.get('title') or 'track'}",
            4500,
        )

    def _reset_local_metadata_dialog(self, dialog: QDialog, track: dict[str,Any]) -> None:
        if self.providers.clear_local_metadata_correction(track):
            self.statusBar().showMessage(
                "Removed Melodex metadata correction · refreshing tags in the background…"
            )
            self._start_local_scan("metadata reset")
        dialog.reject()

    def _apply_local_metadata_update(
        self,
        original: dict[str,Any],
        updated: dict[str,Any],
    ) -> None:
        path=str(original.get("local_path") or "")
        for index,item in enumerate(list(self.player.queue)):
            if str(item.get("local_path") or "")==path:
                self.player.queue[index]={**item,**updated}
        self.player.queueChanged.emit(list(self.player.queue))

        if str(self.current_track.get("local_path") or "")==path:
            self.current_track={**self.current_track,**updated}
            self.now_title.setText(str(self.current_track.get("title") or "Unknown track"))
            pieces=[str(self.current_track.get("artist") or "Unknown artist")]
            album=str(self.current_track.get("album") or "")
            if album:
                pieces.append(album)
            self.now_meta.setText("   ·   ".join(pieces))
            if hasattr(self,"rich_now"):
                self.rich_now.set_track(dict(self.current_track))
        self._refresh_library()

    def _queue_album_data(self, album: object) -> None:
        if not isinstance(album,dict):
            return
        tracks=[dict(x) for x in list(album.get("tracks") or []) if isinstance(x,dict)]
        if not tracks:
            return
        if not self.player.queue:
            self.player.set_queue(tracks,0,False)
        else:
            self.player.append_queue(tracks,autoplay=False)
        self.statusBar().showMessage(
            f"Queued {len(tracks)} tracks from {album.get('title') or 'album'}",
            3500,
        )

    def _library_artwork_requested(self, requests: object) -> None:
        rows=[dict(x) for x in list(requests or []) if isinstance(x,dict)]
        if not rows:
            return
        keys=[str(row.get("key") or "") for row in rows if str(row.get("key") or "")]
        def load():
            result={}
            for row in rows:
                key=str(row.get("key") or "")
                track=dict(row.get("track") or {})
                if key and track:
                    info=self.metadata.local_artwork(track)
                    result[key]=str(info.get("path") or "")
            return result
        def failed(error: str) -> None:
            self.library_browser.cached_artwork_batch_failed("albums",keys)
            self.statusBar().showMessage(
                f"Cached artwork refresh paused · {error}",
                3500,
            )
        self._run_async(
            load,
            self.library_browser.set_artwork,
            failed,
            priority="visible",
            lane="disk",
            label="viewport-album-artwork",
        )

    def _library_online_artwork_requested(self, requests: object) -> None:
        rows=[dict(x) for x in list(requests or []) if isinstance(x,dict)]
        if not rows:
            return

        self.statusBar().showMessage(
            f"Finding album artwork · {len(rows)} at a time"
        )

        def lookup_one(row: dict[str,Any]) -> dict[str,Any]:
            key=str(row.get("key") or "")
            track=dict(row.get("track") or {})
            if not key or not track:
                return {"key":key,"path":"","status":"error","error":"Missing album lookup data"}
            try:
                local=self.metadata.local_artwork(track)
                path=str(local.get("path") or "")
                artwork_info=dict(local)
                if not path:
                    identity=self.metadata.identify(track)
                    artwork_info=self.metadata.artwork(track,identity)
                    path=str(artwork_info.get("path") or "")
                if path:
                    match_info=(
                        dict(artwork_info.get("match") or {})
                        if isinstance(artwork_info.get("match"),dict)
                        else {}
                    )
                    for sibling in list(row.get("tracks") or []):
                        if not isinstance(sibling,dict):
                            continue
                        self.metadata.remember_artwork(
                            sibling,
                            path,
                            source=str(artwork_info.get("source") or ""),
                            source_url=str(artwork_info.get("source_url") or ""),
                            attribution=str(artwork_info.get("attribution") or ""),
                            license_name=str(
                                artwork_info.get("license_name")
                                or artwork_info.get("license")
                                or ""
                            ),
                            match_method=str(match_info.get("method") or ""),
                            match_confidence=(
                                float(match_info.get("confidence"))
                                if match_info.get("confidence") is not None
                                else None
                            ),
                        )
                    return {
                        "key":key,
                        "path":path,
                        "status":"found",
                        "source":str(artwork_info.get("source") or ""),
                    }
                return {"key":key,"path":"","status":"no_match","error":""}
            except Exception as exc:
                return {"key":key,"path":"","status":"error","error":str(exc)}

        def load():
            return [lookup_one(row) for row in rows]

        def apply(result):
            outcomes=[dict(x) for x in list(result or []) if isinstance(x,dict)]
            self.library_browser.set_artwork({
                str(row.get("key") or ""):str(row.get("path") or "")
                for row in outcomes
                if str(row.get("path") or "")
            })
            self.library_browser.finish_album_artwork_lookup_batch(outcomes)
            snapshot=self.library_browser.artwork_lookup_snapshot()
            self.statusBar().showMessage(
                "Album artwork · "
                f"{snapshot.get('completed',0)}/{snapshot.get('total',0)} · "
                f"found {snapshot.get('found',0)} · "
                f"no match {snapshot.get('skipped',0)} · "
                f"failed {snapshot.get('failed',0)}",
                5000 if not snapshot.get("active") else 0,
            )

        def failed(error):
            outcomes=[
                {
                    "key":str(row.get("key") or ""),
                    "path":"",
                    "status":"error",
                    "error":str(error),
                }
                for row in rows
            ]
            self.library_browser.finish_album_artwork_lookup_batch(outcomes)
            self.statusBar().showMessage(
                f"Album artwork batch failed · {error}",
                5000,
            )

        self._run_async(
            load,
            apply,
            failed,
            priority="background",
            lane="network",
            label="online-album-artwork",
        )

    def _choose_artist_photo_file(self, artist: object) -> None:
        if not isinstance(artist,dict):
            return
        name=str(artist.get("name") or "Artist").strip() or "Artist"
        path,_ = QFileDialog.getOpenFileName(
            self,
            f"Choose photo for {name}",
            "",
            "Images (*.jpg *.jpeg *.png *.webp);;All files (*)",
        )
        if not path:
            return
        remembered=self.metadata.remember_artist_photo_file(
            {"name":name},
            path,
        )
        saved=str(remembered.get("path") or "")
        if not saved:
            QMessageBox.warning(
                self,
                "Could not use image",
                "Melodex could not copy that image into its artwork cache.",
            )
            return
        key=str(artist.get("key") or "")
        if key:
            self.library_browser.set_artist_images({key:saved})
        self.statusBar().showMessage(
            f"Saved artist photo for {name}",
            4500,
        )

    def _library_cached_artist_images_requested(self, requests: object) -> None:
        rows=[dict(x) for x in list(requests or []) if isinstance(x,dict)]
        if not rows:
            return

        keys=[str(row.get("key") or "") for row in rows if str(row.get("key") or "")]
        def load():
            result={}
            for row in rows:
                key=str(row.get("key") or "")
                artist_name=str(row.get("artist") or "")
                if key and artist_name:
                    cached=self.metadata.cached_artist_photo({"name":artist_name})
                    result[key]=str(cached.get("path") or "")
            return result

        def failed(error: str) -> None:
            self.library_browser.cached_artwork_batch_failed("artists",keys)
            self.statusBar().showMessage(
                f"Cached artist-photo refresh paused · {error}",
                3500,
            )

        self._run_async(
            load,
            self.library_browser.set_artist_images,
            failed,
            priority="visible",
            lane="disk",
            label="viewport-artist-photo",
        )

    def _library_artist_images_requested(self, requests: object) -> None:
        rows=[dict(x) for x in list(requests or []) if isinstance(x,dict)]
        if not rows:
            return

        self.statusBar().showMessage(
            f"Finding artist photos · {len(rows)} at a time"
        )

        def lookup_one(row: dict[str,Any]) -> dict[str,Any]:
            key=str(row.get("key") or "")
            artist_name=str(row.get("artist") or "")
            track=dict(row.get("track") or {})
            if not key or not artist_name or not track:
                return {"key":key,"path":"","status":"error","error":"Missing artist lookup data"}
            try:
                cached=self.metadata.cached_artist_photo({"name":artist_name})
                path=str(cached.get("path") or "")
                if not path:
                    artist_mbid=str(
                        track.get("musicbrainz_artist_id")
                        or track.get("artist_mbid")
                        or ""
                    ).strip()
                    if artist_mbid:
                        info=self.metadata.artist_info(artist_mbid)
                    else:
                        info=self.metadata.resolve_artist(artist_name)
                    if info:
                        if not info.get("name"):
                            info["name"]=artist_name
                        photo=self.metadata.artist_photo(info)
                        path=str(photo.get("path") or "")
                return {
                    "key":key,
                    "path":path,
                    "status":"found" if path else "no_match",
                    "error":"",
                }
            except Exception as exc:
                return {"key":key,"path":"","status":"error","error":str(exc)}

        def load():
            return [lookup_one(row) for row in rows]

        def apply(result):
            outcomes=[dict(x) for x in list(result or []) if isinstance(x,dict)]
            self.library_browser.set_artist_images({
                str(row.get("key") or ""):str(row.get("path") or "")
                for row in outcomes
                if str(row.get("path") or "")
            })
            self.library_browser.finish_artist_image_lookup_batch(outcomes)
            snapshot=self.library_browser.artwork_lookup_snapshot()
            self.statusBar().showMessage(
                "Artist photos · "
                f"{snapshot.get('completed',0)}/{snapshot.get('total',0)} · "
                f"found {snapshot.get('found',0)} · "
                f"no match {snapshot.get('skipped',0)} · "
                f"failed {snapshot.get('failed',0)}",
                5000 if not snapshot.get("active") else 0,
            )

        def failed(error):
            outcomes=[
                {
                    "key":str(row.get("key") or ""),
                    "path":"",
                    "status":"error",
                    "error":str(error),
                }
                for row in rows
            ]
            self.library_browser.finish_artist_image_lookup_batch(outcomes)
            self.statusBar().showMessage(
                f"Artist photo batch failed · {error}",
                5000,
            )

        self._run_async(
            load,
            apply,
            failed,
            priority="background",
            lane="network",
            label="online-artist-photo",
        )

    def _refresh_journeys(self):
        if not hasattr(self,"journey_recipes_list") or not hasattr(self,"journey_runs_list"):
            return
        self.journey_recipes_list.clear()
        for record in self.state.journey_recipes():
            recipe=dict(record.get("payload") or {})
            stages=list(recipe.get("stages") or [])
            mode=str(recipe.get("routing_mode") or "balanced")
            description=str(record.get("description") or "")
            subtitle=f"{len(stages)} stage{'s' if len(stages)!=1 else ''} · {mode}"
            if description:
                subtitle+=f" · {description}"
            item=QListWidgetItem(f"{record.get('name') or 'Journey recipe'}\n{subtitle}")
            item.setData(Qt.UserRole,record)
            self.journey_recipes_list.addItem(item)
        if hasattr(self,"journey_recipes_stack"):
            self.journey_recipes_stack.setCurrentWidget(
                self.journey_recipes_list
                if self.journey_recipes_list.count()
                else self.journey_recipes_empty
            )

        self.journey_runs_list.clear()
        for run in self.state.journey_runs(80):
            events=self.state.journey_events(str(run.get("id") or ""))
            summary=summarize_journey_run(run,events)
            stamp=float(run.get("started_at") or 0)
            when=time.strftime("%Y-%m-%d %H:%M",time.localtime(stamp)) if stamp else "Unknown time"
            recipe=dict(run.get("recipe") or {})
            name=str(recipe.get("name") or "Unsaved journey")
            status=str(run.get("status") or "unknown")
            changed="adapted" if summary.get("changed") else "as designed"
            final_count=int(summary.get("final_track_count") or 0)
            original_count=int(summary.get("original_track_count") or 0)
            count=final_count or original_count
            item=QListWidgetItem(
                f"{when} · {name}\n{status} · {changed} · {count} track{'s' if count!=1 else ''} · "
                f"{len(events)} event{'s' if len(events)!=1 else ''}"
            )
            item.setData(Qt.UserRole,run)
            self.journey_runs_list.addItem(item)
        if hasattr(self,"journey_runs_stack"):
            self.journey_runs_stack.setCurrentWidget(
                self.journey_runs_list
                if self.journey_runs_list.count()
                else self.journey_runs_empty
            )

    def _selected_journey_recipe_record(self):
        item=self.journey_recipes_list.currentItem() if hasattr(self,"journey_recipes_list") else None
        data=item.data(Qt.UserRole) if item else None
        return dict(data or {}) if isinstance(data,dict) else {}

    def _selected_journey_run_record(self):
        item=self.journey_runs_list.currentItem() if hasattr(self,"journey_runs_list") else None
        data=item.data(Qt.UserRole) if item else None
        return dict(data or {}) if isinstance(data,dict) else {}

    def _journey_recipe_save_current(self):
        if not self.music_journey_stages_data:
            self.statusBar().showMessage(
                "Add Journey Designer stages before saving a recipe",3500
            ); return
        default_name=str(self.music_active_recipe.get("name") or "Journey recipe")
        name,ok=QInputDialog.getText(
            self,
            "Save journey recipe",
            "Recipe name:",
            text=default_name,
        )
        if not ok or not str(name).strip():
            return
        description,ok=QInputDialog.getText(
            self,
            "Save journey recipe",
            "Short description (optional):",
            text=str(self.music_active_recipe.get("description") or ""),
        )
        if not ok:
            return
        try:
            recipe=make_journey_recipe(
                name=str(name),
                description=str(description),
                mode=str(self.music_path_mode.currentData() or "balanced"),
                stages=list(self.music_journey_stages_data),
                ref_map=dict(self.music_map.ref_map or {}),
            )
        except Exception as exc:
            QMessageBox.warning(self,"Could not save journey recipe",str(exc)); return
        recipe_id=str(uuid.uuid4())
        self.state.save_journey_recipe(
            recipe_id,
            str(recipe.get("name") or name),
            str(recipe.get("description") or ""),
            recipe,
        )
        self.music_active_recipe_id=recipe_id
        self.music_active_recipe=dict(recipe)
        self._refresh_journeys()
        self.statusBar().showMessage(
            f"Saved journey recipe · {recipe.get('name')}",4000
        )

    def _journey_recipe_load_selected(self):
        record=self._selected_journey_recipe_record()
        if not record:
            self.statusBar().showMessage("Select a journey recipe first",3000); return
        recipe=dict(record.get("payload") or {})
        self.pending_journey_recipe={
            "id":str(record.get("id") or ""),
            "payload":recipe,
        }
        self.open_page("music_map")
        self.statusBar().showMessage("Refreshing Music Map before loading recipe…",3500)

    def _journey_recipe_import(self):
        filename,_=QFileDialog.getOpenFileName(
            self,
            "Import journey recipe",
            filter="Melodex Journey (*.mdxjourney);;JSON files (*.json)",
        )
        if not filename:
            return
        try:
            recipe=load_journey_recipe(Path(filename))
        except Exception as exc:
            QMessageBox.warning(self,"Could not import journey recipe",str(exc)); return
        recipe_id=str(uuid.uuid4())
        self.state.save_journey_recipe(
            recipe_id,
            str(recipe.get("name") or Path(filename).stem),
            str(recipe.get("description") or ""),
            recipe,
        )
        self._refresh_journeys()
        self.statusBar().showMessage(
            f"Imported journey recipe · {recipe.get('name')}",4500
        )

    def _journey_recipe_export(self):
        record=self._selected_journey_recipe_record()
        if not record:
            self.statusBar().showMessage("Select a journey recipe first",3000); return
        recipe=dict(record.get("payload") or {})
        default_name="".join(
            ch if ch.isalnum() or ch in {" ","-","_"} else "_"
            for ch in str(record.get("name") or "journey")
        ).strip() or "journey"
        filename,_=QFileDialog.getSaveFileName(
            self,
            "Export journey recipe",
            default_name+".mdxjourney",
            "Melodex Journey (*.mdxjourney)",
        )
        if not filename:
            return
        try:
            path=save_journey_recipe(Path(filename),recipe)
        except Exception as exc:
            QMessageBox.warning(self,"Could not export journey recipe",str(exc)); return
        self.statusBar().showMessage(f"Exported {path.name}",4500)

    def _journey_recipe_delete(self):
        record=self._selected_journey_recipe_record()
        if not record:
            self.statusBar().showMessage("Select a journey recipe first",3000); return
        answer=QMessageBox.question(
            self,
            "Delete journey recipe",
            f"Delete {record.get('name') or 'this recipe'}?\n\nRun history is kept.",
            QMessageBox.Yes|QMessageBox.No,
            QMessageBox.No,
        )
        if answer!=QMessageBox.Yes:
            return
        recipe_id=str(record.get("id") or "")
        self.state.delete_journey_recipe(recipe_id)
        if self.music_active_recipe_id==recipe_id:
            self.music_active_recipe_id=""
            self.music_active_recipe={}
        self._refresh_journeys()
        self.statusBar().showMessage("Journey recipe deleted",3000)

    def _apply_pending_journey_recipe(self):
        pending=self.pending_journey_recipe
        self.pending_journey_recipe=None
        if not isinstance(pending,dict):
            return
        recipe=dict(pending.get("payload") or {})
        try:
            materialized=materialize_recipe_stages(
                recipe,
                dict(self.music_map.ref_map or {}),
            )
        except Exception as exc:
            QMessageBox.warning(self,"Could not load journey recipe",str(exc)); return
        mode=str(recipe.get("routing_mode") or "balanced")
        index=self.music_path_mode.findData(mode)
        if index>=0:
            self.music_path_mode.setCurrentIndex(index)
        self.music_journey_stages_data=[
            dict(stage)
            for stage in list(materialized.get("stages") or [])
            if isinstance(stage,dict)
        ]
        self.music_active_recipe_id=str(pending.get("id") or "")
        self.music_active_recipe=dict(recipe)
        self._music_journey_render_stages()
        unresolved=[
            dict(stage)
            for stage in list(materialized.get("unresolved") or [])
            if isinstance(stage,dict)
        ]
        if unresolved:
            names=", ".join(
                str(stage.get("label") or (stage.get("selector") or {}).get("title") or "Unknown waypoint")
                for stage in unresolved[:5]
            )
            QMessageBox.warning(
                self,
                "Recipe loaded with missing waypoints",
                "The semantic stages were loaded, but these exact track waypoints "
                f"are not present on the current Music Map:\n\n{names}",
            )
        self.statusBar().showMessage(
            f"Loaded recipe · {recipe.get('name') or 'Journey recipe'} · choose start and destination",
            6000,
        )

    def _journey_run_inspect(self):
        run=self._selected_journey_run_record()
        if not run:
            self.statusBar().showMessage("Select a journey run first",3000); return
        events=self.state.journey_events(str(run.get("id") or ""))
        summary=summarize_journey_run(run,events)
        d=QDialog(self)
        d.setWindowTitle("Journey run")
        d.resize(760,640)
        lay=QVBoxLayout(d)
        recipe=dict(run.get("recipe") or {})
        title=QLabel(str(recipe.get("name") or "Journey run"))
        title.setStyleSheet("font-size:20px;font-weight:700")
        lay.addWidget(title)
        body=QTextEdit()
        body.setReadOnly(True)
        lines=[
            f"Status: {summary.get('status') or 'unknown'}",
            f"Started: {time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(float(summary.get('started_at') or 0)))}",
            f"Designed tracks: {summary.get('original_track_count') or 0}",
            f"Final tracks: {summary.get('final_track_count') or 0}",
            f"Route changed: {'yes' if summary.get('changed') else 'no'}",
            "",
            "DESIGNED ROUTE",
        ]
        lines.extend(
            f"{i+1}. {track}"
            for i,track in enumerate(list(summary.get("original_tracks") or []))
        )
        lines.extend(["","FINAL / ADAPTED ROUTE"])
        final_tracks=list(summary.get("final_tracks") or [])
        if final_tracks:
            lines.extend(f"{i+1}. {track}" for i,track in enumerate(final_tracks))
        else:
            lines.append("(no final snapshot)")
        lines.extend(["","DECISIONS"])
        decisions=list(summary.get("decisions") or [])
        lines.extend(f"• {row}" for row in decisions) if decisions else lines.append("(no adaptive decisions)")
        body.setPlainText("\n".join(lines))
        lay.addWidget(body,1)
        close=QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(d.reject); close.accepted.connect(d.accept)
        lay.addWidget(close)
        d.exec()

    def _journey_run_replay(self,which):
        run=self._selected_journey_run_record()
        if not run:
            self.statusBar().showMessage("Select a journey run first",3000); return
        which=str(which or "final")
        snapshot=dict(
            run.get("original_route")
            if which=="original"
            else run.get("final_route")
            or {}
        )
        if not snapshot or not list(snapshot.get("tracks") or []):
            self.statusBar().showMessage(
                f"This run has no {which} route snapshot to replay",4000
            ); return
        self.pending_journey_replay=(snapshot,f"{which.title()} journey replay")
        self.open_page("music_map")
        self.statusBar().showMessage(
            f"Refreshing Music Map before {which} replay…",3500
        )

    def _apply_pending_journey_replay(self):
        pending=self.pending_journey_replay
        self.pending_journey_replay=None
        if not pending:
            return
        snapshot,label=pending
        result=materialize_route_snapshot(
            dict(snapshot or {}),
            dict(self.music_map.ref_map or {}),
        )
        if not result.get("complete"):
            unresolved=[
                str(row.get("display") or "Unknown track")
                for row in list(result.get("unresolved") or [])
                if isinstance(row,dict)
            ]
            QMessageBox.warning(
                self,
                "Could not replay full journey",
                "These historical tracks are not available on the current Music Map:\n\n"
                + "\n".join(unresolved[:8]),
            )
            return
        route=dict(result.get("route") or {})
        refs=[str(ref) for ref in list(route.get("path_refs") or []) if str(ref)]
        tracks=[
            dict(self.music_map.ref_map[ref])
            for ref in refs
            if ref in self.music_map.ref_map
        ]
        if len(tracks)!=len(refs):
            self.statusBar().showMessage("Historical route could not be fully rematched",4500); return
        self.music_path_result=route
        self.music_path_start_ref=refs[0]
        self.music_path_end_ref=refs[-1]
        self._music_path_update_label()
        mode=str(route.get("mode") or "balanced")
        index=self.music_path_mode.findData(mode)
        if index>=0:
            self.music_path_mode.setCurrentIndex(index)
        self.music_map.show_route(route)
        self.music_path_steps.clear()
        for index,hop in enumerate(list(route.get("hops") or []),start=1):
            if not isinstance(hop,dict):
                continue
            self.music_path_steps.addItem(
                f"{index}. {self._music_path_name(hop.get('from') or '')}  →  "
                f"{self._music_path_name(hop.get('to') or '')}\n"
                f"{hop.get('reason') or 'Historical route'}"
            )
        self.player.set_queue(tracks,0,True)
        self.statusBar().showMessage(f"{label} · {len(tracks)} tracks",5000)

    def _refresh_playlists(self):
        self.playlists_list.clear()
        records=self.state.playlists()
        for p in records:
            name=str(p.get("name") or "Playlist")
            description=str(p.get("description") or "").strip()
            count=int(p.get("track_count") or 0)
            source=str(p.get("source") or "")
            subtitle=f"{count} track{'s' if count!=1 else ''}"
            if source:
                subtitle+=f" · {source.replace('import:','imported ')}"
            if description:
                subtitle+=f"\n{description}"
            item=QListWidgetItem(f"{name}\n{subtitle}")
            item.setData(Qt.UserRole,p)
            self.playlists_list.addItem(item)
        if hasattr(self,"playlists_stack"):
            self.playlists_stack.setCurrentWidget(
                self.playlists_list if records else self.playlists_empty
            )
        self._playlist_selection_changed()

    @staticmethod
    def _playlist_tracks(record):
        payload=dict(record.get("payload") or {})
        requested=payload.get("requested_tracks")
        if isinstance(requested,list):return [dict(x) for x in requested if isinstance(x,dict)]
        return [dict(x) for x in list(payload.get("tracks") or payload.get("rows") or []) if isinstance(x,dict)]

    def _play_saved_playlist(self,item):
        record=dict(item.data(Qt.UserRole) or {}); tracks=self._playlist_tracks(record)
        if not tracks:
            self.statusBar().showMessage("This playlist has no tracks",3000); return
        self.statusBar().showMessage("Resolving playlist across connected sources…")
        self._run_async(lambda:self.providers.resolve_playlist(tracks),self._start_resolved_playlist)

    def _start_resolved_playlist(self,result):
        tracks=list(result.get("tracks") or []); unresolved=list(result.get("unresolved") or [])
        if tracks:self.player.set_queue(tracks,0,True)
        msg=f"Playing {len(tracks)} matched tracks"
        if unresolved:msg+=f" · {len(unresolved)} could not be matched"
        self.statusBar().showMessage(msg,6000)

    def _import_playlist_file(self):
        filename,_=QFileDialog.getOpenFileName(self,"Import playlist",filter="Playlists (*.xspf *.m3u *.m3u8);;XSPF (*.xspf);;M3U/M3U8 (*.m3u *.m3u8)")
        if not filename:return
        try:data=load_playlist(Path(filename))
        except Exception as exc:QMessageBox.warning(self,"Could not import playlist",str(exc)); return
        requested=[dict(x) for x in list(data.get("tracks") or []) if isinstance(x,dict)]
        if not requested:QMessageBox.information(self,"Empty playlist","No tracks were found in this playlist."); return
        playlist_id=str(uuid.uuid4()); name=str(data.get("name") or Path(filename).stem); description=str(data.get("description") or "")
        self.statusBar().showMessage(f"Importing and matching {len(requested)} tracks…")
        self._run_async(lambda:self.providers.resolve_playlist(requested),lambda result:self._finish_playlist_file_import(playlist_id,name,description,str(data.get("format") or "playlist"),requested,result))

    def _finish_playlist_file_import(self,playlist_id,name,description,fmt,requested,result):
        tracks=list(result.get("tracks") or []); unresolved=list(result.get("unresolved") or [])
        payload={"tracks":tracks,"unresolved":unresolved,"requested_tracks":requested,"format":fmt}
        self.state.save_playlist(playlist_id,name,description,f"import:{fmt}",payload); self._refresh_playlists()
        msg=f"Imported {name}: {len(tracks)} playable"
        if unresolved:msg+=f" · {len(unresolved)} unresolved (kept for future matching)"
        self.statusBar().showMessage(msg,7000)

    def _open_ai_playlist_import(self):
        dialog=QDialog(self); dialog.setWindowTitle("Import an AI playlist"); dialog.resize(900,650)
        layout=QVBoxLayout(dialog); layout.setContentsMargins(24,22,24,20); layout.setSpacing(14)
        title=QLabel("Import an AI playlist"); title.setStyleSheet("font-size: 25px; font-weight: 700;")
        subtitle=QLabel("Paste a playlist from ChatGPT, Claude, Gemini or another AI. JSON, Markdown lists or tables, TXT, CSV and M3U/M3U8 are supported.")
        subtitle.setWordWrap(True); subtitle.setStyleSheet("color: #9aa4b8; font-size: 14px;")
        layout.addWidget(title); layout.addWidget(subtitle)
        editor=QPlainTextEdit(); editor.setPlaceholderText("Paste the playlist here…"); editor.setMinimumHeight(300); layout.addWidget(editor,1)
        actions=QHBoxLayout()
        copy_prompt=QPushButton("Copy ChatGPT Prompt")
        import_file=QPushButton("Import File…")
        paste_clipboard=QPushButton("Paste Clipboard")
        actions.addWidget(copy_prompt); actions.addWidget(import_file); actions.addWidget(paste_clipboard); actions.addStretch(1)
        layout.insertLayout(2,actions)
        privacy=QLabel("No AI connection is needed, and Melodex does not send this text to an AI service. Track matching uses your connected music sources.")
        privacy.setWordWrap(True); privacy.setStyleSheet("color: #9aa4b8;")
        layout.addWidget(privacy)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel)
        analyze=buttons.addButton("Analyse Playlist",QDialogButtonBox.AcceptRole)
        layout.addWidget(buttons)

        prompt=("Create a playlist of real, released tracks. Return valid JSON only, using this structure:\n"
                '{\n  "melodex_playlist": 1,\n  "name": "Playlist name",\n'
                '  "description": "Short description",\n  "tracks": [\n'
                '    {"artist": "Artist name", "title": "Exact track title", "album": "Album when known", "year": 2006, "reason": "Optional short reason"}\n'
                '  ]\n}\nUse canonical artist and track names, and keep the tracks in the intended listening order. Do not add commentary outside the JSON.')

        def do_copy_prompt():
            QApplication.clipboard().setText(prompt)
            self.statusBar().showMessage("Playlist prompt copied. Paste it into your AI chat.",5000)

        def do_paste_clipboard():
            value=QApplication.clipboard().text()
            if not value.strip():
                QMessageBox.information(dialog,"Clipboard is empty","Copy a playlist from your AI chat first, then choose Paste Clipboard.")
                return
            editor.setPlainText(value)

        def do_import_file():
            filename,_=QFileDialog.getOpenFileName(dialog,"Import playlist",filter="Playlist/text files (*.json *.txt *.csv *.tsv *.xspf *.m3u *.m3u8);;All files (*)")
            if not filename:return
            path=Path(filename)
            try:
                if path.suffix.lower() in {".xspf",".m3u",".m3u8"}:
                    data=load_playlist(path)
                else:
                    data=parse_playlist_text(path.read_text("utf-8-sig",errors="replace"))
                    if data.get("name") in {"Pasted playlist","AI playlist"}:
                        data["name"]=path.stem
                editor.setPlainText(json.dumps(data,ensure_ascii=False,indent=2))
            except Exception as exc:
                QMessageBox.warning(dialog,"Could not import playlist",str(exc))

        def do_analyze():
            try:
                data=parse_playlist_text(editor.toPlainText())
            except Exception as exc:
                QMessageBox.warning(dialog,"Could not read playlist",str(exc)); return
            dialog.accept()
            self._import_ai_playlist(data,source="ai-paste")

        copy_prompt.clicked.connect(do_copy_prompt)
        import_file.clicked.connect(do_import_file)
        paste_clipboard.clicked.connect(do_paste_clipboard)
        buttons.rejected.connect(dialog.reject)
        analyze.clicked.connect(do_analyze)
        dialog.exec()

    def _playlist_export_path(self,title):
        path,chosen=QFileDialog.getSaveFileName(self,title,filter="XSPF Playlist (*.xspf);;M3U8 Playlist (*.m3u8);;M3U Playlist (*.m3u)")
        if not path:return None
        p=Path(path)
        if not p.suffix:
            suffix=".m3u8" if "M3U8" in chosen else ".m3u" if "M3U Playlist" in chosen else ".xspf"
            p=p.with_suffix(suffix)
        return p

    def _export_selected_playlist(self):
        item=self.playlists_list.currentItem()
        if not item:self.statusBar().showMessage("Select a playlist first",3000); return
        record=dict(item.data(Qt.UserRole) or {}); tracks=self._playlist_tracks(record)
        if not tracks:self.statusBar().showMessage("This playlist has no tracks",3000); return
        path=self._playlist_export_path("Export playlist")
        if not path:return
        try:save_playlist(path,tracks,str(record.get("name") or "Melodex playlist"),str(record.get("description") or "")); self.statusBar().showMessage(f"Exported {path.name}",5000)
        except Exception as exc:QMessageBox.warning(self,"Could not export playlist",str(exc))

    def _export_queue(self):
        tracks=[dict(x) for x in self.player.queue if isinstance(x,dict)]
        if not tracks:self.statusBar().showMessage("The queue is empty",3000); return
        path=self._playlist_export_path("Export queue")
        if not path:return
        try:save_playlist(path,tracks,"Melodex queue",""); self.statusBar().showMessage(f"Exported {path.name}",5000)
        except Exception as exc:QMessageBox.warning(self,"Could not export queue",str(exc))

    def _refresh_moments(self):
        self.moments_list.clear()
        records=self.state.moments()
        for m in records:
            t=m.get("track") if isinstance(m.get("track"),dict) else {}
            if not t:
                try:
                    t=json.loads(m.get("track_json") or "{}")
                except Exception:
                    t={}
            sec=int(m.get("position_ms",0))//1000
            label=str(m.get("label") or "").strip()
            title=f"{t.get('title') or 'Unknown track'} — {t.get('artist') or 'Unknown artist'}"
            subtitle=f"{sec//60}:{sec%60:02d}" + (f" · {label}" if label else "")
            item=QListWidgetItem(f"{title}\n{subtitle}")
            item.setData(Qt.UserRole,dict(m))
            self.moments_list.addItem(item)
        if hasattr(self,"moments_stack"):
            self.moments_stack.setCurrentWidget(
                self.moments_list if records else self.moments_empty
            )

    def _play_saved_moment(self, item: QListWidgetItem) -> None:
        data=item.data(Qt.UserRole)
        if not isinstance(data,dict):
            return
        track=data.get("track") if isinstance(data.get("track"),dict) else {}
        if not track:
            return
        position=max(0,int(data.get("position_ms") or 0))
        self.player.set_queue([dict(track)],0,True)
        if position:
            QTimer.singleShot(700,lambda:self.player.seek(position))

    def _refresh_taste(self):
        s=self.state.taste_summary(); self.taste_label.setText(f"Taste memory: {s.get('tracks',0)} tracks learned · {s.get('artists',0)} artists · completion rate {float(s.get('completion_rate',0))*100:.0f}%")

    # ------------------------------- sources/search
    def _choose_music_folder(self):
        folder=QFileDialog.getExistingDirectory(self,"Choose a music folder")
        if not folder:
            return
        roots=self.providers.local_roots()
        p=Path(folder)
        if p not in roots:
            roots.append(p)
        self.providers.configure_local_roots(roots)
        self._start_local_scan("folder added")

    def _rescan(self):
        self._start_local_scan("rescan")

    @staticmethod
    def _local_roots_key(roots: list[Path]) -> tuple[str, ...]:
        return tuple(str(Path(root)) for root in roots)

    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        total=max(0,int(seconds))
        minutes,seconds=divmod(total,60)
        hours,minutes=divmod(minutes,60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:d}:{seconds:02d}"

    def _refresh_background_scan_activity(self) -> None:
        if not self._local_scan_in_progress:
            self.background_activity.hide()
            self._background_activity_timer.stop()
            return

        payload=dict(self._local_scan_last_progress or {})
        phase=str(payload.get("phase") or "discovering")
        found=max(0,int(payload.get("audio_files_seen") or 0))
        completed=max(0,int(payload.get("completed") or 0))
        total=max(0,int(payload.get("total") or 0))
        elapsed=self._format_elapsed(
            time.monotonic() - self._local_scan_started_at
            if self._local_scan_started_at
            else 0.0
        )

        if phase=="metadata" and total:
            stage=f"Reading tags · {completed:,}/{total:,}"
            self.background_activity_progress.setRange(0,total)
            self.background_activity_progress.setValue(min(completed,total))
            self.background_activity_progress.setFormat("%v / %m")
        elif phase=="saving":
            stage="Saving library index"
            self.background_activity_progress.setRange(0,0)
            self.background_activity_progress.setFormat("")
        else:
            stage=(
                f"Discovering files · {found:,} found"
                if found
                else "Discovering files"
            )
            self.background_activity_progress.setRange(0,0)
            self.background_activity_progress.setFormat("")

        runner=self._local_scan_runner
        paused=bool(runner is not None and runner.paused)
        if paused:
            stage="Paused · " + stage
        self.background_activity_label.setText(
            f"Indexing music · {stage} · {elapsed} elapsed · "
            "You can keep using Melodex"
        )
        self.background_activity_pause.setText("Resume" if paused else "Pause")
        self.background_activity_pause.setEnabled(runner is not None)
        self.background_activity_cancel.setEnabled(runner is not None)
        self.background_activity.show()

    def _local_scan_progress(self, payload: object) -> None:
        if not isinstance(payload,dict) or not self._local_scan_in_progress:
            return
        self._local_scan_last_progress=dict(payload)
        self._refresh_background_scan_activity()
        if hasattr(self,"library_browser"):
            self.library_browser.set_scan_progress(payload)
        phase=str(payload.get("phase") or "")
        if phase=="discovering":
            found=int(payload.get("audio_files_seen") or 0)
            message=f"Indexing music · discovering files · {found:,} tracks found"
            self.statusBar().showMessage(message)
            if hasattr(self,"home_status"):
                self.home_status.setText(message)
        elif phase=="metadata":
            completed=int(payload.get("completed") or 0)
            total=int(payload.get("total") or 0)
            found=int(payload.get("audio_files_seen") or 0)
            unchanged=int(payload.get("unchanged") or 0)
            if total==0 and found:
                message=(
                    f"Indexing music · metadata already up to date · "
                    f"{unchanged or found:,} reused"
                )
            else:
                message=f"Indexing music · reading metadata · {completed:,}/{total:,}"
            self.statusBar().showMessage(message)
            if hasattr(self,"home_status"):
                self.home_status.setText(message)
        elif phase=="saving":
            message="Indexing music · saving local library index…"
            self.statusBar().showMessage(message)
            if hasattr(self,"home_status"):
                self.home_status.setText(message)

    def _toggle_local_scan_pause(self) -> None:
        runner=self._local_scan_runner
        if runner is None or not self._local_scan_in_progress:
            return
        if runner.paused:
            runner.resume()
            if hasattr(self,"library_browser"):
                self.library_browser.set_scan_paused(False)
            self._refresh_background_scan_activity()
            self.statusBar().showMessage("Music indexing resumed",3000)
        else:
            runner.pause()
            if hasattr(self,"library_browser"):
                self.library_browser.set_scan_paused(True)
            self._refresh_background_scan_activity()
            self.statusBar().showMessage("Music indexing paused",3000)

    def _cancel_local_scan(self) -> None:
        runner=self._local_scan_runner
        if runner is None or not self._local_scan_in_progress:
            return
        self._local_scan_pending=False
        runner.cancel()
        if hasattr(self,"library_browser"):
            self.library_browser.set_scan_cancelling()
        self.background_activity_pause.setEnabled(False)
        self.background_activity_cancel.setEnabled(False)
        self.background_activity_label.setText(
            "Indexing music · Stopping safely… · existing library remains usable"
        )
        self.statusBar().showMessage(
            "Stopping music indexing… a stuck NAS scanner will be terminated automatically"
        )

    def _start_local_scan(self, reason: str = "scan") -> None:
        roots=self.providers.local_roots()
        if not roots:
            self.statusBar().showMessage("Add a music folder first",3000)
            return

        if self._local_scan_in_progress:
            self._local_scan_pending=True
            runner=self._local_scan_runner
            current_key=self._local_roots_key(roots)
            running_key=(
                self._local_roots_key(runner.roots)
                if runner is not None
                else ()
            )
            if runner is not None and current_key != running_key:
                runner.cancel()
                self.statusBar().showMessage(
                    "Music folders changed · stopping the old indexer and restarting…",
                    5000,
                )
            else:
                self.statusBar().showMessage(
                    "Music indexing is already running · a fresh rescan is queued",
                    4000,
                )
            return

        self._local_scan_in_progress=True
        self._local_scan_pending=False
        self._local_scan_sequence += 1
        self._local_scan_started_at=time.monotonic()
        self._local_scan_last_progress={"phase":"discovering","audio_files_seen":0}
        sequence=self._local_scan_sequence
        roots_snapshot=[Path(root) for root in roots]
        roots_key=self._local_roots_key(roots_snapshot)
        if hasattr(self,"library_browser"):
            self.library_browser.begin_scan(reason)
        self._refresh_background_scan_activity()
        self._background_activity_timer.start()
        self.statusBar().showMessage(
            "Indexing your music in an isolated background scanner…"
        )
        if hasattr(self,"home_status"):
            self.home_status.setText(
                "Indexing your music in an isolated background scanner…"
            )

        sig=WorkerSignals()
        self._local_scan_signals=sig
        sig.progress.connect(
            lambda payload: None
            if self._closing or sequence != self._local_scan_sequence
            else self._local_scan_progress(payload)
        )

        def done(snapshot):
            if sequence != self._local_scan_sequence:
                return
            self._local_scan_in_progress=False
            self._local_scan_runner=None
            self._background_activity_timer.stop()
            self.background_activity.hide()
            current_key=self._local_roots_key(self.providers.local_roots())
            result=dict(snapshot or {})

            if bool(result.get("cancelled")):
                if hasattr(self,"library_browser"):
                    self.library_browser.finish_scan("cancelled")
                    QTimer.singleShot(3500,self.library_browser.clear_scan_status)
                self._show_home()
                if bool(result.get("hard_cancelled")):
                    self.statusBar().showMessage(
                        "Music indexing stopped · unresponsive scanner terminated · existing library kept",
                        6500,
                    )
                else:
                    self.statusBar().showMessage(
                        "Music indexing cancelled · existing library kept",
                        5000,
                    )
                if self._local_scan_pending:
                    self._local_scan_pending=False
                    QTimer.singleShot(
                        0,
                        lambda:self._start_local_scan("queued rescan"),
                    )
                return

            # If roots changed while the disposable worker was scanning, its
            # catalog is not applied. A queued scan immediately rebuilds the
            # current root set.
            if current_key != roots_key:
                self._local_scan_pending=False
                QTimer.singleShot(
                    0,
                    lambda:self._start_local_scan("queued change"),
                )
                return

            count=self.providers.apply_local_scan_snapshot(result)
            changes=dict(result.get("changes") or {})
            self._refresh_library()
            self._show_home()
            if hasattr(self,"library_browser"):
                self.library_browser.finish_scan(
                    "complete",
                    count=count,
                    changes=changes,
                )
                QTimer.singleShot(3500,self.library_browser.clear_scan_status)
            summary_parts=[]
            for key,label in (
                ("unchanged","unchanged"),
                ("added","new"),
                ("changed","updated"),
                ("removed","removed"),
            ):
                value=max(0,int(changes.get(key) or 0))
                if value:
                    summary_parts.append(f"{value:,} {label}")
            incomplete=max(0,int(changes.get("incomplete_roots") or 0))
            if incomplete:
                summary_parts.append(
                    f"{incomplete} root{'s' if incomplete != 1 else ''} incomplete (cached copy kept)"
                )
            suffix=(" · " + " · ".join(summary_parts)) if summary_parts else ""
            self.statusBar().showMessage(
                f"Music indexing complete · {count:,} tracks{suffix}",
                6500,
            )
            if self._local_scan_pending:
                self._local_scan_pending=False
                QTimer.singleShot(
                    0,
                    lambda:self._start_local_scan("queued rescan"),
                )

        def failed(error):
            if sequence != self._local_scan_sequence:
                return
            self._local_scan_in_progress=False
            self._local_scan_runner=None
            self._background_activity_timer.stop()
            self.background_activity.hide()
            if hasattr(self,"library_browser"):
                self.library_browser.finish_scan("error",error=str(error))
            self._show_home()
            self.statusBar().showMessage(
                f"Music indexing failed · {error}",
                7000,
            )
            if self._local_scan_pending:
                self._local_scan_pending=False
                QTimer.singleShot(
                    0,
                    lambda:self._start_local_scan("queued rescan"),
                )

        sig.done.connect(
            lambda result: None if self._closing else done(result)
        )
        sig.error.connect(
            lambda error: None if self._closing else failed(error)
        )

        runner=LibraryScanProcess(
            self.data_dir,
            roots_snapshot,
            on_progress=sig.progress.emit,
            on_done=sig.done.emit,
            on_error=sig.error.emit,
        )
        self._local_scan_runner=runner
        self._refresh_background_scan_activity()
        try:
            runner.start()
        except Exception as exc:
            self._local_scan_runner=None
            sig.error.emit(str(exc))

    def _jamendo_settings(self):
        value,ok=QInputDialog.getText(self,"Jamendo reference provider","Your Jamendo developer client ID:",text=str(self.providers.settings.get("jamendo_client_id","")))
        if ok:
            self.providers.set_jamendo_client_id(value.strip()); self.statusBar().showMessage("Jamendo source updated",3000)

    def _active_extension_names(self, *capabilities: str) -> list[str]:
        wanted={str(value) for value in capabilities if str(value)}
        names=[]
        for row in self.providers.extensions(cached_config=True):
            if not bool(row.get("enabled",True)):
                continue
            config=dict(row.get("configuration_status") or {})
            if config.get("declared") and config.get("ready") is False:
                continue
            caps={str(value) for value in list(row.get("capabilities") or []) if value}
            if wanted and not (wanted & caps):
                continue
            name=str(row.get("name") or row.get("id") or "").strip()
            if name:
                names.append(name)
        return names

    def _searchable_source_names(self) -> list[str]:
        names=[]
        for pid in self.providers.searchable_provider_ids():
            provider=self.providers.providers.get(pid)
            if provider is None:
                continue
            if self._plugin_needs_setup_here(pid):
                continue
            name=str(provider.info.name or pid).replace(" (reference provider)","").strip()
            if name:
                names.append(name)
        return names

    def _refresh_plugin_presence(self) -> None:
        if hasattr(self,"search_plugin_presence"):
            self.search_plugin_presence.set_items(self._searchable_source_names())
        if hasattr(self,"artwork_plugin_presence"):
            self.artwork_plugin_presence.set_items(
                self._active_extension_names("artwork")
            )
        if hasattr(self,"recommendation_plugin_presence"):
            self.recommendation_plugin_presence.set_items(
                self._active_extension_names("library_suggestions","recommendations")
            )
        if hasattr(self,"rich_now"):
            self.rich_now.set_plugin_presence(
                lyrics=self._active_extension_names("lyrics"),
                context=self._active_extension_names("context","metadata","identity"),
            )

    def _refresh_sources_and_plugin_presence(self) -> None:
        self._refresh_sources()
        self._refresh_plugin_presence()

    def _plugin_directory(self, capability: str = ""):
        dialog=PluginDirectoryDialog(
            self.providers,
            on_installed=self._refresh_sources_and_plugin_presence,
            on_use=self._use_plugin_directory_entry,
            initial_capability=capability,
            parent=self,
        )
        dialog.exec()

    def _use_plugin_directory_entry(self, entry: dict[str,Any]) -> None:
        plugin_id=str(entry.get("id") or "")
        if not plugin_id:
            return
        if str(entry.get("kind") or "") == "provider":
            self._open_provider_search(plugin_id)
        else:
            self._use_extension(plugin_id)

    def _export_diagnostics(self):
        filename,_=QFileDialog.getSaveFileName(
            self,
            "Export redacted diagnostics",
            "melodex-diagnostics.json",
            "JSON files (*.json)",
        )
        if not filename:
            return
        path=Path(filename)
        if path.suffix.lower() != ".json":
            path=path.with_suffix(".json")
        ui_metrics = {}
        if hasattr(self, "library_browser"):
            ui_metrics["library_catalog"] = dict(
                getattr(self.library_browser, "last_catalog_metrics", {}) or {}
            )
            ui_metrics["library_filter"] = dict(
                getattr(self.library_browser, "last_filter_metrics", {}) or {}
            )
            ui_metrics["library_view"] = dict(
                getattr(self.library_browser, "last_view_metrics", {}) or {}
            )
            ui_metrics["track_virtualization"] = dict(
                getattr(
                    self.library_browser,
                    "last_track_virtualization_metrics",
                    {},
                ) or {}
            )
            ui_metrics["artwork_priority"] = dict(
                getattr(
                    self.library_browser,
                    "last_artwork_priority_metrics",
                    {},
                ) or {}
            )
        if hasattr(self, "responsiveness"):
            ui_metrics["responsiveness"] = self.responsiveness.summary()
        try:
            write_diagnostics(
                path,
                self.providers,
                ui_metrics=ui_metrics,
            )
        except Exception as exc:
            QMessageBox.critical(self,"Could not export diagnostics",str(exc))
            return
        QMessageBox.information(
            self,
            "Diagnostics exported",
            f"Saved redacted diagnostics to:\n{path}\n\n"
            "The export is designed to omit credentials, local library paths, "
            "stream URLs and playback secrets. Review the file before sharing it.",
        )
        self.statusBar().showMessage(f"Exported {path.name}",4000)

    def _install_provider(self):
        path,_=QFileDialog.getOpenFileName(self,"Install provider",filter="Melodex Provider (*.mdxprovider *.zip)")
        if not path:return
        try:
            p=self.providers.install_package(Path(path))
            self._refresh_sources()
            if plugin_needs_setup(self.providers,p.info.id):
                configure_plugin(self,self.providers,p.info.id,setup=True)
                self._refresh_sources()
            QMessageBox.information(
                self,
                "Provider installed",
                f"Installed {p.info.name}" + (
                    "\n\nSetup is still required before this provider is ready."
                    if plugin_needs_setup(self.providers,p.info.id)
                    else "\n\nReady to use."
                ),
            )
        except Exception as exc: QMessageBox.critical(self,"Could not install provider",str(exc))

    def _install_extension(self):
        path,_=QFileDialog.getOpenFileName(
            self,
            "Install capability extension",
            filter="Melodex Extension (*.mdxplugin *.zip)",
        )
        if not path:
            return
        try:
            info=self.providers.install_extension(Path(path))
            self._refresh_sources()
            if plugin_needs_setup(self.providers,info.id):
                configure_plugin(self,self.providers,info.id,setup=True)
                self._refresh_sources()
            QMessageBox.information(
                self,
                "Extension installed",
                f"Installed {info.name}\n\nCapabilities: {', '.join(info.capabilities)}"
                + (
                    "\n\nSetup is still required before this extension is ready."
                    if plugin_needs_setup(self.providers,info.id)
                    else "\n\nReady to use."
                ),
            )
        except Exception as exc:
            QMessageBox.critical(self,"Could not install extension",str(exc))

    def _selected_plugin_id(self) -> str:
        item=self.sources_list.currentItem()
        if not item:
            return ""
        value=str(item.data(Qt.UserRole) or "")
        if value.startswith("extension:"):
            return value.split(":",1)[1]
        return value if value not in {"local", "jamendo", "streams"} else ""

    def _test_all_plugins(self):
        plugin_ids=[
            pid for pid in self.providers.provider_order()
            if pid not in {"local","jamendo","streams"}
        ]
        plugin_ids.extend(
            str(row.get("id") or "")
            for row in self.providers.extensions()
            if str(row.get("id") or "")
        )
        plugin_ids=list(dict.fromkeys(plugin_ids))
        if not plugin_ids:
            self.statusBar().showMessage("No installed plugins to check",3000)
            return

        self.source_check_all.setEnabled(False)
        self.source_check_all.setText(f"Checking 0/{len(plugin_ids)}…")
        self.statusBar().showMessage(
            f"Checking {len(plugin_ids)} installed source/plugin connections…"
        )

        def work():
            results=[]
            total=len(plugin_ids)
            for index,plugin_id in enumerate(plugin_ids,1):
                try:
                    result=dict(self.providers.test_plugin_health(plugin_id,timeout=6.0) or {})
                except Exception as exc:
                    result={
                        "plugin_id":plugin_id,
                        "name":plugin_id,
                        "status":"error",
                        "message":str(exc),
                    }
                result["_index"]=index
                result["_total"]=total
                results.append(result)
            return results

        def done(results):
            rows=[dict(x) for x in list(results or []) if isinstance(x,dict)]
            self.source_check_all.setEnabled(True)
            self.source_check_all.setText("Check installed")
            self._refresh_sources()
            ready=sum(
                1 for row in rows
                if str(row.get("status") or "") in {"ready","ok"}
            )
            setup=sum(
                1 for row in rows
                if str(row.get("status") or "")=="setup_required"
            )
            attention=len(rows)-ready-setup
            bits=[f"{ready} ready"]
            if setup:
                bits.append(f"{setup} need setup")
            if attention:
                bits.append(f"{attention} need attention or are unavailable")
            summary=" · ".join(bits)
            self.statusBar().showMessage("Plugin check complete · "+summary,7000)
            QMessageBox.information(
                self,
                "Installed plugin check",
                "Checked the installed optional sources and enhancements.\n\n"
                + summary
                + "\n\nSelect any item marked Not tested/Needs attention for its individual details.",
            )

        def failed(error):
            self.source_check_all.setEnabled(True)
            self.source_check_all.setText("Check installed")
            self.statusBar().showMessage(f"Plugin check stopped: {error}",5000)

        self._run_async(work,done,failed)

    def _test_selected_plugin(self):
        plugin_id=self._selected_plugin_id()
        if not plugin_id:
            self.statusBar().showMessage(
                "Select an installed third-party provider or extension first",3000
            )
            return
        self.statusBar().showMessage("Testing plugin…")
        self._run_async(
            lambda:self.providers.test_plugin_health(plugin_id),
            lambda result:self._finish_plugin_health_test(plugin_id,result),
        )

    def _finish_plugin_health_test(self,plugin_id,result):
        result=dict(result or {})
        self._refresh_sources()
        self.statusBar().showMessage(health_summary(result),6000)
        if result.get("status")=="setup_required":
            answer=QMessageBox.question(
                self,
                "Plugin setup required",
                f"{result.get('name') or plugin_id} needs setup before it can be tested.\n\nConfigure it now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer==QMessageBox.Yes:
                configure_plugin(self,self.providers,plugin_id,setup=True)
                self._refresh_sources()
            return
        QMessageBox.information(
            self,
            "Plugin health",
            f"{result.get('name') or plugin_id}\n\n{health_summary(result)}",
        )

    def _configure_selected_plugin(self):
        plugin_id=self._selected_plugin_id()
        if not plugin_id:
            self.statusBar().showMessage("Select an installed provider or extension first",3000)
            return
        result=configure_plugin(self,self.providers,plugin_id)
        self._refresh_sources()
        if result is None:
            return
        if result.get("ready",True):
            self.statusBar().showMessage("Plugin configuration updated",3000)

    def _selected_extension_id(self) -> str:
        item=self.sources_list.currentItem()
        if not item:
            return ""
        value=str(item.data(Qt.UserRole) or "")
        return value.split(":",1)[1] if value.startswith("extension:") else ""

    def _toggle_extension(self):
        extension_id=self._selected_extension_id()
        if not extension_id:
            self.statusBar().showMessage("Select a capability extension first",2500)
            return
        extension=next(
            (x for x in self.providers.extensions() if str(x.get("id") or "") == extension_id),
            None,
        )
        if not extension:
            return
        enabled=not bool(extension.get("enabled",True))
        self.providers.set_extension_enabled(extension_id,enabled)
        self._refresh_sources()
        self.statusBar().showMessage(
            f"{extension.get('name') or extension_id} {'enabled' if enabled else 'disabled'}",
            3000,
        )

    def _remove_extension(self):
        extension_id=self._selected_extension_id()
        if not extension_id:
            self.statusBar().showMessage("Select a capability extension first",2500)
            return
        extension=next(
            (x for x in self.providers.extensions() if str(x.get("id") or "") == extension_id),
            {},
        )
        name=str(extension.get("name") or extension_id)
        answer=QMessageBox.question(
            self,
            "Remove extension",
            f"Remove {name}?\n\nThis deletes the installed extension from Melodex. "
            "It does not delete the original .mdxplugin file.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        if self.providers.remove_extension(extension_id):
            self._refresh_sources()
            self.statusBar().showMessage(f"Removed {name}",3000)

    def _selected_provider_id(self) -> str:
        item=self.sources_list.currentItem()
        if not item:
            return ""
        plugin_id=str(item.data(Qt.UserRole) or "")
        if plugin_id.startswith("extension:") or plugin_id in {"", "local", "jamendo", "streams"}:
            return ""
        return plugin_id

    def _remove_provider(self):
        plugin_id=self._selected_provider_id()
        if not plugin_id:
            self.statusBar().showMessage("Select an installed provider first",2500)
            return
        provider=self.providers.providers.get(plugin_id)
        if provider is None:
            return
        bundled=self.providers.is_bundled_provider(plugin_id)
        details=(
            " The bundled copy will stay removed until you choose Restore bundled sources."
            if bundled else ""
        )
        answer=QMessageBox.question(
            self,
            "Remove provider",
            f"Remove {provider.info.name} from Melodex?{details}\n\n"
            "This does not delete the original .mdxprovider file.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        if self.providers.remove_provider(plugin_id):
            self._refresh_sources()
            self.statusBar().showMessage(f"Removed {provider.info.name}",3000)

    def _restore_bundled_sources(self):
        restored=self.providers.restore_bundled_providers()
        self._refresh_sources()
        if restored:
            message=f"Restored {len(restored)} bundled source(s)."
        else:
            message="Bundled sources are already installed."
        QMessageBox.information(self,"Bundled sources",message)

    def _stream_prompt(self, existing: dict[str, Any] | None = None):
        existing = existing or {}
        name, ok = QInputDialog.getText(
            self,
            "User Stream",
            "Name:",
            text=str(existing.get("name") or ""),
        )
        if not ok:
            return None
        url, ok = QInputDialog.getText(
            self,
            "User Stream",
            "HTTP(S) stream URL:",
            text=str(existing.get("url") or ""),
        )
        if not ok:
            return None
        genre, ok = QInputDialog.getText(
            self,
            "User Stream",
            "Genre (optional):",
            text=str(existing.get("genre") or ""),
        )
        if not ok:
            return None
        return {
            "name": name.strip() or "Untitled stream",
            "url": url.strip(),
            "genre": genre.strip(),
            "description": str(existing.get("description") or ""),
        }

    def _user_streams_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("User Streams")
        dialog.resize(720, 420)
        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Add internet radio or direct HTTP(S) audio streams. "
            "You can also import M3U, M3U8 or PLS stream playlists."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        rows = QListWidget()
        layout.addWidget(rows, 1)

        def refresh():
            rows.clear()
            for entry in self.providers.user_streams():
                detail = entry.get("genre") or entry.get("url") or ""
                item = QListWidgetItem(f"{entry.get('name','Untitled stream')}\n{detail}")
                item.setData(Qt.UserRole, entry)
                rows.addItem(item)

        def add_url():
            values = self._stream_prompt()
            if not values:
                return
            try:
                self.providers.add_user_stream(**values)
                refresh()
                self._refresh_sources()
            except Exception as exc:
                QMessageBox.critical(dialog, "Could not add stream", str(exc))

        def edit_selected():
            current = rows.currentItem()
            if not current:
                return
            entry = dict(current.data(Qt.UserRole) or {})
            values = self._stream_prompt(entry)
            if not values:
                return
            try:
                self.providers.update_user_stream(str(entry.get("id") or ""), **values)
                refresh()
                self._refresh_sources()
            except Exception as exc:
                QMessageBox.critical(dialog, "Could not update stream", str(exc))

        def import_playlist():
            filename, _ = QFileDialog.getOpenFileName(
                dialog,
                "Import stream playlist",
                filter="Stream playlists (*.m3u *.m3u8 *.pls)",
            )
            if not filename:
                return
            try:
                added = self.providers.import_user_stream_playlist(Path(filename))
                refresh()
                self._refresh_sources()
                QMessageBox.information(
                    dialog,
                    "Playlist imported",
                    f"Added {len(added)} new stream(s).",
                )
            except Exception as exc:
                QMessageBox.critical(dialog, "Could not import playlist", str(exc))

        def remove_selected():
            current = rows.currentItem()
            if not current:
                return
            entry = dict(current.data(Qt.UserRole) or {})
            if QMessageBox.question(
                dialog,
                "Remove stream",
                f"Remove {entry.get('name','this stream')}?",
                QMessageBox.Yes | QMessageBox.No,
            ) != QMessageBox.Yes:
                return
            self.providers.remove_user_stream(str(entry.get("id") or ""))
            refresh()
            self._refresh_sources()

        buttons = QHBoxLayout()
        add_button = QPushButton("Add URL"); add_button.clicked.connect(add_url)
        edit_button = QPushButton("Edit"); edit_button.clicked.connect(edit_selected)
        import_button = QPushButton("Import playlist"); import_button.clicked.connect(import_playlist)
        remove_button = QPushButton("Remove"); remove_button.clicked.connect(remove_selected)
        close_button = QPushButton("Close"); close_button.clicked.connect(dialog.accept)
        for button in (add_button, edit_button, import_button, remove_button):
            buttons.addWidget(button)
        buttons.addStretch(1); buttons.addWidget(close_button)
        layout.addLayout(buttons)

        rows.itemDoubleClicked.connect(lambda _item: edit_selected())
        refresh()
        dialog.exec()

    def _search_has_useful_results(self) -> bool:
        if not hasattr(self, "results"):
            return False
        for index in range(self.results.count()):
            data=self.results.item(index).data(Qt.UserRole)
            if isinstance(data,dict) and data:
                return True
        return False

    def _show_delayed_search_loading(self, sequence: int, target: str) -> None:
        if (
            sequence != self._search_sequence
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
        )

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
        t=dict(item.data(Qt.UserRole) or {}); self.player.set_queue([t],0,True)

    def _open_selected_source(self):
        item=self.results.currentItem()
        if not item:return
        t=dict(item.data(Qt.UserRole) or {})
        url=str(t.get("source_page") or "")
        if url: QDesktopServices.openUrl(url)
        else: self.statusBar().showMessage("This source did not provide a content page",3000)

    def _play_library(self,item):
        t=dict(item.data(Qt.UserRole) or {}); tracks=self.providers.local_catalog(); idx=next((i for i,x in enumerate(tracks) if x.get('track_id')==t.get('track_id')),0); self.player.set_queue(tracks,idx,True)

    def _add_selected_to_queue(self):
        item=self.results.currentItem()
        if not item:return
        t=dict(item.data(Qt.UserRole) or {}); q=list(self.player.queue)
        if not q: self.player.set_queue([t],0,False)
        else: self.player.queue.append(t); self.player.queueChanged.emit(self.player.queue)

    # ------------------------------- local intelligence
    def _intelligence_seeds(self, intent: str) -> list[dict[str, Any]]:
        if intent == "rediscover":
            return []
        current = dict(self.current_track or {})
        if not current or not current.get("local_path"):
            return []
        if intent in {"similar", "detour"}:
            return [current]
        if intent == "bridge":
            idx = int(getattr(self.player, "index", -1))
            queue = list(getattr(self.player, "queue", []) or [])
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
        )

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
            self.player.set_queue([dict(data)], 0, True)

    def _play_selected_intelligence(self) -> None:
        track = self._selected_intelligence_track()
        if track:
            self.player.set_queue([track], 0, True)

    def _queue_selected_intelligence(self) -> None:
        track = self._selected_intelligence_track()
        if not track:
            return
        if not self.player.queue:
            self.player.set_queue([track], 0, False)
        else:
            self.player.queue.append(track)
            self.player.queueChanged.emit(self.player.queue)
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
        )

    def _library_analysis_finished(self, result: dict[str, Any]) -> None:
        self.statusBar().showMessage(
            f"Library analysis ready · {int(result.get('analysed') or 0)}/{int(result.get('total') or 0)} analysed · {int(result.get('newly_analysed') or 0)} new",
            8000,
        )

    # ------------------------------- Music Map
    def _build_album_wall_payload(self):
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
            self.album_wall.set_model({},self.current_track)
            self.statusBar().showMessage("Add local music to build an Album Wall",4000)
            return
        self.statusBar().showMessage("Building Album Wall from local metadata and cached Flow analysis…")
        self._run_async(self._build_album_wall_payload,self._apply_album_wall_payload)

    def _apply_album_wall_payload(self,payload):
        payload=dict(payload or {})
        self.album_wall.set_model(payload,self.current_track)
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
        )

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
            self.player.set_queue(tracks,0,True)
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
            self.player.set_queue(tracks,0,False)
        else:
            self.player.append_queue(tracks,autoplay=False)
        self.statusBar().showMessage(f"Queued {len(tracks)} tracks from {album.get('title') or 'album'}",4000)

    def _album_wall_artwork_requested(self,requests):
        rows=[dict(x) for x in list(requests or []) if isinstance(x,dict)]
        if not rows:
            return
        def load():
            result={}
            for row in rows:
                key=str(row.get("key") or "")
                track=dict(row.get("track") or {})
                if not key or not track:
                    continue
                info=self.metadata.local_artwork(track)
                result[key]=str(info.get("path") or "")
            return result
        self._run_async(load,self.album_wall.set_artwork)

    def _album_wall_online_artwork_requested(self,requests):
        rows=[dict(x) for x in list(requests or []) if isinstance(x,dict)]
        if not rows:
            return

        def load():
            result={}
            for row in rows:
                key=str(row.get("key") or "")
                track=dict(row.get("track") or {})
                if not key or not track:
                    continue
                path=""
                try:
                    local=self.metadata.local_artwork(track)
                    path=str(local.get("path") or "")
                    if not path:
                        identity=self.metadata.identify(track)
                        artwork=self.metadata.artwork(track,identity)
                        path=str(artwork.get("path") or "")
                except Exception:
                    path=""
                result[key]=path
            return result

        self._run_async(load,self.album_wall.set_artwork)

    def _build_music_map_payload(self):
        catalog=self.providers.local_catalog()
        profiles, _seed_refs, ref_map, _analysed = self.local_intelligence.build_snapshot(
            catalog,
            [],
            max_tracks=5000,
            analyse_seeds=False,
        )
        model=build_music_map(profiles,max_nodes=700,neighbours=2)
        mapped_refs={
            str(node.get("ref") or "")
            for node in list(model.get("nodes") or [])
            if isinstance(node,dict) and str(node.get("ref") or "")
        }
        mapped_ref_map={
            ref:dict(track)
            for ref,track in ref_map.items()
            if ref in mapped_refs
        }
        knowledge=self.knowledge.snapshot(mapped_ref_map)
        graph=build_knowledge_graph(mapped_ref_map,knowledge)
        return {
            "model":model,
            "ref_map":mapped_ref_map,
            "knowledge_graph":graph,
        }

    def _refresh_music_map(self):
        catalog=self.providers.local_catalog()
        if not catalog:
            self.music_map.set_map({}, {}, self.current_track)
            self.statusBar().showMessage("Add local music to build a Music Map",4000)
            return
        self.statusBar().showMessage("Building Music Map from cached Flow analysis…")
        self._run_async(self._build_music_map_payload,self._apply_music_map_payload)

    def _apply_music_map_payload(self,payload):
        payload=dict(payload or {})
        if self.music_live_active:
            self._journey_live_stop("map refreshed · adaptation stopped")
        self.music_map.set_map(
            dict(payload.get("model") or {}),
            dict(payload.get("ref_map") or {}),
            self.current_track,
            dict(payload.get("knowledge_graph") or {}),
        )
        self.music_path_start_ref=""
        self.music_path_end_ref=""
        self.music_path_result={}
        self.music_journey_stages_data=[]
        if self.pending_journey_recipe is None:
            self.music_active_recipe_id=""
            self.music_active_recipe={}
        self._music_path_update_label()
        if hasattr(self,"music_journey_stages"):
            self._music_journey_render_stages()
        if hasattr(self,"music_path_steps"):
            self.music_path_steps.clear()
            self.music_path_steps.addItem("Select a mapped track, set start/destination, then Find path.")
        mapped=int((payload.get("model") or {}).get("analysed") or 0)
        if mapped:
            self.statusBar().showMessage(f"Music Map ready · {mapped} analysed tracks",5000)
        else:
            self.statusBar().showMessage("Music Map needs cached Flow analysis · choose Analyse my library",6000)
        if self.pending_journey_recipe is not None:
            self._apply_pending_journey_recipe()
        if self.pending_journey_replay is not None:
            self._apply_pending_journey_replay()

    def _remember_now_playing_knowledge(self,track,bundle):
        if not isinstance(track,dict) or not isinstance(bundle,dict):
            return
        kwargs={}
        if isinstance(bundle.get("identity"),dict):
            kwargs["identity"]=dict(bundle.get("identity") or {})
        if isinstance(bundle.get("artist"),dict):
            kwargs["artist"]=dict(bundle.get("artist") or {})
        if "credits" in bundle:
            kwargs["credits"]=[
                dict(x) for x in list(bundle.get("credits") or []) if isinstance(x,dict)
            ]
        if "context" in bundle:
            kwargs["context"]=[
                dict(x) for x in list(bundle.get("context") or []) if isinstance(x,dict)
            ]
        if kwargs:
            self.knowledge.remember(dict(track),**kwargs)
            if self.current_page=="music_map" and hasattr(self,"music_map"):
                knowledge=self.knowledge.snapshot(self.music_map.ref_map)
                self.music_map.set_knowledge_graph(
                    build_knowledge_graph(self.music_map.ref_map,knowledge)
                )

    def _knowledge_bundle_for_track(self,track):
        track=dict(track or {})
        errors=[]
        try:
            identity=self.metadata.identify(track).as_dict()
        except Exception as exc:
            identity={
                "artist":str(track.get("artist") or ""),
                "title":str(track.get("title") or ""),
                "album":str(track.get("album") or ""),
            }
            errors.append(f"identity: {exc}")

        artist={}
        credits=[]
        context=[]
        artist_mbid=str(identity.get("artist_mbid") or "")
        recording_mbid=str(identity.get("recording_mbid") or "")
        if artist_mbid:
            try:
                artist=self.metadata.artist_info(artist_mbid)
                qid=str(artist.get("wikidata_qid") or "")
                if qid:
                    identity["wikidata_id"]=qid
            except Exception as exc:
                errors.append(f"artist: {exc}")
        if recording_mbid:
            try:
                credits=self.metadata.recording_credits(recording_mbid)
            except Exception as exc:
                errors.append(f"credits: {exc}")
        if self.providers.capabilities is not None:
            try:
                context_result=self.metadata.enrich_context(track,identity)
                context=[
                    dict(x)
                    for x in list(context_result.get("cards") or [])
                    if isinstance(x,dict)
                ]
                errors.extend(
                    str(x)
                    for x in list(context_result.get("errors") or [])
                    if x
                )
            except Exception as exc:
                errors.append(f"context: {exc}")

        self.knowledge.remember(
            track,
            identity=identity,
            artist=artist,
            credits=credits,
            context=context,
        )
        return {
            "track":track,
            "matched":bool(recording_mbid or artist_mbid),
            "credits":len(credits),
            "context_cards":len(context),
            "errors":errors,
        }

    def _enrich_selected_map_knowledge(self):
        track=self._music_map_selected()
        if not track:
            self.statusBar().showMessage("Select a mapped track first",3000)
            return
        self.statusBar().showMessage(
            "Enriching selected track via MusicBrainz and enabled context plugins…"
        )
        self._run_async(
            lambda:self._knowledge_bundle_for_track(track),
            self._knowledge_enrichment_finished,
        )

    def _knowledge_needs_enrichment(self,track):
        payload=self.knowledge.get(dict(track or {}))
        identity=payload.get("identity") if isinstance(payload.get("identity"),dict) else {}
        has_identity=bool(
            identity.get("recording_mbid")
            or identity.get("artist_mbid")
            or track.get("musicbrainz_recording_id")
            or track.get("musicbrainz_artist_id")
        )
        has_credits="credits" in payload
        has_context="context" in payload
        has_artist="artist" in payload
        return not (has_identity and has_credits and has_context and has_artist)

    def _enrich_map_knowledge_batch(self):
        tracks=self.music_map.mapped_tracks() if hasattr(self,"music_map") else []
        pending=[track for track in tracks if self._knowledge_needs_enrichment(track)]
        batch=pending[:8]
        if not batch:
            self.statusBar().showMessage("Mapped knowledge is already populated for these tracks",4000)
            return
        self.statusBar().showMessage(
            f"Enriching {len(batch)} mapped tracks via MusicBrainz and enabled context plugins…"
        )
        def work():
            rows=[]
            for track in batch:
                try:
                    rows.append(self._knowledge_bundle_for_track(track))
                except Exception as exc:
                    rows.append({"track":track,"matched":False,"credits":0,"context_cards":0,"errors":[str(exc)]})
            return rows
        self._run_async(work,self._knowledge_batch_finished)

    def _knowledge_enrichment_finished(self,result):
        errors=[str(x) for x in list((result or {}).get("errors") or []) if x]
        self.statusBar().showMessage(
            f"Knowledge enriched · {int((result or {}).get('credits') or 0)} credits · "
            f"{int((result or {}).get('context_cards') or 0)} context cards"
            + (f" · {len(errors)} warning(s)" if errors else ""),
            7000,
        )
        self._refresh_music_map()

    def _knowledge_batch_finished(self,rows):
        rows=[dict(x) for x in list(rows or []) if isinstance(x,dict)]
        matched=sum(1 for row in rows if row.get("matched"))
        credits=sum(int(row.get("credits") or 0) for row in rows)
        cards=sum(int(row.get("context_cards") or 0) for row in rows)
        warnings=sum(len(list(row.get("errors") or [])) for row in rows)
        self.statusBar().showMessage(
            f"Knowledge batch complete · {matched}/{len(rows)} identified · "
            f"{credits} credits · {cards} context cards"
            + (f" · {warnings} warning(s)" if warnings else ""),
            9000,
        )
        self._refresh_music_map()

    # ------------------------------- Music Map Pathfinder
    def _music_path_name(self,ref):
        track=dict(self.music_map.ref_map.get(str(ref),{}) or {}) if hasattr(self,"music_map") else {}
        if not track:return "—"
        artist=str(track.get("artist") or "Unknown artist")
        title=str(track.get("title") or "Unknown track")
        return f"{artist} — {title}"

    def _music_path_update_label(self):
        if not hasattr(self,"music_path_label"):return
        self.music_path_label.setText(
            f"Pathfinder · start {self._music_path_name(self.music_path_start_ref)}"
            f"  →  destination {self._music_path_name(self.music_path_end_ref)}"
        )

    def _music_path_set_start(self):
        ref=self.music_map.selected_ref_value() if hasattr(self,"music_map") else ""
        if not ref:
            self.statusBar().showMessage("Select a Music Map track first",3000); return
        self.music_path_start_ref=ref
        self.music_path_result={}
        self.music_map.set_route_endpoints(self.music_path_start_ref,self.music_path_end_ref)
        self._music_path_update_label()
        self.statusBar().showMessage("Pathfinder start set",2500)

    def _music_path_set_end(self):
        ref=self.music_map.selected_ref_value() if hasattr(self,"music_map") else ""
        if not ref:
            self.statusBar().showMessage("Select a Music Map track first",3000); return
        self.music_path_end_ref=ref
        self.music_path_result={}
        self.music_map.set_route_endpoints(self.music_path_start_ref,self.music_path_end_ref)
        self._music_path_update_label()
        self.statusBar().showMessage("Pathfinder destination set",2500)

    def _music_path_find(self):
        if not self.music_path_start_ref or not self.music_path_end_ref:
            self.statusBar().showMessage("Set both Pathfinder start and destination",3500); return
        mode=str(self.music_path_mode.currentData() or "balanced")
        result=find_music_path(
            dict(self.music_map.model or {}),
            dict(self.music_map.knowledge_graph or {}),
            self.music_path_start_ref,
            self.music_path_end_ref,
            mode=mode,
            max_hops=12,
        )
        self.music_path_result=dict(result or {})
        self.music_map.show_route(self.music_path_result)
        self.music_path_steps.clear()
        if not self.music_path_result.get("found"):
            reason=str(self.music_path_result.get("reason") or "No route found")
            self.music_path_steps.addItem(reason)
            self.statusBar().showMessage(reason,6000)
            return

        refs=[str(x) for x in list(self.music_path_result.get("path_refs") or []) if str(x)]
        hops=[dict(x) for x in list(self.music_path_result.get("hops") or []) if isinstance(x,dict)]
        for index,hop in enumerate(hops):
            a=self._music_path_name(hop.get("from") or (refs[index] if index<len(refs) else ""))
            b=self._music_path_name(hop.get("to") or (refs[index+1] if index+1<len(refs) else ""))
            reason=str(hop.get("reason") or "graph connection")
            self.music_path_steps.addItem(f"{index+1}. {a}  →  {b}\n{reason}")
        self.statusBar().showMessage(
            f"Pathfinder ready · {len(hops)} hop{'s' if len(hops)!=1 else ''} · "
            f"score {float(self.music_path_result.get('score') or 0):.0%}",
            7000,
        )

    def _music_path_tracks(self):
        if not self.music_path_result.get("found"):return []
        refs=[str(x) for x in list(self.music_path_result.get("path_refs") or []) if str(x)]
        return [
            dict(self.music_map.ref_map[ref])
            for ref in refs
            if ref in self.music_map.ref_map
        ]

    def _music_path_play(self):
        if self.music_live_active:
            self._journey_live_stop("normal route playback")
        tracks=self._music_path_tracks()
        if not tracks:
            self.statusBar().showMessage("Find a Pathfinder route first",3000); return
        self.player.set_queue(tracks,0,True)
        self.statusBar().showMessage(f"Playing Pathfinder route · {len(tracks)} tracks",4000)

    def _music_path_queue(self):
        tracks=self._music_path_tracks()
        if not tracks:
            self.statusBar().showMessage("Find a Pathfinder route first",3000); return
        if not self.player.queue:
            self.player.set_queue(tracks,0,False)
        else:
            self.player.queue.extend(dict(track) for track in tracks)
            self.player.queueChanged.emit(self.player.queue)
        self.statusBar().showMessage(f"Queued Pathfinder route · {len(tracks)} tracks",4000)

    def _music_path_clear(self):
        if self.music_live_active:
            self._journey_live_stop("route cleared")
        self.music_path_start_ref=""
        self.music_path_end_ref=""
        self.music_path_result={}
        if hasattr(self,"music_map"):self.music_map.clear_route()
        self._music_path_update_label()
        if hasattr(self,"music_path_steps"):
            self.music_path_steps.clear()
            self.music_path_steps.addItem("Pathfinder explanations will appear here.")
        self.statusBar().showMessage("Pathfinder cleared",2500)

    def _journey_recipe_mark_modified(self):
        if self.music_active_recipe_id:
            self.music_active_recipe_id=""
            self.music_active_recipe={}

    # ------------------------------- Music Map Journey Designer
    def _music_journey_render_stages(self):
        if not hasattr(self,"music_journey_stages"):return
        self.music_journey_stages.clear()
        if not self.music_journey_stages_data:
            self.music_journey_stages.addItem(
                "Journey stages use the Pathfinder start/destination. Load a preset or add constraints/track waypoints."
            )
            return
        for index,stage in enumerate(self.music_journey_stages_data, start=1):
            if str(stage.get("type") or "")=="track":
                label=str(stage.get("label") or self._music_path_name(stage.get("ref") or ""))
                text=f"{index}. Track waypoint · {label}"
            else:
                key=str(stage.get("constraint") or "")
                text=f"{index}. Constraint · {str(stage.get('label') or STAGE_LABELS.get(key,key.title()))}"
            item=QListWidgetItem(text)
            item.setData(Qt.UserRole,index-1)
            self.music_journey_stages.addItem(item)

    def _music_journey_load_preset(self):
        self.music_active_recipe_id=""
        self.music_active_recipe={}
        raw=self.music_journey_preset.currentData() if hasattr(self,"music_journey_preset") else []
        self.music_journey_stages_data=[
            {"type":"constraint","constraint":str(key),"label":STAGE_LABELS.get(str(key),str(key).title())}
            for key in list(raw or [])
        ]
        self._music_journey_render_stages()
        self.statusBar().showMessage("Journey preset loaded",2500)

    def _music_journey_add_constraint(self):
        self.music_active_recipe_id=""
        self.music_active_recipe={}
        key=str(self.music_journey_constraint.currentData() or "") if hasattr(self,"music_journey_constraint") else ""
        if not key:return
        self.music_journey_stages_data.append(
            {"type":"constraint","constraint":key,"label":STAGE_LABELS.get(key,key.title())}
        )
        self._music_journey_render_stages()

    def _music_journey_add_track(self):
        self.music_active_recipe_id=""
        self.music_active_recipe={}
        ref=self.music_map.selected_ref_value() if hasattr(self,"music_map") else ""
        if not ref:
            self.statusBar().showMessage("Select a mapped track first",3000); return
        self.music_journey_stages_data.append(
            {"type":"track","ref":ref,"label":self._music_path_name(ref)}
        )
        self._music_journey_render_stages()

    def _music_journey_remove_stage(self):
        if not self.music_journey_stages_data:return
        self.music_active_recipe_id=""
        self.music_active_recipe={}
        row=self.music_journey_stages.currentRow() if hasattr(self,"music_journey_stages") else -1
        if row<0 or row>=len(self.music_journey_stages_data):
            row=len(self.music_journey_stages_data)-1
        self.music_journey_stages_data.pop(row)
        self._music_journey_render_stages()

    def _music_journey_clear_stages(self):
        self.music_active_recipe_id=""
        self.music_active_recipe={}
        self.music_journey_stages_data=[]
        self._music_journey_render_stages()
        self.statusBar().showMessage("Journey stages cleared",2500)

    def _music_journey_build(self):
        if self.music_live_active:
            self._journey_live_stop("design changed")
        if not self.music_path_start_ref or not self.music_path_end_ref:
            self.statusBar().showMessage(
                "Set Pathfinder start and destination before building a journey",4000
            ); return
        if not self.music_journey_stages_data:
            self.statusBar().showMessage(
                "Load a Journey preset or add at least one stage",3500
            ); return
        mode=str(self.music_path_mode.currentData() or "balanced")
        self.statusBar().showMessage("Designing staged local journey…")
        result=build_music_journey(
            dict(self.music_map.model or {}),
            dict(self.music_map.knowledge_graph or {}),
            self.music_path_start_ref,
            self.music_path_end_ref,
            list(self.music_journey_stages_data),
            mode=mode,
            max_hops_per_segment=8,
            candidates_per_stage=10,
        )
        self.music_path_result=dict(result or {})
        self.music_map.show_route(self.music_path_result)
        self.music_path_steps.clear()
        if not self.music_path_result.get("found"):
            reason=str(self.music_path_result.get("reason") or "Journey could not be built")
            self.music_path_steps.addItem(reason)
            for stage in list(self.music_path_result.get("stages") or []):
                if isinstance(stage,dict):
                    self.music_path_steps.addItem(
                        f"✓ {stage.get('label') or 'Stage'} · fit {float(stage.get('score') or 0):.0%}\n"
                        f"{stage.get('reason') or ''}"
                    )
            self.statusBar().showMessage(reason,7000)
            return

        stages_by_ref={
            str(stage.get("ref") or ""):dict(stage)
            for stage in list(self.music_path_result.get("stages") or [])
            if isinstance(stage,dict) and str(stage.get("ref") or "")
        }
        hops=[dict(x) for x in list(self.music_path_result.get("hops") or []) if isinstance(x,dict)]
        for index,hop in enumerate(hops,start=1):
            a=self._music_path_name(hop.get("from") or "")
            b=self._music_path_name(hop.get("to") or "")
            reason=str(hop.get("reason") or "graph connection")
            stage=stages_by_ref.get(str(hop.get("to") or ""))
            if stage:
                reason += (
                    f"\n→ Journey stage: {stage.get('label') or 'Stage'} · "
                    f"fit {float(stage.get('score') or 0):.0%} · {stage.get('reason') or ''}"
                )
            self.music_path_steps.addItem(f"{index}. {a}  →  {b}\n{reason}")
        self.statusBar().showMessage(
            f"Journey ready · {len(self.music_path_result.get('stages') or [])} stages · "
            f"{len(hops)} hops · score {float(self.music_path_result.get('score') or 0):.0%}",
            8000,
        )

    # ------------------------------- Journey Live
    def _music_ref_for_track(self,track):
        if not isinstance(track,dict) or not hasattr(self,"music_map"):
            return ""
        candidate=dict(track or {})
        for ref,mapped in self.music_map.ref_map.items():
            mapped=dict(mapped or {})
            for key in ("rel","local_path","track_id"):
                a=str(candidate.get(key) or "").strip()
                b=str(mapped.get(key) or "").strip()
                if a and b and a==b:
                    return str(ref)
        artist=str(candidate.get("artist") or "").strip().casefold()
        title=str(candidate.get("title") or "").strip().casefold()
        album=str(candidate.get("album") or "").strip().casefold()
        matches=[]
        for ref,mapped in self.music_map.ref_map.items():
            if (
                str(mapped.get("artist") or "").strip().casefold()==artist
                and str(mapped.get("title") or "").strip().casefold()==title
                and (
                    not album
                    or str(mapped.get("album") or "").strip().casefold()==album
                )
            ):
                matches.append(str(ref))
        return matches[0] if len(matches)==1 else ""

    def _journey_live_update_label(self,text=""):
        if not hasattr(self,"music_live_label"):
            return
        if text:
            self.music_live_label.setText("Journey Live · "+str(text))
            return
        if not self.music_live_active:
            self.music_live_label.setText("Journey Live · inactive")
            return
        current_ref=self._music_ref_for_track(self.current_track or {})
        current=self._music_path_name(current_ref)
        destination=self._music_path_name(self.music_live_destination_ref)
        avoided=len(self.music_live_avoid_refs)+len(self.music_live_avoid_artists)
        suffix=f" · {avoided} avoid rule{'s' if avoided!=1 else ''}" if avoided else ""
        self.music_live_label.setText(
            f"Journey Live · {current} → {destination}{suffix}"
        )

    def _journey_live_event(self,event_type,payload=None):
        if not self.music_live_run_id:
            return
        try:
            self.state.record_journey_event(
                self.music_live_run_id,
                str(event_type or ""),
                dict(payload or {}),
            )
        except Exception:
            pass

    def _journey_live_recipe_snapshot(self):
        name=str(self.music_active_recipe.get("name") or "Unsaved journey")
        description=str(self.music_active_recipe.get("description") or "")
        try:
            return make_journey_recipe(
                name=name,
                description=description,
                mode=str(self.music_path_mode.currentData() or "balanced"),
                stages=list(self.music_journey_stages_data),
                ref_map=dict(self.music_map.ref_map or {}),
            )
        except Exception:
            return {
                "melodex_journey":1,
                "name":name,
                "description":description,
                "routing_mode":str(self.music_path_mode.currentData() or "balanced"),
                "stages":[],
            }

    def _journey_live_final_snapshot(self):
        route=dict(self.music_live_route or self.music_path_result or {})
        played=[str(ref) for ref in list(self.music_live_played_refs or []) if str(ref)]
        tail=[str(ref) for ref in list(route.get("path_refs") or []) if str(ref)]
        combined=list(played)
        if tail:
            if combined and tail[0]==combined[-1]:
                combined.extend(tail[1:])
            else:
                for ref in tail:
                    if not combined or ref!=combined[-1]:
                        combined.append(ref)
        if combined:
            route["path_refs"]=combined
        return portable_route_snapshot(route,dict(self.music_map.ref_map or {}))

    def _journey_live_start(self):
        route=dict(self.music_path_result or {})
        if not route.get("found") or not route.get("journey"):
            self.statusBar().showMessage(
                "Build a Journey Designer route before starting Journey Live",4000
            ); return
        if self.music_live_active:
            self._journey_live_stop("restarted")
        refs=[str(x) for x in list(route.get("path_refs") or []) if str(x)]
        tracks=[
            dict(self.music_map.ref_map[ref])
            for ref in refs
            if ref in self.music_map.ref_map
        ]
        if len(tracks)<1 or len(tracks)!=len(refs):
            self.statusBar().showMessage(
                "Journey Live needs every route track to remain on the current Music Map",4500
            ); return
        self.music_live_active=True
        self.music_live_route=dict(route)
        self.music_live_original_route=dict(route)
        self.music_live_destination_ref=refs[-1]
        self.music_live_avoid_refs=set()
        self.music_live_avoid_artists=set()
        self.music_live_replanning=False
        self.music_live_played_refs=[]
        self.music_live_run_id=str(uuid.uuid4())
        recipe=self._journey_live_recipe_snapshot()
        original_snapshot=portable_route_snapshot(
            route,
            dict(self.music_map.ref_map or {}),
        )
        try:
            self.state.start_journey_run(
                self.music_live_run_id,
                recipe_id=str(self.music_active_recipe_id or ""),
                recipe=recipe,
                original_route=original_snapshot,
            )
            self._journey_live_event(
                "start",
                {
                    "recipe_id":str(self.music_active_recipe_id or ""),
                    "destination":self._music_path_name(self.music_live_destination_ref),
                    "routing_mode":str(self.music_path_mode.currentData() or "balanced"),
                },
            )
        except Exception:
            self.music_live_run_id=""
        if hasattr(self,"music_live_steering"):
            self.music_live_steering.setCurrentIndex(0)
        self.player.set_queue(tracks,0,True)
        self.music_map.show_route(route)
        self._journey_live_update_label()
        self._refresh_journeys()
        self.statusBar().showMessage(
            "Journey Live active · manual Next will adapt the remaining route",6000
        )

    def _journey_live_stop(self,message="inactive"):
        was_active=bool(self.music_live_active)
        run_id=str(self.music_live_run_id or "")
        final_snapshot=self._journey_live_final_snapshot() if was_active and run_id else {}
        status="completed" if str(message)=="destination reached" else "stopped"
        if run_id:
            self._journey_live_event(
                "complete" if status=="completed" else "stop",
                {"reason":str(message or status)},
            )
            try:
                self.state.finish_journey_run(
                    run_id,
                    status=status,
                    final_route=final_snapshot,
                )
            except Exception:
                pass
        self.music_live_active=False
        self.music_live_replanning=False
        self.music_live_run_id=""
        self._journey_live_update_label(message)
        if hasattr(self,"journey_runs_list"):
            self._refresh_journeys()

    def _journey_live_apply_steer(self):
        if not self.music_live_active:
            self.statusBar().showMessage("Start Journey Live first",3000); return
        steering=str(self.music_live_steering.currentData() or "") if hasattr(self,"music_live_steering") else ""
        if not steering:
            self.statusBar().showMessage("Choose a Journey Live steering direction first",3000); return
        self._journey_live_event(
            "steer",
            {
                "steering":steering,
                "label":str(self.music_live_steering.currentText() or steering),
            },
        )
        self._journey_live_replan(steering,reason=f"steer:{steering}")

    def _journey_live_avoid_current_artist(self):
        if not self.music_live_active or not self.current_track:
            self.statusBar().showMessage("Start Journey Live and play a mapped track first",3500); return
        artist=str(self.current_track.get("artist") or "").strip()
        if not artist:
            self.statusBar().showMessage("The current track has no artist metadata to avoid",3500); return
        self.music_live_avoid_artists.add(artist)
        self._journey_live_event("avoid_artist",{"artist":artist})
        self.statusBar().showMessage(f"Journey Live will avoid {artist} in the remaining route",4500)
        self._journey_live_replan("",reason="avoid artist")

    def _journey_live_restore(self):
        if not self.music_live_active:
            self.statusBar().showMessage("Start Journey Live first",3000); return
        self.music_live_avoid_refs=set()
        self.music_live_avoid_artists=set()
        self._journey_live_event("restore",{})
        self._journey_live_replan(
            "",
            base_route=dict(self.music_live_original_route or {}),
            reason="restore designed route",
        )

    def _journey_live_replan(
        self,
        steering="",
        *,
        reopen_stage_refs=None,
        base_route=None,
        reason="",
    ):
        if not self.music_live_active:
            self.statusBar().showMessage("Start Journey Live first",3000); return
        if self.music_live_replanning:
            self.statusBar().showMessage("Journey Live is already replanning…",2500); return
        current_ref=self._music_ref_for_track(self.current_track or {})
        if not current_ref:
            self.statusBar().showMessage(
                "The current track is not available on the active Music Map",4500
            ); return
        if current_ref==self.music_live_destination_ref:
            self._journey_live_stop("destination reached")
            return
        route=dict(base_route or self.music_live_route or {})
        mode=str(self.music_path_mode.currentData() or route.get("mode") or "balanced")
        self.music_live_replanning=True
        self._journey_live_update_label("replanning…")
        avoid_refs=set(self.music_live_avoid_refs)
        avoid_artists=set(self.music_live_avoid_artists)
        reopen=set(reopen_stage_refs or set())
        destination=str(self.music_live_destination_ref)
        request_reason=str(reason or "")
        def work():
            result=replan_live_journey(
                dict(self.music_map.model or {}),
                dict(self.music_map.knowledge_graph or {}),
                route,
                current_ref,
                destination,
                mode=mode,
                steering=str(steering or ""),
                avoid_refs=avoid_refs,
                avoid_artists=avoid_artists,
                reopen_stage_refs=reopen,
                max_hops_per_segment=8,
            )
            result=dict(result or {})
            result["_live_from_ref"]=current_ref
            result["_live_request_reason"]=request_reason
            return result
        self._run_async(work,self._journey_live_apply_result)

    def _journey_live_apply_result(self,result):
        self.music_live_replanning=False
        if not self.music_live_active:
            return
        result=dict(result or {})
        expected=str(result.get("_live_from_ref") or "")
        current_ref=self._music_ref_for_track(self.current_track or {})
        if expected and current_ref and current_ref!=expected:
            self.statusBar().showMessage(
                "Journey Live moved while replanning · recalculating from the current track",4500
            )
            QTimer.singleShot(0,lambda:self._journey_live_replan(""))
            return
        if not result.get("found"):
            reason=str(result.get("reason") or "No adaptive route could be found")
            self._journey_live_event(
                "replan_failed",
                {
                    "reason":reason,
                    "request":str(result.get("_live_request_reason") or ""),
                },
            )
            self._journey_live_update_label("replan failed · queue unchanged")
            self.statusBar().showMessage(
                reason+" · existing queue kept unchanged",7000
            )
            return

        refs=[str(x) for x in list(result.get("path_refs") or []) if str(x)]
        if not refs or refs[0]!=current_ref:
            self._journey_live_update_label("invalid replan · queue unchanged")
            self.statusBar().showMessage(
                "Journey Live returned an invalid route start · existing queue kept unchanged",6500
            )
            return
        tail=[
            dict(self.music_map.ref_map[ref])
            for ref in refs[1:]
            if ref in self.music_map.ref_map
        ]
        if len(tail)!=max(0,len(refs)-1):
            self._journey_live_update_label("map changed · queue unchanged")
            self.statusBar().showMessage(
                "A replanned track is no longer on the Music Map · existing queue kept unchanged",6500
            )
            return

        self.player.replace_upcoming(tail)
        self.music_live_route=dict(result)
        self.music_path_result=dict(result)
        self._journey_live_event(
            "replan",
            {
                "reason":str(result.get("_live_request_reason") or result.get("reason") or ""),
                "upcoming_tracks":len(tail),
                "score":float(result.get("score") or 0.0),
            },
        )
        self.music_map.show_route(result)
        if hasattr(self,"music_live_steering"):
            self.music_live_steering.setCurrentIndex(0)
        self.music_path_steps.clear()
        stages_by_ref={
            str(stage.get("ref") or ""):dict(stage)
            for stage in list(result.get("stages") or [])
            if isinstance(stage,dict) and str(stage.get("ref") or "")
        }
        hops=[dict(x) for x in list(result.get("hops") or []) if isinstance(x,dict)]
        for index,hop in enumerate(hops,start=1):
            a=self._music_path_name(hop.get("from") or "")
            b=self._music_path_name(hop.get("to") or "")
            detail=str(hop.get("reason") or "graph connection")
            stage=stages_by_ref.get(str(hop.get("to") or ""))
            if stage:
                detail+=(
                    f"\n→ Live stage: {stage.get('label') or 'Stage'} · "
                    f"fit {float(stage.get('score') or 0):.0%} · {stage.get('reason') or ''}"
                )
            self.music_path_steps.addItem(f"{index}. {a}  →  {b}\n{detail}")
        self._journey_live_update_label()
        self.statusBar().showMessage(
            f"Journey Live replanned · {len(tail)} upcoming track{'s' if len(tail)!=1 else ''} · "
            f"score {float(result.get('score') or 0):.0%}",
            6500,
        )

    def _on_manual_advance(self,previous,current,played_ms,duration_ms):
        if not self.music_live_active:
            return
        previous_ref=self._music_ref_for_track(dict(previous or {}))
        if previous_ref:
            self.music_live_avoid_refs.add(previous_ref)
        self._journey_live_event(
            "manual_skip",
            {
                "track":_track_text(dict(previous or {})),
                "played_ms":int(played_ms or 0),
                "duration_ms":int(duration_ms or 0),
                "quick_skip":bool(int(played_ms or 0)<30000),
            },
        )
        reopen=set()
        # Preserve the existing taste model's conservative definition of an
        # immediate skip: under 30 seconds means the stage was not really
        # experienced, so a skipped semantic waypoint is reopened.
        if previous_ref and int(played_ms or 0)<30000:
            reopen.add(previous_ref)
        self.statusBar().showMessage("Journey Live adapting after manual skip…",3500)
        self._journey_live_replan(
            "",
            reopen_stage_refs=reopen,
            reason="manual skip",
        )

    def _analyse_library_for_map(self):
        catalog=self.providers.local_catalog()
        if not catalog:
            QMessageBox.information(self,"Add music first","Add a local music folder before analysing your library.")
            return
        if not self.flow.analysis_available:
            QMessageBox.information(
                self,
                "Audio analysis unavailable",
                "Music Map analysis needs ffmpeg and NumPy. Install/enable them, then try again."
            )
            return
        self.statusBar().showMessage("Analysing local library for Music Map…")
        self._run_async(
            lambda:self.local_intelligence.analyse_catalog(catalog),
            self._music_map_analysis_finished,
        )

    def _music_map_analysis_finished(self,result):
        self.statusBar().showMessage(
            f"Library analysis ready · {int(result.get('analysed') or 0)}/{int(result.get('total') or 0)} analysed",
            5000,
        )
        self._refresh_music_map()

    def _music_map_selected(self):
        return self.music_map.selected_track() if hasattr(self,"music_map") else {}

    def _play_music_map_track(self,track):
        if isinstance(track,dict) and track:
            self.player.set_queue([dict(track)],0,True)

    def _play_music_map_selected(self):
        track=self._music_map_selected()
        if track:self._play_music_map_track(track)

    def _queue_music_map_selected(self):
        track=self._music_map_selected()
        if not track:return
        if not self.player.queue:self.player.set_queue([track],0,False)
        else:
            self.player.queue.append(dict(track)); self.player.queueChanged.emit(self.player.queue)
        self.statusBar().showMessage("Added Music Map track to queue",3000)

    def _journey_from_music_map(self):
        track=self._music_map_selected()
        if not track:
            self.statusBar().showMessage("Select a Music Map track first",3000); return
        catalog=self.providers.local_catalog()
        self.statusBar().showMessage("Building a journey from this part of your map…")
        self._run_async(
            lambda:self.mind.build_session(
                catalog,
                self._path_for,
                minutes=int(self.minutes.currentText()),
                adventure=self.adventure.value()/100,
                mode=str(self.mode.currentData() or "balanced"),
                start_track=track,
            ),
            lambda plan:self._apply_mind(plan),
        )

    # ------------------------------- Flow / Mind
    def _path_for(self,t):
        p=str(t.get("local_path") or ""); return Path(p) if p else None

    def _transition_for(self,a,b):
        aa=self.flow.cached_analysis_for(self._path_for(a)); bb=self.flow.cached_analysis_for(self._path_for(b)); return self.flow.transition(aa,bb).as_dict()

    def _flow_queue(self):
        q=list(self.player.queue)
        if len(q)<2:return
        self.statusBar().showMessage("Planning Flow…")
        self._run_async(lambda:self.flow.plan_order(q,self._path_for,start_index=max(0,self.player.index),adventurous=0.35),lambda plan:self._apply_flow(plan))

    def _apply_flow(self,plan):
        tracks=list(plan.get("tracks",[])); self.player.set_queue(tracks,0,True); self.statusBar().showMessage(f"Flow ready · {plan.get('analysed',0)} tracks audio-analysed",5000)

    def _play_for_me(self,mode,minutes,adventure):
        catalog=self.providers.local_catalog()
        if not catalog:
            QMessageBox.information(self,"Add music first","Play for Me needs at least some local music. Add a folder, then try again."); return
        self.statusBar().showMessage("Building your journey…")
        self._run_async(lambda:self.mind.build_session(catalog,self._path_for,minutes=minutes,adventure=adventure,mode=mode),lambda plan:self._apply_mind(plan))

    def _apply_mind(self,plan):
        tracks=list(plan.get("tracks",[]));
        if tracks:self.player.set_queue(tracks,0,True)
        self.statusBar().showMessage(f"Journey ready · {len(tracks)} tracks · {plan.get('new_to_you',0)} new to you",6000)

    def _next_queue_track(self) -> dict[str, Any]:
        queue=list(getattr(self.player,"queue",[]) or [])
        index=int(getattr(self.player,"index",-1))
        next_index=index+1
        if next_index < 0 or next_index >= len(queue):
            return {}
        row=queue[next_index]
        return dict(row) if isinstance(row,dict) else {}

    def _schedule_next_track_prefetch(self) -> None:
        if self._closing:
            return
        self._prefetch_sequence += 1
        sequence=self._prefetch_sequence
        QTimer.singleShot(
            self._prefetch_delay_ms,
            lambda token=sequence:self._prefetch_next_track_assets(token),
        )

    def _prefetch_next_track_assets(self, sequence: int) -> None:
        if (
            self._closing
            or sequence != self._prefetch_sequence
            or self._local_scan_in_progress
        ):
            return
        track=self._next_queue_track()
        token=UserState.track_key(track) if track else ""
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
                payload["artwork"]=dict(
                    self.metadata.local_artwork(dict(track)) or {}
                )
            except Exception:
                payload["artwork"]={}
            local_path=str(payload["local_path"] or "")
            if local_path:
                payload["analysis_loaded"]=True
                try:
                    payload["analysis"]=self.flow.cached_analysis_for(
                        Path(local_path)
                    )
                except Exception:
                    payload["analysis"]=None
            return payload

        def apply(payload: object) -> None:
            if (
                sequence != self._prefetch_sequence
                or not isinstance(payload,dict)
            ):
                return
            current_next=self._next_queue_track()
            if token != UserState.track_key(current_next):
                return
            self._prefetched_track_assets[token]=dict(payload)
            # Keep this deliberately tiny: prediction must never become a
            # competing cache of the whole queue.
            while len(self._prefetched_track_assets) > 3:
                oldest=next(iter(self._prefetched_track_assets))
                self._prefetched_track_assets.pop(oldest,None)

        self._run_async(
            load,
            apply,
            priority="prefetch",
            lane="prefetch",
            label="next-track-prefetch",
        )

    # ------------------------------- player/taste
    def _on_track_changed(self,t):
        if self._closing:
            return
        if self.current_track and self.current_track_started and time.time()-self.current_track_started<30:
            self.state.record_skip(self.current_track)
        self.current_track=dict(t); self.current_track_started=time.time(); self.current_history_id=self.state.record_play(t)
        token=UserState.track_key(self.current_track)
        prefetched=dict(self._prefetched_track_assets.pop(token,{}) or {})
        self._set_taste_action_state()
        self._load_taste_action_state(self.current_track)
        self._visual_position_ms = 0
        self._visual_duration_ms = 0
        if hasattr(self, "living_canvas"):
            local_path=str(self.current_track.get("local_path") or "").strip()
            if (
                prefetched.get("analysis_loaded")
                and str(prefetched.get("local_path") or "") == local_path
            ):
                self.living_canvas.set_track(
                    self.current_track,
                    prefetched.get("analysis"),
                )
            else:
                self.living_canvas.set_track(self.current_track, None)
                self._request_cached_visual_analysis(self.current_track)
        if hasattr(self,"music_map"):
            self.music_map.highlight_track(t)
        if hasattr(self,"album_wall"):
            self.album_wall.highlight_track(t)
        if self.music_live_active:
            current_ref=self._music_ref_for_track(self.current_track)
            if current_ref and (
                not self.music_live_played_refs
                or self.music_live_played_refs[-1]!=current_ref
            ):
                self.music_live_played_refs.append(current_ref)
            if current_ref and current_ref==self.music_live_destination_ref:
                self._journey_live_stop("destination reached")
            else:
                self._journey_live_update_label()
        self.now_title.setText(str(t.get("title") or "Unknown track"))
        artist=str(t.get("artist") or "Unknown artist")
        album=str(t.get("album") or "")
        provider=str(t.get("provider_id") or "")
        pieces=[artist]
        if album:
            pieces.append(album)
        if self.power_toggle.isChecked() and provider:
            pieces.append(provider)
        src=str(t.get("source_page") or "")
        attr=str(t.get("attribution") or "")
        base="   ·   ".join(pieces)
        self.now_meta.setText(
            base + ((f"   ·   <a href=\"{src}\">{attr or 'Source'}</a>") if src else "")
        )
        if hasattr(self,"player_cover"):
            artwork=dict(prefetched.get("artwork") or {})
            artwork_path=str(artwork.get("path") or "")
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
                    lambda:self.metadata.local_artwork(dict(t)),
                    lambda result:self._player_artwork_loaded(token,result),
                    priority="foreground",
                    lane="disk",
                    label="current-track-artwork",
                )
        if hasattr(self,"rich_now"):
            self.rich_now.set_track(dict(t))
        if hasattr(self, "living_canvas"):
            self.living_canvas.refresh_context()
        if self.current_page=="home":
            self._refresh_home_continue()
        self._schedule_next_track_prefetch()

    def _player_artwork_loaded(self, token: str, result: object) -> None:
        if not isinstance(result,dict):
            return
        current=dict(self.current_track or {})
        if token!=UserState.track_key(current):
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

        def lookup():
            try:
                return self.flow.cached_analysis_for(Path(local_path))
            except Exception:
                return None

        self._run_async(
            lookup,
            lambda analysis:self._visual_analysis_loaded(local_path,analysis),
            priority="foreground",
            lane="analysis",
            label="current-track-analysis",
        )

    def _visual_analysis_loaded(self, local_path: str, analysis: object) -> None:
        current_path = str((self.current_track or {}).get("local_path") or "")
        if self._closing or not local_path or local_path != current_path:
            return
        self.living_canvas.set_analysis(analysis)
        self.living_canvas.set_position(self._visual_position_ms, self._visual_duration_ms)

    def _request_visual_mode_data(self, request: str) -> None:
        if self._closing or not hasattr(self, "living_canvas"):
            return
        mode, _, scale = str(request or "").partition(":")
        scale = scale or str(self.living_canvas.memory_scale.currentData() or "sessions")
        if mode not in {"constellation", "memory"}:
            return

        self._visual_context_sequence += 1
        sequence = self._visual_context_sequence
        queue_candidates: list[dict[str, Any]] = []
        if mode == "constellation":
            queue = list(getattr(self.player, "queue", []) or [])
            current_index = int(getattr(self.player, "index", -1))
            start = max(0, current_index - 5)
            end = min(len(queue), current_index + 21)
            for index in range(start, end):
                if index == current_index or not isinstance(queue[index], dict):
                    continue
                queue_candidates.append({
                    "_visual_token": len(queue_candidates),
                    "_visual_relation": "Up next" if index > current_index else "Played earlier",
                    "track": dict(queue[index]),
                })
        limit = 2000 if mode == "memory" else 120

        def load_context():
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
            lambda payload:self._visual_context_loaded(sequence,mode,payload),
            priority="visible",
            lane="disk",
            label=f"visual-context:{mode}",
        )

    def _visual_context_loaded(self, sequence: int, mode: str, payload: object) -> None:
        if self._closing or sequence != self._visual_context_sequence:
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

        current = dict(self.current_track or {})
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
            candidates.append({
                "_visual_token": token,
                "_visual_relation": "Played earlier",
                "track": dict(track),
            })
            refs[token] = dict(track)
            token += 1
        neighbours = build_constellation(current, candidates, limit=24)
        self._visual_neighbour_tracks = {
            node.token: refs[node.token]
            for node in neighbours if node.token in refs
        }
        self.living_canvas.set_neighbours(neighbours)

    def _queue_visual_neighbour(self, token: int) -> None:
        track = self._visual_neighbour_tracks.get(int(token))
        if not track:
            return
        self.player.append_queue([dict(track)], autoplay=False)
        self.statusBar().showMessage(
            f"Queued {track.get('artist') or 'Unknown artist'} — {track.get('title') or 'Unknown track'}",
            4000,
        )

    def _on_position(self,pos,dur):
        if self._closing:
            return
        self._visual_position_ms = int(pos)
        self._visual_duration_ms = int(dur)
        if hasattr(self,"living_canvas"):
            self.living_canvas.set_position(pos, dur)
            active_player = self.player.players[self.player.active]
            self.living_canvas.set_playing(
                active_player.playbackState() == QMediaPlayer.PlayingState
            )
        if hasattr(self,"rich_now"):self.rich_now.set_position(pos)
        if dur>0:self.seek.setValue(int(1000*pos/dur))
        if dur>0 and pos>=dur-1500 and self.current_history_id:
            self.state.mark_completed(self.current_history_id); self.current_history_id=0

    def _seek_released(self):
        p=self.player.players[self.player.active]; dur=p.duration()
        if dur>0:self.player.seek(int(dur*self.seek.value()/1000))

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
        token=UserState.track_key(track)
        if not token:
            self._set_taste_action_state()
            return

        def apply(signal: object) -> None:
            if token != UserState.track_key(dict(self.current_track or {})):
                return
            row=dict(signal or {}) if isinstance(signal,dict) else {}
            self._set_taste_action_state(
                loved=bool(int(row.get("loves") or 0)),
                kept=bool(int(row.get("keeps") or 0)),
            )

        self._run_async(
            lambda:self.state.track_signal(dict(track)),
            apply,
        )

    def _feedback(self,positive):
        if not self.current_track:
            return
        track=dict(self.current_track)
        token=UserState.track_key(track)
        if positive and hasattr(self,"love_button"):
            previous_text=self.love_button.text()
            previous_enabled=self.love_button.isEnabled()
            self.love_button.setText("♥ Loved")
            self.love_button.setEnabled(False)
            self.motion.settle(
                self.love_button,
                duration_ms=FAST_MOTION_MS,
                start_opacity=0.82,
            )
            self.statusBar().showMessage("Loved",2500)
        else:
            previous_text=""
            previous_enabled=True
            self.statusBar().showMessage(
                "Loved" if positive else "Not for me",
                2500,
            )

        def persist() -> bool:
            self.state.record_feedback(track,positive)
            return True

        def failed(error: str) -> None:
            if positive and token == UserState.track_key(dict(self.current_track or {})):
                self.love_button.setText(previous_text)
                self.love_button.setEnabled(previous_enabled)
            self.statusBar().showMessage(
                f"Could not save preference · {error}",
                5000,
            )

        self._run_async(persist,lambda _result:None,failed)

    def _keep(self):
        if not self.current_track:
            return
        track=dict(self.current_track)
        token=UserState.track_key(track)
        previous_text=self.keep_button.text() if hasattr(self,"keep_button") else "Keep"
        previous_enabled=self.keep_button.isEnabled() if hasattr(self,"keep_button") else True
        if hasattr(self,"keep_button"):
            self.keep_button.setText("✓ Kept")
            self.keep_button.setEnabled(False)
            self.motion.settle(
                self.keep_button,
                duration_ms=FAST_MOTION_MS,
                start_opacity=0.82,
            )
        self.statusBar().showMessage("Kept in taste memory",2500)

        def persist() -> bool:
            self.state.record_keep(track)
            return True

        def failed(error: str) -> None:
            if token == UserState.track_key(dict(self.current_track or {})) and hasattr(self,"keep_button"):
                self.keep_button.setText(previous_text)
                self.keep_button.setEnabled(previous_enabled)
            self.statusBar().showMessage(
                f"Could not save Keep · {error}",
                5000,
            )

        self._run_async(persist,lambda _result:None,failed)

    def _more_actions(self):
        if not self.current_track:return
        label,ok=QInputDialog.getText(self,"Save a moment","Moment note (leave blank if you like):")
        if ok:
            pos=self.player.players[self.player.active].position(); self.state.save_moment(self.current_track,pos,label); self.statusBar().showMessage("Moment saved",3000)

    @staticmethod
    def _resolver_target(track):
        track=dict(track or {}); resolution=track.get("_resolution")
        if isinstance(resolution,dict) and isinstance(resolution.get("requested"),dict):
            requested=dict(resolution.get("requested") or {})
            if str(requested.get("title") or "").strip():return requested
        return {"artist":str(track.get("artist") or ""),"title":str(track.get("title") or ""),"album":str(track.get("album") or ""),"duration":track.get("duration") or 0}

    def _inspect_current_match(self):
        if not self.current_track:
            self.statusBar().showMessage("Play a track first, then inspect its source match",3500); return
        target=self._resolver_target(self.current_track)
        self.statusBar().showMessage("Checking resolver candidates…")
        self._run_async(lambda:self.providers.inspect_resolution(target,24),lambda info:self._show_resolver_inspector(target,info))

    def _show_resolver_inspector(self,target,info):
        d=QDialog(self); d.setWindowTitle("Resolver Inspector"); d.resize(760,560); lay=QVBoxLayout(d)
        requested=f"{target.get('artist','')} — {target.get('title','')}".strip(" —")
        album=str(target.get("album") or ""); head=QLabel(f"Requested: {requested}" + (f"  ·  {album}" if album else "")); head.setWordWrap(True); lay.addWidget(head)
        blocked=int(info.get("blocked_count") or 0); threshold=float(info.get("minimum_score") or 0.62); preferred=info.get("preferred")
        summary=QLabel(f"Automatic threshold: {threshold:.0%}  ·  Wrong matches remembered: {blocked}" + ("  ·  Preferred match remembered" if preferred else "")); summary.setWordWrap(True); summary.setStyleSheet("color:#aab0ba"); lay.addWidget(summary)
        rows=QListWidget(); lay.addWidget(rows,1)
        current_pid=str((self.current_track or {}).get("provider_id") or ""); current_tid=str((self.current_track or {}).get("track_id") or ""); current_row=-1
        for i,row in enumerate(list(info.get("candidates") or [])):
            if not isinstance(row,dict):continue
            t=dict(row.get("track") or {}); score=float(row.get("score") or 0); provider=str(row.get("provider_id") or t.get("provider_id") or "")
            flags=", ".join(list(row.get("flags") or [])); reasons=" · ".join(list(row.get("reasons") or []))
            duration=row.get("duration_delta"); duration_text=(f" · Δ{float(duration):.0f}s" if duration is not None else "")
            star="★ " if bool(row.get("preferred")) else ""
            line1=f"{star}{score:.0%}  {provider}  ·  {t.get('artist','Unknown artist')} — {t.get('title','Unknown track')}"
            line2=f"title {float(row.get('title_score') or 0):.0%} · artist {float(row.get('artist_score') or 0):.0%} · album {float(row.get('album_score') or 0):.0%}{duration_text}"
            if flags:line2+=f" · [{flags}]"
            if reasons:line2+=f"\n{reasons}"
            item=QListWidgetItem(line1+"\n"+line2); item.setData(Qt.UserRole,row); rows.addItem(item)
            if str(t.get("provider_id") or "")==current_pid and str(t.get("track_id") or "")==current_tid:current_row=rows.count()-1
        if rows.count()==0:
            rows.addItem("No resolver candidates were returned by the connected sources.")
        else:rows.setCurrentRow(current_row if current_row>=0 else 0)
        buttons=QHBoxLayout(); play=QPushButton("Play this match"); prefer=QPushButton("Prefer"); wrong=QPushButton("Wrong match"); reset=QPushButton("Reset memory"); close=QPushButton("Close")
        for b in (play,prefer,wrong,reset,close):buttons.addWidget(b)
        lay.addLayout(buttons)
        def selected():
            item=rows.currentItem(); data=item.data(Qt.UserRole) if item else None
            return dict(data or {}) if isinstance(data,dict) else {}
        play.clicked.connect(lambda:self._resolver_use_candidate(target,selected(),d,False))
        prefer.clicked.connect(lambda:self._resolver_use_candidate(target,selected(),d,True))
        wrong.clicked.connect(lambda:self._resolver_wrong_candidate(target,selected(),d))
        reset.clicked.connect(lambda:self._resolver_reset_memory(target,d))
        close.clicked.connect(d.reject)
        d.exec()

    def _resolver_use_candidate(self,target,row,dialog,remember):
        candidate=dict(row.get("track") or {}) if isinstance(row,dict) else {}
        if not candidate:
            self.statusBar().showMessage("Select a resolver candidate first",3000); return
        if remember:self.providers.prefer_resolution(target,candidate)
        dialog.accept(); self.statusBar().showMessage("Using preferred match…" if remember else "Loading selected match…")
        self._run_async(lambda:self.providers.resolve_exact(candidate,target),self._apply_resolver_match)

    def _resolver_wrong_candidate(self,target,row,dialog):
        candidate=dict(row.get("track") or {}) if isinstance(row,dict) else {}
        if not candidate:
            self.statusBar().showMessage("Select a resolver candidate first",3000); return
        self.providers.block_resolution(target,candidate); dialog.accept(); self.statusBar().showMessage("Wrong match remembered · trying the next candidate…")
        self._run_async(lambda:self.providers.resolve(target),self._apply_resolver_match)

    def _resolver_reset_memory(self,target,dialog):
        self.providers.clear_resolution_preference(target); self.providers.clear_resolution_blocks(target); dialog.accept(); self.statusBar().showMessage("Match memory reset for this song",3500)
        self._run_async(lambda:self.providers.inspect_resolution(target,24),lambda info:self._show_resolver_inspector(target,info))

    def _apply_resolver_match(self,resolved):
        if not isinstance(resolved,dict):return
        idx=self.player.index
        if idx<0:self.player.set_queue([resolved],0,True); return
        self.player.queue[idx]=dict(resolved); self.player.queueChanged.emit(self.player.queue); self.player.players[self.player.active].stop(); self.player._load_index(idx,True)
        mode=str((resolved.get("_resolution") or {}).get("mode") or "match") if isinstance(resolved.get("_resolution"),dict) else "match"
        self.statusBar().showMessage(f"Resolver match applied · {mode}",4000)

    def _refresh_queue(self,tracks):
        self.queue_list.clear()
        for i,t in enumerate(tracks):
            prefix="▶ " if i==self.player.index else ""; item=QListWidgetItem(prefix+_track_text(t)); item.setData(Qt.UserRole,i); self.queue_list.addItem(item)
        if hasattr(self, "living_canvas") and self.living_canvas.active_mode == "constellation":
            self.living_canvas.refresh_context()

    def _queue_jump(self,item):
        idx=int(item.data(Qt.UserRole)); self.player.players[self.player.active].stop(); self.player._load_index(idx,True)

    # ------------------------------- LLM
    def _llm_settings(self):
        return LLMSettings(
            provider=self.state.get_text("llm_provider","openwebui"),
            endpoint=self.state.get_text("llm_endpoint",LLMClient.default_endpoint(self.state.get_text("llm_provider","openwebui"))),
            model=self.state.get_text("llm_model",""), api_key=self.state.get_text("llm_api_key","")
        )

    def _translate_lyrics(self, payload: dict[str,Any]) -> None:
        payload=dict(payload or {})
        text=str(payload.get("text") or "").strip()
        if not text:
            return

        settings=self._llm_settings()
        if not str(settings.model or "").strip():
            answer=QMessageBox.question(
                self,
                "Connect an LLM",
                "Lyrics translation uses your optional configured LLM. "
                "No model is configured yet. Open LLM settings now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                return
            self._llm_settings_dialog()
            settings=self._llm_settings()
            if not str(settings.model or "").strip():
                return

        target,ok=QInputDialog.getText(
            self,
            "Translate lyrics",
            "Translate into:",
            text=self.state.get_text("lyrics_translation_language","English"),
        )
        target=str(target or "").strip()
        if not ok or not target:
            return

        endpoint=str(settings.endpoint or LLMClient.default_endpoint(settings.provider))
        answer=QMessageBox.question(
            self,
            "Send lyrics for translation?",
            "This sends the currently displayed lyric text to your configured LLM "
            f"endpoint for this one request:\n\n{endpoint}\n\n"
            "The translation is shown temporarily in Melodex and is not saved.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.state.set_text("lyrics_translation_language",target)
        artist=str(payload.get("artist") or "")
        title=str(payload.get("title") or "")
        prompt=(
            f"Translate the following song lyrics into {target}. "
            "Preserve the original line breaks and stanza structure. "
            "Return only the translation, with no commentary, analysis, title or quotation marks."
            f"\n\nTrack: {artist} — {title}\n\n{text}"
        )
        self.statusBar().showMessage(f"Translating lyrics into {target}…")
        self._run_async(
            lambda:self.llm.complete(settings,prompt,{},[]),
            lambda result:self._show_lyrics_translation(target,str(result or "")),
        )

    def _show_lyrics_translation(self, language: str, text: str) -> None:
        dialog=QDialog(self)
        dialog.setWindowTitle(f"Lyrics translation · {language}")
        dialog.resize(760,720)
        layout=QVBoxLayout(dialog)
        layout.setContentsMargins(22,20,22,18)
        layout.setSpacing(10)

        note=QLabel(
            f"<b>Temporary translation · {_escape_html(language)}</b><br>"
            "<span style='color:#8f9bad'>Generated by your configured LLM. "
            "This translation is not saved by Melodex.</span>"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        browser=QTextEdit()
        browser.setReadOnly(True)
        browser.setPlainText(str(text or "").strip())
        layout.addWidget(browser,1)

        buttons=QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.accept)
        layout.addWidget(buttons)
        self.statusBar().showMessage(f"Lyrics translated into {language}",4000)
        dialog.exec()

    def _llm_settings_dialog(self):
        d=QDialog(self); d.setWindowTitle("Connect an LLM"); f=QFormLayout(d)
        provider=QComboBox(); provider.addItems(["openwebui","ollama","openai","custom"]); provider.setCurrentText(self.state.get_text("llm_provider","openwebui"))
        endpoint=QLineEdit(self.state.get_text("llm_endpoint",LLMClient.default_endpoint(provider.currentText()))); model=QLineEdit(self.state.get_text("llm_model","")); key=QLineEdit(self.state.get_text("llm_api_key","")); key.setEchoMode(QLineEdit.Password)
        provider.currentTextChanged.connect(lambda p:endpoint.setText(LLMClient.default_endpoint(p)))
        f.addRow("Provider",provider); f.addRow("Endpoint",endpoint); f.addRow("Model",model); f.addRow("API key",key)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(d.accept); buttons.rejected.connect(d.reject); f.addRow(buttons)
        if d.exec():
            self.state.set_text("llm_provider",provider.currentText()); self.state.set_text("llm_endpoint",endpoint.text().strip()); self.state.set_text("llm_model",model.text().strip()); self.state.set_text("llm_api_key",key.text().strip())

    def _llm_context(self):
        queue = (
            self.player.queue[self.player.index:self.player.index + 12]
            if self.player.index >= 0
            else []
        )
        return {
            "current_track": llm_track_summary(self.current_track),
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
        settings=self._llm_settings(); self._run_async(lambda:self.llm.complete(settings,prompt,self._llm_context(),[]),lambda text:self._handle_llm(text))

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
        elif typ=="flow_queue":self._flow_queue()
        elif typ=="save_moment":
            if self.current_track:self.state.save_moment(self.current_track,self.player.players[self.player.active].position(),str(args.get("label", "")))
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
        )

    def _finish_ai_playlist(self,playlist_id,name,description,result,requested=None,source="llm"):
        tracks=list(result.get("tracks") or []); unresolved=list(result.get("unresolved") or [])
        payload={"tracks":tracks,"unresolved":unresolved,"requested":int(result.get("requested") or len(tracks)+len(unresolved))}
        if requested is not None:payload["requested_tracks"]=[dict(x) for x in requested]
        self.state.save_playlist(playlist_id,name,description,source,payload); self._refresh_playlists()
        if tracks:self.player.set_queue(tracks,0,True)
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
                tracks=[dict(x) for x in list(args.get("tracks") or []) if isinstance(x,dict)]; self.player.set_queue(tracks,int(args.get("start",0)),bool(args.get("autoplay",True))); result=self.player.status()
            elif action=="append_queue":
                tracks=[dict(x) for x in list(args.get("tracks") or []) if isinstance(x,dict)]; self.player.append_queue(tracks,bool(args.get("autoplay",False))); result=self.player.status()
            elif action=="play_pause":self.player.play_pause(); result=self.player.status()
            elif action=="next":self.player.next(); result=self.player.status()
            elif action=="previous":self.player.previous(); result=self.player.status()
            elif action=="stop":self.player.stop(); result=self.player.status()
            elif action=="clear_queue":self.player.clear_queue(); result=self.player.status()
            elif action=="seek_ms":self.player.seek(int(args.get("value",0))); result=self.player.status()
            elif action=="set_volume":self.player.set_volume(float(args.get("value",1.0))); result=self.player.status()
            elif action=="flow_queue":self._flow_queue(); result={"started":True,"queue_length":len(self.player.queue)}
            elif action=="love_current":self._feedback(True); result={"recorded":bool(self.current_track)}
            elif action=="dislike_current":self._feedback(False); result={"recorded":bool(self.current_track)}
            elif action=="keep_current":self._keep(); result={"recorded":bool(self.current_track)}
            elif action=="save_moment":
                if self.current_track:
                    moment_id=self.state.save_moment(self.current_track,self.player.players[self.player.active].position(),str(args.get("label", ""))); result={"saved":True,"id":moment_id}
                else:result={"saved":False,"reason":"nothing playing"}
            elif action=="open_view":
                view=str(args.get("view","home")); self.open_page(view if view in self.pages else "home"); result={"page":self.current_page}
            else:raise RuntimeError(f"Unsupported control action: {action}")
            box["result"]=result
        except Exception as exc:box["error"]=str(exc)
        finally:event.set()

    def _start_local_bridge(self):
        if self.bridge:return
        try:
            self.bridge=ProviderBridge(self.providers,"127.0.0.1",0,controller=self._control_request,state_path=self.data_dir/"bridge.json"); self.bridge.start()
        except Exception as exc:
            self.bridge=None; self.statusBar().showMessage(f"AI control bridge could not start: {exc}",7000)

    def _restart_bridge(self,host):
        token=self.bridge.token if self.bridge else ""; port=self.bridge.port if self.bridge else 0
        if self.bridge:self.bridge.stop()
        self.bridge=ProviderBridge(self.providers,host,port,token=token,controller=self._control_request,state_path=self.data_dir/"bridge.json"); self.bridge.start()

    def _bridge_dialog(self):
        if not self.bridge:
            self._start_local_bridge()
            if not self.bridge:return
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
    def _run_async(
        self,
        fn,
        done,
        on_error=None,
        *,
        priority="foreground",
        lane="default",
        label="",
    ):
        sig=WorkerSignals()
        sig.done.connect(lambda result: None if self._closing else done(result))
        if on_error is None:
            sig.error.connect(
                lambda e: None if self._closing else QMessageBox.warning(self,"Melodex",e)
            )
        else:
            sig.error.connect(lambda e: None if self._closing else on_error(e))
        self._last_worker=sig

        def work():
            try:
                sig.done.emit(fn())
            except Exception as exc:
                sig.error.emit(str(exc))

        return self.background.submit(
            work,
            priority=priority,
            lane=lane,
            label=label,
        )

    def closeEvent(self,event):
        if self.music_live_active:
            self._journey_live_stop("application closed")
        if hasattr(self, "responsiveness"):
            self.responsiveness.stop()
        self._closing = True
        runner=self._local_scan_runner
        if runner is not None:
            runner.shutdown()
            self._local_scan_runner=None
        if self.bridge:self.bridge.stop()
        if hasattr(self,"background"):
            self.background.shutdown(wait=False,cancel_pending=True)
        self.player.close(); self.metadata.close(); self.providers.close(); self.flow.close(); self.knowledge.close(); self.state.close(); super().closeEvent(event)
