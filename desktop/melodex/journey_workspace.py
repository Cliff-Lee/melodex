Warning: truncated output (original token count: 18527)
Total output lines: 1766

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Qt, QTimer, Signal
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
    nextTrackRequested = Signal()
    sessionFromTrackRequested = Signal(object)
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
    
        l=self._page_layout(
            "music_map",
            "Music Map",
            "Explore your music as a landscape. Pan and zoom freely; select a track to reveal its closest relationships. Routes and technical tools stay out of the way until requested.",
        )
    
        simple=QHBoxLayout()
        self.music_map_options_button=QPushButton("Map options…")
        self.music_map_options_button.setObjectName("quietButton")
        self.music_map_options_button.clicked.connect(self._toggle_music_map_options)
        self.music_map_play_button=QPushButton("▶ Play selected")
        self.music_map_play_button.clicked.connect(self._play_music_map_selected)
        self.music_map_play_button.setEnabled(False)
        self.music_map_queue_button=QPushButton("+ Queue selected")
        self.music_map_queue_button.clicked.connect(self._queue_music_map_selected)
        self.music_map_queue_button.setEnabled(False)
        self.music_map_plan_button=QPushButton("Plan a route…")
        self.music_map_plan_button.setObjectName("secondaryButton")
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
        close_tools=QPushButton("Hide route tools")
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
        live_tab_layout=QVBoxLayout(self.m…6527 tokens truncated…  if ordered==self.music_journey_stages_data:return
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
        if not self.music_live_active:
            self._status("Start Journey Live first",3000); return
        steering=str(self.music_live_steering.currentData() or "") if hasattr(self,"music_live_steering") else ""
        if not steering:
            self._status("Choose a Journey Live steering direction first",3000); return
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
