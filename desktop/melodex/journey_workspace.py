from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QMenu,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .journey_archive import JourneyArchive
from .ux_components import set_help


def _track_text(track: dict[str, Any]) -> str:
    artist = str(track.get("artist") or "Unknown artist")
    title = str(track.get("title") or "Unknown track")
    source = str(track.get("provider_id") or "")
    return f"{artist} — {title}" + (f"   ·   {source}" if source else "")


class JourneyWorkspace(QObject):
    """Own the Music Map/Journey UI, state and orchestration.

    Domain algorithms remain in the existing Qt-free journey/path/map modules.
    MainWindow integrates through semantic signals and explicit service getters.
    """

    navigationRequested = Signal(str)
    playTracksRequested = Signal(object)
    queueTracksRequested = Signal(object)
    replaceUpcomingRequested = Signal(object)
    queueTrackReasonsRequested = Signal(object)
    nextTrackRequested = Signal()
    sessionFromTrackRequested = Signal(object)
    surpriseMeRequested = Signal()
    protectQueueTrackRequested = Signal(int)
    statusMessageRequested = Signal(str, int)

    def __init__(
        self,
        providers: Any,
        user_state: Any,
        flow: Any,
        *,
        local_intelligence: Callable[[], Any],
        knowledge: Callable[[], Any],
        metadata: Callable[[], Any],
        run_async: Callable[..., Any],
        current_track: Callable[[], dict[str, Any] | None],
        page_titles: dict[str, QLabel],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.providers = providers
        self.state = user_state
        self.flow = flow
        self._local_intelligence_getter = local_intelligence
        self._knowledge_getter = knowledge
        self._metadata_getter = metadata
        self._run_async = run_async
        self._current_track_getter = current_track
        self.page_titles = page_titles

        self.music_map_page = QWidget()
        self.music_map_built = False
        self._designer_open_pending = False

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

        self.archive = JourneyArchive(
            self.state,
            current_design=self._archive_design_snapshot,
            page_titles=self.page_titles,
        )
        self.archive.designRequested.connect(self.open_designer)
        self.archive.recipeLoadRequested.connect(self._queue_recipe_load)
        self.archive.replayRequested.connect(self._queue_replay)
        self.archive.recipeActivated.connect(self._archive_recipe_activated)
        self.archive.recipeDeleted.connect(self._archive_recipe_deleted)
        self.archive.statusMessageRequested.connect(self.statusMessageRequested.emit)
        self.journeys_page = self.archive.page
        self.pages = {
            "music_map": self.music_map_page,
            "journeys": self.journeys_page,
        }

    @property
    def local_intelligence(self) -> Any:
        return self._local_intelligence_getter()

    @property
    def knowledge(self) -> Any:
        return self._knowledge_getter()

    @property
    def metadata(self) -> Any:
        return self._metadata_getter()

    @property
    def current_track(self) -> dict[str, Any] | None:
        track = self._current_track_getter()
        return dict(track) if isinstance(track, dict) else None

    def _status(self, message: str, timeout_ms: int = 0) -> None:
        self.statusMessageRequested.emit(str(message), int(timeout_ms))

    def _dialog_parent(self) -> QWidget:
        return self.music_map_page if self.music_map_built else self.journeys_page

    @staticmethod
    def _clear_layout_items(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            child = item.layout()
            if child is not None:
                JourneyWorkspace._clear_layout_items(child)
                child.deleteLater()
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _page_layout(self, page: str, title: str, subtitle: str = ""):
        target = self.pages[page]
        existing = target.layout()
        if existing is None:
            layout = QVBoxLayout(target)
        else:
            layout = existing
            self._clear_layout_items(layout)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        layout.addWidget(title_label)
        self.page_titles[page] = title_label
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setWordWrap(True)
            subtitle_label.setObjectName("pageSubtitle")
            layout.addWidget(subtitle_label)
        return layout

    def build_music_map(self) -> None:
        if self.music_map_built:
            return
        self._build_music_map()
        self.music_map_built = True
        if self._designer_open_pending:
            self._designer_open_pending = False
            self._show_designer_tools()

    def refresh_music_map(self) -> None:
        if self.music_map_built:
            self._refresh_music_map()

    def refresh_journeys(self) -> None:
        self.archive.refresh()

    def refresh_knowledge_graph(self) -> None:
        if not self.music_map_built or not hasattr(self, "music_map"):
            return
        from .music_knowledge import build_knowledge_graph

        ref_map = dict(self.music_map.ref_map or {})
        knowledge = self.knowledge.snapshot(ref_map)
        self.music_map.set_knowledge_graph(
            build_knowledge_graph(ref_map, knowledge)
        )

    def open_designer(self) -> None:
        self.navigationRequested.emit("music_map")
        if self.music_map_built:
            self._show_designer_tools()
        else:
            self._designer_open_pending = True
        self._status(
            "Journey design ready · select a track for the start, another for the destination, then shape the route",
            6000,
        )

    def _show_designer_tools(self) -> None:
        self.music_map_power_scroll.show()
        self.music_map_planner_tabs.setCurrentWidget(self.music_map_journey_panel)
        self.music_path_steps.show()

    def on_track_changed(self, track: dict[str, Any]) -> None:
        if self.music_map_built:
            self.music_map.highlight_track(track)
        if not self.music_live_active:
            return
        current_ref = self._music_ref_for_track(dict(track or {}))
        if current_ref and (
            not self.music_live_played_refs
            or self.music_live_played_refs[-1] != current_ref
        ):
            self.music_live_played_refs.append(current_ref)
        if current_ref and current_ref == self.music_live_destination_ref:
            self._journey_live_stop("destination reached")
        else:
            self._journey_live_update_label()

    def on_manual_advance(
        self,
        previous: object,
        current: object,
        played_ms: int,
        duration_ms: int,
    ) -> None:
        self._on_manual_advance(previous, current, played_ms, duration_ms)

    def shutdown(self) -> None:
        if self.music_live_active:
            self._journey_live_stop("application closed")

    def _build_music_map(self):
        from .music_journey import STAGE_LABELS
        from .music_map import MusicMapWidget
    
        l=self._page_layout("music_map", "Music Map")
        self.page_titles["music_map"].setStyleSheet("font-size:19px;font-weight:700")
    
        simple=QHBoxLayout()
        self.music_map_options_button=QPushButton("More…")
        self.music_map_options_button.setObjectName("quietButton")
        self.music_map_options_button.clicked.connect(self._toggle_music_map_options)
        self.music_map_play_button=QPushButton("▶ Play selected")
        self.music_map_play_button.clicked.connect(self._play_music_map_selected)
        self.music_map_play_button.setEnabled(False)
        self.music_map_queue_button=QPushButton("+ Queue selected")
        self.music_map_queue_button.clicked.connect(self._queue_music_map_selected)
        self.music_map_queue_button.setEnabled(False)
        self.music_map_plan_button=QPushButton("Journey")
        self.music_map_plan_button.setObjectName("secondaryButton")
        self.music_map_plan_button.clicked.connect(self._toggle_music_map_tools)
        self.music_map_surprise_button=QPushButton("Surprise me")
        self.music_map_surprise_button.setObjectName("secondaryButton")
        self.music_map_surprise_button.setAccessibleName(
            "Create a surprise listening session from local music"
        )
        self.music_map_surprise_button.setToolTip(
            "Build an exploratory playlist from your available local music"
        )
        self.music_map_surprise_button.clicked.connect(self.surpriseMeRequested.emit)
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
        simple.addWidget(self.music_map_surprise_button)
        simple.addWidget(self.music_map_plan_button)
        l.addLayout(simple)
    
        self.music_map_options_panel=QFrame(self.music_map_page)
        self.music_map_options_panel.setObjectName("powerPanel")
        map_options=QVBoxLayout(self.music_map_options_panel)
        map_options.setContentsMargins(12,8,12,8)
        improve=QPushButton("Analyse local music")
        improve.clicked.connect(self._analyse_library_for_map)
        refresh_map=QPushButton("Refresh")
        refresh_map.clicked.connect(self._refresh_music_map)
        enrich_selected=QPushButton("Find selected track details")
        enrich_selected.clicked.connect(self._enrich_selected_map_knowledge)
        enrich_map=QPushButton("Find details for 8 tracks")
        enrich_map.clicked.connect(self._enrich_map_knowledge_batch)
        map_options.addWidget(QLabel("Map tools"))
        map_options.addWidget(improve)
        map_options.addWidget(refresh_map)
        map_options.addWidget(enrich_selected)
        map_options.addWidget(enrich_map)
        map_options.addStretch(1)
        # Floating controls must not consume height from the map canvas.
        self.music_map_options_panel.hide()
    
        self.music_map_power_panel=QFrame()
        self.music_map_power_panel.setObjectName("powerPanel")
        power=QVBoxLayout(self.music_map_power_panel)
        power.setContentsMargins(13,11,13,11)
        power.setSpacing(8)
    
        top=QGridLayout()
        top.setHorizontalSpacing(7)
        top.setVerticalSpacing(6)
        power_title=QLabel("Route planner")
        power_title.setStyleSheet("font-size:15px;font-weight:700")
        start_here=QPushButton("Start listening here")
        start_here.clicked.connect(self._journey_from_music_map)
        journey_options=QPushButton("Journey options…")
        journey_options.setObjectName("quietButton")
        journey_options.clicked.connect(self._toggle_music_journey_options)
        close_tools=QPushButton("Close")
        close_tools.setAccessibleName("Close Journey tools")
        close_tools.setObjectName("quietButton")
        close_tools.clicked.connect(self._toggle_music_map_tools)
        top.addWidget(power_title,0,0)
        top.addWidget(close_tools,0,2)
        top.addWidget(start_here,1,0)
        top.addWidget(journey_options,1,1)
        top.setColumnStretch(1,1)
        power.addLayout(top)
    
        path_grid=QGridLayout()
        path_grid.setHorizontalSpacing(7)
        path_grid.setVerticalSpacing(6)
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
        find_path.setObjectName("primaryButton")
        find_path.clicked.connect(self._music_path_find)
        play_path=QPushButton("▶ Play route")
        play_path.setObjectName("secondaryButton")
        play_path.clicked.connect(self._music_path_play)
        queue_path=QPushButton("+ Queue route")
        queue_path.setObjectName("secondaryButton")
        queue_path.clicked.connect(self._music_path_queue)
        clear_path=QPushButton("Clear")
        clear_path.setObjectName("quietButton")
        clear_path.clicked.connect(self._music_path_clear)
        self.music_path_label=QLabel("Start —  →  Destination —")
        self.music_path_label.setStyleSheet("color:#aab0ba")
        path_grid.addWidget(QLabel("Route"),0,0)
        path_grid.addWidget(self.music_path_mode,0,1)
        path_grid.addWidget(set_start,0,2)
        path_grid.addWidget(set_end,0,3)
        path_grid.addWidget(find_path,1,0)
        path_grid.addWidget(play_path,1,1)
        path_grid.addWidget(queue_path,1,2)
        path_grid.addWidget(clear_path,1,3)
        path_grid.addWidget(self.music_path_label,2,0,1,4)
        path_grid.setColumnStretch(3,1)
        self.music_map_route_tab=QWidget()
        route_tab_layout=QVBoxLayout(self.music_map_route_tab)
        route_tab_layout.setContentsMargins(4,6,4,4)
        route_tab_layout.addLayout(path_grid)
        route_tab_layout.addStretch(1)
    
        self.music_map_journey_panel=QFrame()
        self.music_map_journey_panel.setObjectName("subtlePanel")
        journey_box=QVBoxLayout(self.music_map_journey_panel)
        journey_box.setContentsMargins(10,8,10,8)
        journey_box.setSpacing(7)
    
        preset_button=QToolButton()
        preset_button.setText("Starting shapes ▾")
        preset_button.setObjectName("quietButton")
        preset_button.setPopupMode(QToolButton.InstantPopup)
        preset_menu=QMenu(preset_button)
        for title,keys in (
            ("Gentle → darker → energy",["calm","dark","forgotten","energetic"]),
            ("Calm → rhythm → energy",["calm","rhythmic","energetic"]),
            ("Familiar → rediscovery → bright",["familiar","forgotten","bright"]),
            ("Surprising → darker → bright",["surprising","dark","bright"]),
        ):
            action=preset_menu.addAction(title)
            action.triggered.connect(
                lambda _checked=False, stage_keys=list(keys):self._music_journey_load_preset(stage_keys)
            )
        preset_button.setMenu(preset_menu)
        set_help(
            preset_button,
            "Starting shapes",
            "Load a suggested sequence as a starting point. You can then add, remove, or rearrange every stage.",
        )
        build_journey=QPushButton("Build journey")
        build_journey.setObjectName("primaryButton")
        build_journey.clicked.connect(self._music_journey_build)
        add_track=QPushButton("Add selected track")
        add_track.clicked.connect(self._music_journey_add_track)
        set_help(add_track,"Add selected track","Add the selected Music Map track as an exact waypoint in this route.")

        palette_header=QHBoxLayout()
        palette_header.addWidget(QLabel("Add a direction"))
        palette_header.addWidget(add_track)
        palette_header.addStretch(1)
        palette_header.addWidget(preset_button)
        palette_header.addWidget(build_journey)
        journey_box.addLayout(palette_header)

        from .journey_composer import JourneyStagePaletteButton
        self.music_journey_palette_buttons={}
        palette_rows=QGridLayout()
        palette_rows.setHorizontalSpacing(6)
        palette_rows.setVerticalSpacing(5)
        palette_rows.addWidget(QLabel("Sound & feel"),0,0)
        palette_rows.addWidget(QLabel("Discovery"),1,0)
        for row,keys in (
            (0,("calm","dark","energetic","bright","rhythmic")),
            (1,("familiar","forgotten","surprising")),
        ):
            for column,key in enumerate(keys,start=1):
                button=JourneyStagePaletteButton(
                    STAGE_LABELS[key],
                    {"type":"constraint","constraint":key,"label":STAGE_LABELS[key]},
                )
                button.clicked.connect(
                    lambda _checked=False, stage_key=key:self._music_journey_add_constraint(stage_key)
                )
                self.music_journey_palette_buttons[key]=button
                palette_rows.addWidget(button,row,column)
        palette_rows.setColumnStretch(6,1)
        journey_box.addLayout(palette_rows)

        from .journey_composer import JourneyEndpointDropTarget
        journey_sequence=QHBoxLayout()
        journey_sequence.setSpacing(6)
        self.music_journey_start_endpoint=JourneyEndpointDropTarget("start")
        self.music_journey_start_endpoint.setMinimumWidth(180)
        self.music_journey_start_endpoint.setMaximumWidth(270)
        self.music_journey_start_endpoint.setMinimumHeight(96)
        self.music_journey_start_endpoint.clicked.connect(self._music_path_set_start)
        self.music_journey_start_endpoint.trackDropped.connect(
            lambda stage:self._music_path_set_endpoint("start",stage)
        )
        journey_sequence.addWidget(self.music_journey_start_endpoint,1)
        endpoint_arrow=QLabel("→")
        endpoint_arrow.setObjectName("mutedText")
        endpoint_arrow.setAccessibleName("through the journey stages")
        journey_sequence.addWidget(endpoint_arrow)
        from .journey_composer import JourneyStageTimeline
        self.music_journey_stages=JourneyStageTimeline()
        journey_sequence.addWidget(self.music_journey_stages,4)
        endpoint_arrow=QLabel("→")
        endpoint_arrow.setObjectName("mutedText")
        endpoint_arrow.setAccessibleName("to the destination")
        journey_sequence.addWidget(endpoint_arrow)
        self.music_journey_end_endpoint=JourneyEndpointDropTarget("destination")
        self.music_journey_end_endpoint.setMinimumWidth(180)
        self.music_journey_end_endpoint.setMaximumWidth(270)
        self.music_journey_end_endpoint.setMinimumHeight(96)
        self.music_journey_end_endpoint.clicked.connect(self._music_path_set_end)
        self.music_journey_end_endpoint.trackDropped.connect(
            lambda stage:self._music_path_set_endpoint("destination",stage)
        )
        journey_sequence.addWidget(self.music_journey_end_endpoint,1)
        journey_box.addLayout(journey_sequence)
        self.music_journey_stages.orderChanged.connect(
            self._music_journey_stage_order_changed
        )
        set_help(
            self.music_journey_stages,
            "Journey stages",
            "This is the order your route follows between its start and destination. "
            "Drag a direction from the palette or a track from Music Map into a position; "
            "drag stages to reorder them. Move up / Move down remain available.",
        )

        remove_stage=QPushButton("Remove")
        remove_stage.clicked.connect(self._music_journey_remove_stage)
        clear_stages=QPushButton("Clear shape")
        clear_stages.clicked.connect(self._music_journey_clear_stages)
        move_stage_up=QPushButton("Move up")
        move_stage_up.clicked.connect(lambda:self._music_journey_move_stage(-1))
        move_stage_down=QPushButton("Move down")
        move_stage_down.clicked.connect(lambda:self._music_journey_move_stage(1))
        set_help(move_stage_up,"Move stage up","Put the selected journey stage earlier in the route. Keyboard: Alt+↑.")
        set_help(move_stage_down,"Move stage down","Put the selected journey stage later in the route. Keyboard: Alt+↓.")
        edit_actions=QHBoxLayout()
        edit_actions.addWidget(move_stage_up)
        edit_actions.addWidget(move_stage_down)
        edit_actions.addWidget(remove_stage)
        edit_actions.addWidget(clear_stages)
        edit_actions.addStretch(1)
        play_journey=QPushButton("▶ Play")
        play_journey.clicked.connect(self._music_path_play)
        queue_journey=QPushButton("+ Queue")
        queue_journey.clicked.connect(self._music_path_queue)
        edit_actions.addWidget(play_journey)
        edit_actions.addWidget(queue_journey)
        journey_box.addLayout(edit_actions)
    
        live_grid=QGridLayout()
        live_grid.setHorizontalSpacing(7)
        live_grid.setVerticalSpacing(6)
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
        skip_replan.clicked.connect(lambda: self.nextTrackRequested.emit())
        replan=QPushButton("Replan")
        replan.clicked.connect(lambda:self._journey_live_replan("",reason="manual replan"))
        restore=QPushButton("Restore design")
        restore.clicked.connect(self._journey_live_restore)
        stop_live=QPushButton("Stop live")
        stop_live.clicked.connect(self._journey_live_stop)
        self.music_live_label=QLabel("Live journey inactive")
        self.music_live_label.setStyleSheet("color:#aab0ba")
        live_grid.addWidget(QLabel("While listening"),0,0)
        live_grid.addWidget(play_live,0,1)
        live_grid.addWidget(self.music_live_steering,0,2)
        live_grid.addWidget(apply_steer,0,3)
        live_grid.addWidget(avoid_artist,1,0)
        live_grid.addWidget(skip_replan,1,1)
        live_grid.addWidget(replan,1,2)
        live_grid.addWidget(restore,2,0)
        live_grid.addWidget(stop_live,2,1)
        live_grid.addWidget(self.music_live_label,2,2,1,2)
        live_grid.setColumnStretch(2,1)
        self.music_map_live_tab=QWidget()
        live_tab_layout=QVBoxLayout(self.music_map_live_tab)
        live_tab_layout.setContentsMargins(10,8,10,8)
        live_tab_layout.addLayout(live_grid)
        live_tab_layout.addStretch(1)

        self.music_map_planner_tabs=QTabWidget()
        self.music_map_planner_tabs.addTab(self.music_map_route_tab,"Route")
        self.music_map_planner_tabs.addTab(self.music_map_journey_panel,"Compose")
        self.music_map_planner_tabs.addTab(self.music_map_live_tab,"Live")
        power.addWidget(self.music_map_planner_tabs)
    
        self.music_map_power_scroll=QScrollArea(self.music_map_page)
        self.music_map_power_scroll.setWidgetResizable(True)
        self.music_map_power_scroll.setFrameShape(QFrame.NoFrame)
        self.music_map_power_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.music_map_power_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.music_map_power_scroll.setMinimumHeight(108)
        self.music_map_power_scroll.setMaximumHeight(600)
        self.music_map_power_scroll.setWidget(self.music_map_power_panel)
        self.music_map_power_scroll.hide()
    
        self.music_map=MusicMapWidget(self.music_map_page)
        self.music_map.trackSelected.connect(self._music_map_selection_changed)
        self.music_map.trackActivated.connect(self._play_music_map_track)
        self.music_map.artworkRequested.connect(self._music_map_artwork_requested)
        self.music_map.view_button.clicked.connect(self._on_music_map_view_changed)
        l.addWidget(self.music_map,1)

        # Contextual track actions float over the scene, never in the page layout.
        self.music_map_track_panel=QFrame(self.music_map_page)
        self.music_map_track_panel.setObjectName("powerPanel")
        track_layout=QVBoxLayout(self.music_map_track_panel)
        track_layout.setContentsMargins(12,9,12,9)
        track_layout.setSpacing(6)
        self.music_map_track_label=QLabel("")
        self.music_map_track_label.setObjectName("mapSelectedTrack")
        self.music_map_track_label.setAccessibleName("Selected Music Map track")
        self._music_map_track_full_label=""
        track_layout.addWidget(self.music_map_track_label)
        track_actions=QHBoxLayout()
        self.music_map_play_button.setText("▶ Play")
        self.music_map_queue_button.setText("+ Queue")
        track_actions.addWidget(self.music_map_play_button)
        track_actions.addWidget(self.music_map_queue_button)
        track_layout.addLayout(track_actions)
        listening_actions=QHBoxLayout()
        self.music_map_listen_here_button=QPushButton("Play from here")
        self.music_map_listen_here_button.setObjectName("primaryButton")
        self.music_map_listen_here_button.setEnabled(False)
        self.music_map_listen_here_button.setToolTip(
            "Build a listening session beginning with this selected track"
        )
        self.music_map_listen_here_button.setAccessibleName(
            "Play a listening session starting from the selected track"
        )
        self.music_map_listen_here_button.clicked.connect(self._journey_from_music_map)
        listening_actions.addWidget(self.music_map_listen_here_button)
        self.music_map_start_journey_button=QPushButton("Plan a journey")
        self.music_map_start_journey_button.setObjectName("secondaryButton")
        self.music_map_start_journey_button.setToolTip(
            "Choose a destination and preview a route between tracks"
        )
        self.music_map_start_journey_button.clicked.connect(self._start_music_map_journey)
        listening_actions.addWidget(self.music_map_start_journey_button)
        track_layout.addLayout(listening_actions)
        self.music_map_nearby_label=QLabel("Explore nearby")
        self.music_map_nearby_label.setObjectName("mutedText")
        track_layout.addWidget(self.music_map_nearby_label)
        neighbours=QHBoxLayout()
        neighbours.setSpacing(6)
        self._music_map_related_refs: list[str]=[]
        self._music_map_related_rows: list[dict[str, Any]]=[]
        self.music_map_related_buttons: list[QPushButton]=[]
        for index in range(2):
            button=QPushButton("")
            button.setObjectName("quietButton")
            button.setAccessibleName(f"Explore related track {index + 1}")
            button.clicked.connect(
                lambda _checked=False, i=index: self._focus_music_map_related(i)
            )
            neighbours.addWidget(button,1)
            self.music_map_related_buttons.append(button)
            button.hide()
        track_layout.addLayout(neighbours)
        self.music_map_nearby_label.hide()
        self.music_map_track_panel.hide()
    
        self.music_path_steps=QListWidget()
        self.music_path_steps.setMaximumHeight(116)
        self.music_path_steps.addItem("Route explanations will appear here after you plan one.")
        self.music_path_steps.hide()
        power.addWidget(self.music_path_steps)

        # Position the panels over the canvas (rather than in its layout).
        # Reposition on map resize/move; the QGraphicsView keeps its viewport.
        self.music_map.installEventFilter(self)
        self._music_map_escape=QShortcut(QKeySequence(Qt.Key_Escape),self.music_map_page)
        self._music_map_escape.setContext(Qt.WidgetWithChildrenShortcut)
        self._music_map_escape.activated.connect(self._dismiss_music_map_overlays)
        QTimer.singleShot(0, self._position_music_map_overlays)
    
    
    def _position_music_map_overlays(self) -> None:
        """Position overlays inside the graphics view, not over the search bar."""
        if not hasattr(self, "music_map"):
            return
        viewport = self.music_map.view.geometry()
        origin = self.music_map.mapTo(self.music_map_page, viewport.topLeft())
        if viewport.width() <= 0 or viewport.height() <= 0:
            return
        margin = 10
        left, top = origin.x(), origin.y()
        available_width = max(1, viewport.width() - 2 * margin)
        available_height = max(1, viewport.height() - 2 * margin)
        self.music_map_options_panel.setGeometry(
            left + margin,
            top + margin,
            min(285, available_width),
            min(260, available_height),
        )
        journey_width = min(440, available_width)
        self.music_map_power_scroll.setGeometry(
            left + viewport.width() - journey_width - margin,
            top + margin,
            journey_width,
            min(540, available_height),
        )
        if hasattr(self, "music_map_track_panel"):
            track_width = min(430, available_width)
            track_height = min(
                188 if self._music_map_related_refs else 140, available_height
            )
            self.music_map_track_panel.setGeometry(
                left + margin,
                top + viewport.height() - track_height - margin,
                track_width,
                track_height,
            )
            self._sync_music_map_track_panel()

    def _sync_music_map_track_panel(self) -> None:
        """Hide contextual actions while a tool is open; preserve selection."""
        if not hasattr(self, "music_map_track_panel"):
            return
        if self._music_map_track_full_label:
            self.music_map_track_label.setText(
                self.music_map_track_label.fontMetrics().elidedText(
                    self._music_map_track_full_label,
                    Qt.ElideRight,
                    max(30, self.music_map_track_panel.width() - 24),
                )
            )
            self.music_map_track_label.setToolTip(self._music_map_track_full_label)
        for i, button in enumerate(self.music_map_related_buttons):
            if i < len(self._music_map_related_rows):
                row = self._music_map_related_rows[i]
                label = f'{row["kind"]} · {row["artist"]} — {row["title"]}'
                button.setText(
                    button.fontMetrics().elidedText(
                        label, Qt.ElideRight,
                        max(55, (self.music_map_track_panel.width() - 42) // 2),
                    )
                )
        tool_open = (
            self.music_map_power_scroll.isVisible()
            or self.music_map_options_panel.isVisible()
            or self.music_map.view_settings_panel.isVisible()
        )
        selected = bool(self.music_map.selected_track())
        self.music_map_track_panel.setVisible(selected and not tool_open)
        if selected and not tool_open:
            self.music_map_track_panel.raise_()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if hasattr(self, "music_map") and watched is self.music_map:
            if event.type() in (QEvent.Resize, QEvent.Move, QEvent.Show):
                QTimer.singleShot(0, self._position_music_map_overlays)
        return super().eventFilter(watched, event)

    def _toggle_music_map_options(self) -> None:
        visible = not self.music_map_options_panel.isVisible()
        if visible:
            self.music_map.view_settings_panel.hide()
            self.music_map_power_scroll.hide()
            self.music_path_steps.hide()
        self._position_music_map_overlays()
        self.music_map_options_panel.setVisible(visible)
        if visible:
            self.music_map_options_panel.raise_()
        self._sync_music_map_track_panel()

    def _toggle_music_map_tools(self) -> None:
        visible = not self.music_map_power_scroll.isVisible()
        if visible:
            self.music_map.view_settings_panel.hide()
            self.music_map_options_panel.hide()
        self._position_music_map_overlays()
        self.music_map_power_scroll.setVisible(visible)
        self.music_path_steps.setVisible(visible)
        if visible:
            self.music_map_power_scroll.raise_()
            if hasattr(self, "music_map_planner_tabs"):
                self.music_map_planner_tabs.setCurrentWidget(self.music_map_route_tab)
            self._status(
                "Journey ready · select a start and destination on the map",
                5000,
            )
        self._sync_music_map_track_panel()

    def _toggle_music_journey_options(self) -> None:
        if not self.music_map_power_scroll.isVisible():
            self.music_map.view_settings_panel.hide()
            self.music_map_options_panel.hide()
            self._position_music_map_overlays()
            self.music_map_power_scroll.show()
            self.music_path_steps.show()
            self.music_map_power_scroll.raise_()
        if hasattr(self, "music_map_planner_tabs"):
            self.music_map_planner_tabs.setCurrentWidget(self.music_map_journey_panel)
        self._sync_music_map_track_panel()

    def _on_music_map_view_changed(self) -> None:
        if self.music_map.view_settings_panel.isVisible():
            self.music_map_options_panel.hide()
            self.music_map_power_scroll.hide()
            self.music_path_steps.hide()
        self._sync_music_map_track_panel()

    def _dismiss_music_map_overlays(self) -> None:
        # Preserve selected track and ongoing audio when closing an overlay.
        if self.music_map_power_scroll.isVisible():
            self.music_map_power_scroll.hide()
            self.music_path_steps.hide()
        elif self.music_map_options_panel.isVisible():
            self.music_map_options_panel.hide()
        elif self.music_map.view_settings_panel.isVisible():
            self.music_map.view_settings_panel.hide()
        self._sync_music_map_track_panel()

    def _start_music_map_journey(self) -> None:
        if not self._music_map_selected():
            return
        self._music_path_set_start()
        if not self.music_map_power_scroll.isVisible():
            self._toggle_music_map_tools()
        self.music_map_planner_tabs.setCurrentWidget(self.music_map_route_tab)
        self._status("Select a destination track, then choose Use selected as destination", 5000)

    def _focus_music_map_related(self, index: int) -> None:
        """Navigate to a genuine graph neighbour without changing playback."""
        if 0 <= index < len(self._music_map_related_refs):
            self.music_map.focus_ref(self._music_map_related_refs[index])

    def _music_map_selection_changed(self, track: object) -> None:
        enabled = isinstance(track, dict) and bool(track)
        self.music_map_play_button.setEnabled(enabled)
        self.music_map_queue_button.setEnabled(enabled)
        self.music_map_listen_here_button.setEnabled(enabled)
        self.music_map_start_journey_button.setEnabled(enabled)
        self._music_map_track_full_label = _track_text(dict(track)) if enabled else ""
        rows = (
            self.music_map.related_tracks(self.music_map.selected_ref_value(), limit=2)
            if enabled else []
        )
        self._music_map_related_rows = list(rows)
        self._music_map_related_refs = [str(row["ref"]) for row in rows]
        self.music_map_nearby_label.setVisible(bool(rows))
        for i, button in enumerate(self.music_map_related_buttons):
            if i >= len(rows):
                button.hide()
                continue
            row = rows[i]
            label = f'{row["kind"]} · {row["artist"]} — {row["title"]}'
            button.setToolTip(label + "\n" + str(row["reason"]))
            button.show()
        self._position_music_map_overlays()
        self._sync_music_map_track_panel()

    def _archive_design_snapshot(self) -> dict[str, Any]:
        ref_map = (
            dict(self.music_map.ref_map or {})
            if self.music_map_built and hasattr(self, "music_map")
            else {}
        )
        mode = (
            str(self.music_path_mode.currentData() or "balanced")
            if self.music_map_built and hasattr(self, "music_path_mode")
            else "balanced"
        )
        return {
            "stages": list(self.music_journey_stages_data),
            "mode": mode,
            "ref_map": ref_map,
            "active_recipe": dict(self.music_active_recipe),
        }

    def _queue_recipe_load(self, pending: object) -> None:
        row = dict(pending or {}) if isinstance(pending, dict) else {}
        if not row:
            return
        self.pending_journey_recipe = row
        self.navigationRequested.emit("music_map")
        self._status("Refreshing Music Map before loading recipe…", 3500)

    def _queue_replay(self, snapshot: object, label: str) -> None:
        route = dict(snapshot or {}) if isinstance(snapshot, dict) else {}
        if not route:
            return
        self.pending_journey_replay = (route, str(label or "Journey replay"))
        self.navigationRequested.emit("music_map")
        self._status(f"Refreshing Music Map before {str(label or 'journey replay').lower()}…", 3500)

    def _archive_recipe_activated(self, recipe_id: str, recipe: object) -> None:
        self.music_active_recipe_id = str(recipe_id or "")
        self.music_active_recipe = dict(recipe or {}) if isinstance(recipe, dict) else {}

    def _archive_recipe_deleted(self, recipe_id: str) -> None:
        if self.music_active_recipe_id == str(recipe_id or ""):
            self.music_active_recipe_id = ""
            self.music_active_recipe = {}

    def _refresh_journeys(self) -> None:
        self.archive.refresh()

    def _apply_pending_journey_recipe(self):
        from .journey_recipe import materialize_recipe_stages
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
            QMessageBox.warning(self._dialog_parent(),"Could not load journey recipe",str(exc)); return
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
                self._dialog_parent(),
                "Recipe loaded with missing waypoints",
                "The semantic stages were loaded, but these exact track waypoints "
                f"are not present on the current Music Map:\n\n{names}",
            )
        self._status(
            f"Loaded recipe · {recipe.get('name') or 'Journey recipe'} · choose start and destination",
            6000,
        )
    
    
    def _apply_pending_journey_replay(self):
        from .journey_replay import materialize_route_snapshot
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
                self._dialog_parent(),
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
            self._status("Historical route could not be fully rematched",4500); return
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
        self.playTracksRequested.emit(tracks)
        self._status(f"{label} · {len(tracks)} tracks",5000)
    
    
    def _build_music_map_payload(self):
        from .music_knowledge import build_knowledge_graph
        from .music_map_model import build_music_map
        from .rediscovery_signals import build_rediscovery_signals
        from .taste_model import build_local_taste_model, score_taste_match
        from .user_state import UserState
    
        catalog=self.providers.local_catalog()
        profiles, _seed_refs, ref_map, _analysed = self.local_intelligence.build_snapshot(
            catalog,
            [],
            max_tracks=5000,
            analyse_seeds=False,
        )
        history_signals = {
            str(row.get("track_key") or ""): dict(row)
            for row in self.state.track_signals(5000)
            if isinstance(row, dict) and str(row.get("track_key") or "")
        }
        library_signals = build_rediscovery_signals(
            list(ref_map.values()),
            history_signals,
        )
        taste_model = build_local_taste_model(self.state)
        for profile in profiles:
            track = ref_map.get(str(profile.get("ref") or ""))
            if not isinstance(track, dict):
                continue
            adjustment, reason = score_taste_match(track, taste_model)
            profile["taste_model_adjustment"] = adjustment
            profile["taste_model_reason"] = reason
            signal = library_signals.get(UserState.track_key(track))
            if signal:
                profile["library_rediscovery"] = dict(signal)
        model=build_music_map(profiles,max_nodes=700,neighbours=2)
        mapped_refs={
            str(node.get("ref") or "")
            for node in list(model.get("nodes") or [])
            if isinstance(node,dict) and str(node.get("ref") or "")
        }
        mapped_nodes = {
            str(node.get("ref") or ""): dict(node)
            for node in list(model.get("nodes") or [])
            if isinstance(node, dict) and str(node.get("ref") or "")
        }
        mapped_ref_map={
            ref:dict(track)
            for ref,track in ref_map.items()
            if ref in mapped_refs
        }
        for ref, track in mapped_ref_map.items():
            taste_reason = str(mapped_nodes.get(ref, {}).get("taste_reason") or "").strip()
            if taste_reason:
                track["_taste_model_reason"] = taste_reason
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
            self._status("Add local music to build a Music Map",4000)
            return
        self._status("Building Music Map from cached Flow analysis…")
        self._run_async(self._build_music_map_payload,self._apply_music_map_payload, priority="visible", task_name="music-map-model", replace_key="page:music-map-model")

    def _music_map_artwork_requested(self, requests: object) -> None:
        rows = [dict(row) for row in list(requests or []) if isinstance(row, dict)]
        if not rows:
            return
        prefetch = all(bool(row.get("prefetch")) for row in rows)

        def load():
            metadata = self._metadata_getter()
            result = {}
            for row in rows:
                ref = str(row.get("ref") or "")
                track = dict(row.get("track") or {})
                if not ref or not track:
                    continue
                path = str(metadata.local_artwork(track).get("path") or "")
                result[ref] = metadata.prepared_artwork_payload(
                    path,
                    int(row.get("generation") or 0),
                    128,
                )
                result[ref]["prefetch"] = bool(row.get("prefetch"))
            return result

        self._run_async(
            load,
            self.music_map.set_artwork,
            priority="prefetch" if prefetch else "visible",
            task_name="music-map-cover-prefetch" if prefetch else "music-map-visible-covers",
        )
    
    
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
        self._music_map_selection_changed(self._music_map_selected())
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
            self._status(f"Music Map ready · {mapped} analysed tracks",5000)
        else:
            self._status("Music Map needs cached Flow analysis · choose Analyse my library",6000)
        if self.pending_journey_recipe is not None:
            self._apply_pending_journey_recipe()
        if self.pending_journey_replay is not None:
            self._apply_pending_journey_replay()
    
    
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
            self._status("Select a mapped track first",3000)
            return
        self._status(
            "Enriching selected track via MusicBrainz and enabled context plugins…"
        )
        self._run_async(
            lambda:self._knowledge_bundle_for_track(track),
            self._knowledge_enrichment_finished,
        priority="background", task_name="knowledge-enrich-selected")
    
    
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
            self._status("Mapped knowledge is already populated for these tracks",4000)
            return
        self._status(
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
        self._run_async(work,self._knowledge_batch_finished, priority="background", task_name="knowledge-enrich-batch")
    
    
    def _knowledge_enrichment_finished(self,result):
        errors=[str(x) for x in list((result or {}).get("errors") or []) if x]
        self._status(
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
        self._status(
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
        if hasattr(self,"music_journey_start_endpoint"):
            name=self._music_path_name(self.music_path_start_ref)
            self.music_journey_start_endpoint.set_track_label("" if name=="—" else name)
        if hasattr(self,"music_journey_end_endpoint"):
            name=self._music_path_name(self.music_path_end_ref)
            self.music_journey_end_endpoint.set_track_label("" if name=="—" else name)


    def _music_path_set_endpoint(self, endpoint: str, stage_or_ref: object):
        ref=(
            str(stage_or_ref.get("ref") or "")
            if isinstance(stage_or_ref,dict)
            else str(stage_or_ref or "")
        )
        if not ref or ref not in getattr(self.music_map,"ref_map",{}):
            self._status("Choose a track that is on the current Music Map",3500)
            return False
        if str(endpoint or "").casefold()=="start":
            self.music_path_start_ref=ref
            message="Journey start set"
        elif str(endpoint or "").casefold() in {"end","destination"}:
            self.music_path_end_ref=ref
            message="Journey destination set"
        else:
            return False
        self.music_path_result={}
        self.music_map.set_route_endpoints(
            self.music_path_start_ref,
            self.music_path_end_ref,
        )
        self._music_path_update_label()
        self._status(message,2500)
        return True
    
    
    def _music_path_set_start(self):
        ref=self.music_map.selected_ref_value() if hasattr(self,"music_map") else ""
        if not ref:
            self._status("Select a Music Map track first",3000); return
        self._music_path_set_endpoint("start",ref)
    
    
    def _music_path_set_end(self):
        ref=self.music_map.selected_ref_value() if hasattr(self,"music_map") else ""
        if not ref:
            self._status("Select a Music Map track first",3000); return
        self._music_path_set_endpoint("destination",ref)
    
    
    def _music_path_find(self):
        from .music_pathfinder import find_music_path
        if not self.music_path_start_ref or not self.music_path_end_ref:
            self._status("Set both Pathfinder start and destination",3500); return
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
            self._status(reason,6000)
            return
    
        refs=[str(x) for x in list(self.music_path_result.get("path_refs") or []) if str(x)]
        hops=[dict(x) for x in list(self.music_path_result.get("hops") or []) if isinstance(x,dict)]
        for index,hop in enumerate(hops):
            a=self._music_path_name(hop.get("from") or (refs[index] if index<len(refs) else ""))
            b=self._music_path_name(hop.get("to") or (refs[index+1] if index+1<len(refs) else ""))
            reason=str(hop.get("reason") or "graph connection")
            self.music_path_steps.addItem(f"{index+1}. {a}  →  {b}\n{reason}")
        self._status(
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
            self._status("Find a Pathfinder route first",3000); return
        self.playTracksRequested.emit(tracks)
        self._status(f"Playing Pathfinder route · {len(tracks)} tracks",4000)
    
    
    def _music_path_queue(self):
        tracks=self._music_path_tracks()
        if not tracks:
            self._status("Find a Pathfinder route first",3000); return
        self.queueTracksRequested.emit(tracks)
        self._status(f"Queued Pathfinder route · {len(tracks)} tracks",4000)
    
    
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
        self._status("Pathfinder cleared",2500)
    
    
    def _journey_recipe_mark_modified(self):
        if self.music_active_recipe_id:
            self.music_active_recipe_id=""
            self.music_active_recipe={}
    
    # ------------------------------- Music Map Journey Designer
    
    def _music_journey_render_stages(self):
        from .music_journey import STAGE_LABELS
        if not hasattr(self,"music_journey_stages"):return
        if not self.music_journey_stages_data:
            self.music_journey_stages.set_stages([])
            return
        for stage in self.music_journey_stages_data:
            if str(stage.get("type") or "")=="track":
                label=str(stage.get("label") or self._music_path_name(stage.get("ref") or ""))
                stage["label"]=label
            else:
                key=str(stage.get("constraint") or "")
                stage["label"]=str(stage.get("label") or STAGE_LABELS.get(key,key.title()))
        self.music_journey_stages.set_stages(self.music_journey_stages_data)


    def _music_journey_stage_order_changed(self, stages):
        ordered=[dict(stage) for stage in list(stages or []) if isinstance(stage,dict)]
        if ordered==self.music_journey_stages_data:return
        self.music_journey_stages_data=ordered
        self.music_active_recipe_id=""
        self.music_active_recipe={}


    def _music_journey_move_stage(self, offset: int):
        if not hasattr(self,"music_journey_stages"):return
        if self.music_journey_stages.move_current(offset):
            self._music_journey_stage_order_changed(
                self.music_journey_stages.ordered_stages()
            )
    
    
    def _music_journey_load_preset(self, stage_keys: list[str] | None = None):
        from .music_journey import STAGE_LABELS
        self.music_active_recipe_id=""
        self.music_active_recipe={}
        raw=list(stage_keys or [])
        self.music_journey_stages_data=[
            {"type":"constraint","constraint":str(key),"label":STAGE_LABELS.get(str(key),str(key).title())}
            for key in list(raw or [])
        ]
        self._music_journey_render_stages()
        self._status("Journey preset loaded",2500)
    
    
    def _music_journey_add_constraint(self, key: str = ""):
        from .music_journey import STAGE_LABELS
        self.music_active_recipe_id=""
        self.music_active_recipe={}
        key=str(key or "")
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
            self._status("Select a mapped track first",3000); return
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
        self._status("Journey stages cleared",2500)
    
    
    def _music_journey_build(self):
        from .music_journey import build_music_journey
        if self.music_live_active:
            self._journey_live_stop("design changed")
        if not self.music_path_start_ref or not self.music_path_end_ref:
            self._status(
                "Set Pathfinder start and destination before building a journey",4000
            ); return
        mode=str(self.music_path_mode.currentData() or "balanced")
        self._status("Designing local journey…")
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
            self._status(reason,7000)
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
        self._status(
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
        from .journey_recipe import make_journey_recipe
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
        from .journey_replay import portable_route_snapshot
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
        from .journey_replay import portable_route_snapshot
        route=dict(self.music_path_result or {})
        if not route.get("found") or not route.get("journey"):
            self._status(
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
            self._status(
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
        self.playTracksRequested.emit(tracks)
        self.music_map.show_route(route)
        self._journey_live_update_label()
        self._refresh_journeys()
        self._status(
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
        steering=str(self.music_live_steering.currentData() or "") if hasattr(self,"music_live_steering") else ""
        if not steering:
            self._status("Choose a Journey Live steering direction first",3000); return
        self.request_live_steer(steering)

    def request_live_steer(self, steering: str) -> None:
        from .music_journey_live import STEERING_STAGES

        steering = str(steering or "").strip().lower()
        if not self.music_live_active:
            self._status("Start Journey Live first", 3000)
            return
        if steering not in STEERING_STAGES:
            self._status("Choose a valid direction for the live journey", 3000)
            return
        label = STEERING_STAGES[steering][1]
        self._journey_live_event(
            "steer",
            {
                "steering":steering,
                "label":label,
            },
        )
        self._journey_live_replan(steering,reason=f"steer:{steering}")

    def request_more_like(self, track: object, queue_index: int = -1) -> None:
        if not self.music_live_active:
            self._status("Start Journey Live before steering the queue", 3500)
            return
        row = dict(track) if isinstance(track, dict) else {}
        target_ref = self._music_ref_for_track(row)
        if not target_ref:
            self._status(
                "That track is not available on the active Music Map", 4000
            )
            return
        if int(queue_index) >= 0:
            self.protectQueueTrackRequested.emit(int(queue_index))
        label = self._music_path_name(target_ref)
        self._journey_live_event(
            "steer",
            {
                "steering": "more_like_this",
                "label": f"More like {label}",
                "target": label,
            },
        )
        self._journey_live_replan(
            "",
            similar_to_ref=target_ref,
            reason=f"more_like:{target_ref}",
        )

    def request_toward_artist(self, track: object) -> None:
        if not self.music_live_active:
            self._status("Start Journey Live before steering the queue", 3500)
            return
        row = dict(track) if isinstance(track, dict) else {}
        artist = " ".join(str(row.get("artist") or "").strip().split())
        if not artist:
            self._status("That track has no artist to steer toward", 3500)
            return
        music_model = dict(self.music_map.model or {})
        mapped_artists = {
            " ".join(str(node.get("artist") or "").strip().casefold().split())
            for node in list(music_model.get("nodes") or [])
            if isinstance(node, dict)
        }
        if artist.casefold() not in mapped_artists:
            self._status(
                f"{artist} is not represented on the active Music Map", 4000
            )
            return
        self._journey_live_event(
            "steer",
            {
                "steering": "toward_artist",
                "artist": artist,
                "label": f"Toward {artist}",
            },
        )
        self._journey_live_replan(
            "",
            target_artist=artist,
            reason=f"toward_artist:{artist}",
        )

    def request_toward_region(self, track: object) -> None:
        if not self.music_live_active:
            self._status("Start Journey Live before steering the queue", 3500)
            return
        row = dict(track) if isinstance(track, dict) else {}
        target_ref = self._music_ref_for_track(row)
        if not target_ref:
            self._status(
                "That track is not available on the active Music Map", 4000
            )
            return
        label = self._music_path_name(target_ref)
        self._journey_live_event(
            "steer",
            {
                "steering": "toward_map_region",
                "label": f"Toward this map area · {label}",
                "target": label,
            },
        )
        self._journey_live_replan(
            "",
            target_region_ref=target_ref,
            reason=f"toward_region:{target_ref}",
        )
    
    
    def _journey_live_avoid_current_artist(self):
        if not self.music_live_active or not self.current_track:
            self._status("Start Journey Live and play a mapped track first",3500); return
        artist=str(self.current_track.get("artist") or "").strip()
        if not artist:
            self._status("The current track has no artist metadata to avoid",3500); return
        self.music_live_avoid_artists.add(artist)
        self._journey_live_event("avoid_artist",{"artist":artist})
        self._status(f"Journey Live will avoid {artist} in the remaining route",4500)
        self._journey_live_replan("",reason="avoid artist")
    
    
    def _journey_live_restore(self):
        if not self.music_live_active:
            self._status("Start Journey Live first",3000); return
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
        similar_to_ref="",
        target_artist="",
        target_region_ref="",
        reason="",
    ):
        from .music_journey_live import replan_live_journey
        if not self.music_live_active:
            self._status("Start Journey Live first",3000); return
        if self.music_live_replanning:
            self._status("Journey Live is already replanning…",2500); return
        current_ref=self._music_ref_for_track(self.current_track or {})
        if not current_ref:
            self._status(
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
        similar_ref=str(similar_to_ref or "")
        artist_target=" ".join(str(target_artist or "").strip().split())
        region_target=str(target_region_ref or "")
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
                similar_to_ref=similar_ref,
                target_artist=artist_target,
                target_region_ref=region_target,
                max_hops_per_segment=8,
            )
            result=dict(result or {})
            result["_live_from_ref"]=current_ref
            result["_live_request_reason"]=request_reason
            result["_live_similar_to_ref"]=similar_ref
            result["_live_target_artist"]=artist_target
            result["_live_target_region_ref"]=region_target
            result["_live_steering"]=str(steering or "")
            return result
        self._run_async(work,self._journey_live_apply_result, priority="foreground", task_name="journey-live-replan", replace_key="journey-live-replan")
    
    
    def _journey_live_apply_result(self,result):
        self.music_live_replanning=False
        if not self.music_live_active:
            return
        result=dict(result or {})
        expected=str(result.get("_live_from_ref") or "")
        current_ref=self._music_ref_for_track(self.current_track or {})
        if expected and current_ref and current_ref!=expected:
            self._status(
                "Journey Live moved while replanning · recalculating from the current track",4500
            )
            steering = str(result.get("_live_steering") or "")
            similar_ref = str(result.get("_live_similar_to_ref") or "")
            artist_target = str(result.get("_live_target_artist") or "")
            region_target = str(result.get("_live_target_region_ref") or "")
            QTimer.singleShot(
                0,
                lambda: self._journey_live_replan(
                    steering,
                    similar_to_ref=similar_ref,
                    target_artist=artist_target,
                    target_region_ref=region_target,
                ),
            )
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
            self._status(
                reason+" · existing queue kept unchanged",7000
            )
            return
    
        refs=[str(x) for x in list(result.get("path_refs") or []) if str(x)]
        if not refs or refs[0]!=current_ref:
            self._journey_live_update_label("invalid replan · queue unchanged")
            self._status(
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
            self._status(
                "A replanned track is no longer on the Music Map · existing queue kept unchanged",6500
            )
            return
    
        self.replaceUpcomingRequested.emit(tail)
        from .music_journey_live import route_track_reasons

        self.queueTrackReasonsRequested.emit(
            route_track_reasons(result, self.music_map.ref_map)
        )
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
        self._status(
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
        self._status("Journey Live adapting after manual skip…",3500)
        self._journey_live_replan(
            "",
            reopen_stage_refs=reopen,
            reason="manual skip",
        )
    
    
    def _analyse_library_for_map(self):
        catalog=self.providers.local_catalog()
        if not catalog:
            QMessageBox.information(self._dialog_parent(),"Add music first","Add a local music folder before analysing your library.")
            return
        if not self.flow.analysis_available:
            QMessageBox.information(
                self._dialog_parent(),
                "Audio analysis unavailable",
                "Music Map analysis needs ffmpeg and NumPy. Install/enable them, then try again."
            )
            return
        self._status("Analysing local library for Music Map…")
        self._run_async(
            lambda:self.local_intelligence.analyse_catalog(catalog),
            self._music_map_analysis_finished,
        priority="background", task_name="music-map-analysis")
    
    
    def _music_map_analysis_finished(self,result):
        self._status(
            f"Library analysis ready · {int(result.get('analysed') or 0)}/{int(result.get('total') or 0)} analysed",
            5000,
        )
        self._refresh_music_map()
    
    
    def _music_map_selected(self):
        return self.music_map.selected_track() if hasattr(self,"music_map") else {}
    
    
    def _play_music_map_track(self,track):
        if isinstance(track,dict) and track:
            self.playTracksRequested.emit([dict(track)])
    
    
    def _play_music_map_selected(self):
        track=self._music_map_selected()
        if track:self._play_music_map_track(track)
    
    
    def _queue_music_map_selected(self):
        track=self._music_map_selected()
        if not track:return
        self.queueTracksRequested.emit([track])
        self._status("Added Music Map track to queue",3000)
    
    
    def _journey_from_music_map(self):
        track=self._music_map_selected()
        if not track:
            self._status("Select a Music Map track first",3000)
            return
        self.sessionFromTrackRequested.emit(dict(track))
