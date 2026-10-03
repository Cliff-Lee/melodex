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
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .ux_components import EmptyState, set_help


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
        self.journeys_page = QWidget()
        self.pages = {
            "music_map": self.music_map_page,
            "journeys": self.journeys_page,
        }
        self.music_map_built = False

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

        self._build_journeys()

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

    def refresh_music_map(self) -> None:
        if self.music_map_built:
            self._refresh_music_map()

    def refresh_journeys(self) -> None:
        self._refresh_journeys()

    def open_designer(self) -> None:
        self._open_journey_designer()

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
    
        top=QHBoxLayout()
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
        skip_replan.clicked.connect(lambda: self.nextTrackRequested.emit())
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
    
        self.music_map=MusicMapWidget(self.music_map_page)
        self.music_map.trackSelected.connect(self._music_map_selection_changed)
        self.music_map.trackActivated.connect(self._play_music_map_track)
        l.addWidget(self.music_map,1)
    
        self.music_path_steps=QListWidget()
        self.music_path_steps.setMaximumHeight(116)
        self.music_path_steps.addItem("Route explanations will appear here after you plan one.")
        self.music_path_steps.hide()
        l.addWidget(self.music_path_steps)
    
    
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
            self._status(
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
            "Build a listening route that changes gradually as it plays.",
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
            "Routes you want to use again."
        )
        saved_help.setWordWrap(True)
        saved_help.setObjectName("mutedText")
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
            "What actually played, including any changes you made on the way."
        )
        runs_help.setWordWrap(True)
        runs_help.setObjectName("mutedText")
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
        self.navigationRequested.emit("music_map")
        self.music_map_power_panel.show()
        self.music_map_journey_panel.show()
        self.music_path_steps.show()
        self._status(
            "Journey design ready · select a track for the start, another for the destination, then shape the route",
            6000,
        )
    
    
    
    def _refresh_journeys(self):
        from .journey_replay import summarize_journey_run
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
        from .journey_recipe import make_journey_recipe, save_journey_recipe
        if not self.music_journey_stages_data:
            self._status(
                "Add Journey Designer stages before saving a recipe",3500
            ); return
        default_name=str(self.music_active_recipe.get("name") or "Journey recipe")
        name,ok=QInputDialog.getText(
                self._dialog_parent(),
            "Save journey recipe",
            "Recipe name:",
            text=default_name,
        )
        if not ok or not str(name).strip():
            return
        description,ok=QInputDialog.getText(
                self._dialog_parent(),
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
            QMessageBox.warning(self._dialog_parent(),"Could not save journey recipe",str(exc)); return
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
        self._status(
            f"Saved journey recipe · {recipe.get('name')}",4000
        )
    
    
    def _journey_recipe_load_selected(self):
        record=self._selected_journey_recipe_record()
        if not record:
            self._status("Select a journey recipe first",3000); return
        recipe=dict(record.get("payload") or {})
        self.pending_journey_recipe={
            "id":str(record.get("id") or ""),
            "payload":recipe,
        }
        self.navigationRequested.emit("music_map")
        self._status("Refreshing Music Map before loading recipe…",3500)
    
    
    def _journey_recipe_import(self):
        from .journey_recipe import load_journey_recipe, save_journey_recipe
        filename,_=QFileDialog.getOpenFileName(
                self._dialog_parent(),
            "Import journey recipe",
            filter="Melodex Journey (*.mdxjourney);;JSON files (*.json)",
        )
        if not filename:
            return
        try:
            recipe=load_journey_recipe(Path(filename))
        except Exception as exc:
            QMessageBox.warning(self._dialog_parent(),"Could not import journey recipe",str(exc)); return
        recipe_id=str(uuid.uuid4())
        self.state.save_journey_recipe(
            recipe_id,
            str(recipe.get("name") or Path(filename).stem),
            str(recipe.get("description") or ""),
            recipe,
        )
        self._refresh_journeys()
        self._status(
            f"Imported journey recipe · {recipe.get('name')}",4500
        )
    
    
    def _journey_recipe_export(self):
        from .journey_recipe import save_journey_recipe
        record=self._selected_journey_recipe_record()
        if not record:
            self._status("Select a journey recipe first",3000); return
        recipe=dict(record.get("payload") or {})
        default_name="".join(
            ch if ch.isalnum() or ch in {" ","-","_"} else "_"
            for ch in str(record.get("name") or "journey")
        ).strip() or "journey"
        filename,_=QFileDialog.getSaveFileName(
                self._dialog_parent(),
            "Export journey recipe",
            default_name+".mdxjourney",
            "Melodex Journey (*.mdxjourney)",
        )
        if not filename:
            return
        try:
            path=save_journey_recipe(Path(filename),recipe)
        except Exception as exc:
            QMessageBox.warning(self._dialog_parent(),"Could not export journey recipe",str(exc)); return
        self._status(f"Exported {path.name}",4500)
    
    
    def _journey_recipe_delete(self):
        record=self._selected_journey_recipe_record()
        if not record:
            self._status("Select a journey recipe first",3000); return
        answer=QMessageBox.question(
                self._dialog_parent(),
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
        self._status("Journey recipe deleted",3000)
    
    
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
    
    
    def _journey_run_inspect(self):
        from .journey_replay import summarize_journey_run
        run=self._selected_journey_run_record()
        if not run:
            self._status("Select a journey run first",3000); return
        events=self.state.journey_events(str(run.get("id") or ""))
        summary=summarize_journey_run(run,events)
        d=QDialog(self._dialog_parent())
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
            self._status("Select a journey run first",3000); return
        which=str(which or "final")
        snapshot=dict(
            run.get("original_route")
            if which=="original"
            else run.get("final_route")
            or {}
        )
        if not snapshot or not list(snapshot.get("tracks") or []):
            self._status(
                f"This run has no {which} route snapshot to replay",4000
            ); return
        self.pending_journey_replay=(snapshot,f"{which.title()} journey replay")
        self.navigationRequested.emit("music_map")
        self._status(
            f"Refreshing Music Map before {which} replay…",3500
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
            self._status("Add local music to build a Music Map",4000)
            return
        self._status("Building Music Map from cached Flow analysis…")
        self._run_async(self._build_music_map_payload,self._apply_music_map_payload, priority="visible", task_name="music-map-model", replace_key="page:music-map-model")
    
    
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
    
    
    def _music_path_set_start(self):
        ref=self.music_map.selected_ref_value() if hasattr(self,"music_map") else ""
        if not ref:
            self._status("Select a Music Map track first",3000); return
        self.music_path_start_ref=ref
        self.music_path_result={}
        self.music_map.set_route_endpoints(self.music_path_start_ref,self.music_path_end_ref)
        self._music_path_update_label()
        self._status("Pathfinder start set",2500)
    
    
    def _music_path_set_end(self):
        ref=self.music_map.selected_ref_value() if hasattr(self,"music_map") else ""
        if not ref:
            self._status("Select a Music Map track first",3000); return
        self.music_path_end_ref=ref
        self.music_path_result={}
        self.music_map.set_route_endpoints(self.music_path_start_ref,self.music_path_end_ref)
        self._music_path_update_label()
        self._status("Pathfinder destination set",2500)
    
    
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
        from .music_journey import STAGE_LABELS
        self.music_active_recipe_id=""
        self.music_active_recipe={}
        raw=self.music_journey_preset.currentData() if hasattr(self,"music_journey_preset") else []
        self.music_journey_stages_data=[
            {"type":"constraint","constraint":str(key),"label":STAGE_LABELS.get(str(key),str(key).title())}
            for key in list(raw or [])
        ]
        self._music_journey_render_stages()
        self._status("Journey preset loaded",2500)
    
    
    def _music_journey_add_constraint(self):
        from .music_journey import STAGE_LABELS
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
        if not self.music_journey_stages_data:
            self._status(
                "Load a Journey preset or add at least one stage",3500
            ); return
        mode=str(self.music_path_mode.currentData() or "balanced")
        self._status("Designing staged local journey…")
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

