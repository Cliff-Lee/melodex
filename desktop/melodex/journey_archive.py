from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
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


class JourneyArchive(QObject):
    """Saved Journey recipes and private run history UI/persistence."""

    designRequested = Signal()
    recipeLoadRequested = Signal(object)
    replayRequested = Signal(object, str)
    recipeActivated = Signal(str, object)
    recipeDeleted = Signal(str)
    statusMessageRequested = Signal(str, int)

    def __init__(
        self,
        user_state: Any,
        *,
        current_design: Callable[[], dict[str, Any]],
        page_titles: dict[str, QLabel],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.state = user_state
        self._current_design = current_design
        self.page_titles = page_titles
        self.page = QWidget()
        self._build_page()

    def _status(self, message: str, timeout_ms: int = 0) -> None:
        self.statusMessageRequested.emit(str(message), int(timeout_ms))

    def _request_design(self) -> None:
        self.designRequested.emit()

    def _page_layout(self, title: str, subtitle: str = ""):
        layout = QVBoxLayout(self.page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        layout.addWidget(title_label)
        self.page_titles["journeys"] = title_label
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setWordWrap(True)
            subtitle_label.setObjectName("pageSubtitle")
            layout.addWidget(subtitle_label)
        return layout

    def _build_page(self):
        l=self._page_layout(
            "Journeys",
            "Build a listening route that changes gradually as it plays.",
        )
    
        top=QHBoxLayout()
        design=QPushButton("Design a journey")
        design.setObjectName("primaryButton")
        design.clicked.connect(self._request_design)
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
        self.journey_recipes_empty.actionRequested.connect(self._request_design)
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
    
    
    
    def refresh(self):
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
        from .journey_recipe import make_journey_recipe

        design = dict(self._current_design() or {})
        stages = [
            dict(stage)
            for stage in list(design.get("stages") or [])
            if isinstance(stage, dict)
        ]
        if not stages:
            self._status("Add Journey Designer stages before saving a recipe", 3500)
            return

        active_recipe = dict(design.get("active_recipe") or {})
        default_name = str(active_recipe.get("name") or "Journey recipe")
        name, ok = QInputDialog.getText(
            self.page,
            "Save journey recipe",
            "Recipe name:",
            text=default_name,
        )
        if not ok or not str(name).strip():
            return

        description, ok = QInputDialog.getText(
            self.page,
            "Save journey recipe",
            "Short description (optional):",
            text=str(active_recipe.get("description") or ""),
        )
        if not ok:
            return

        try:
            recipe = make_journey_recipe(
                name=str(name),
                description=str(description),
                mode=str(design.get("mode") or "balanced"),
                stages=stages,
                ref_map=dict(design.get("ref_map") or {}),
            )
        except Exception as exc:
            QMessageBox.warning(self.page, "Could not save journey recipe", str(exc))
            return

        recipe_id = str(uuid.uuid4())
        self.state.save_journey_recipe(
            recipe_id,
            str(recipe.get("name") or name),
            str(recipe.get("description") or ""),
            recipe,
        )
        self.recipeActivated.emit(recipe_id, dict(recipe))
        self.refresh()
        self._status(f"Saved journey recipe · {recipe.get('name')}", 4000)
    def _journey_recipe_load_selected(self):
        record = self._selected_journey_recipe_record()
        if not record:
            self._status("Select a journey recipe first", 3000)
            return
        self.recipeLoadRequested.emit(
            {
                "id": str(record.get("id") or ""),
                "payload": dict(record.get("payload") or {}),
            }
        )
    def _journey_recipe_import(self):
        from .journey_recipe import load_journey_recipe, save_journey_recipe
        filename,_=QFileDialog.getOpenFileName(
                self.page,
            "Import journey recipe",
            filter="Melodex Journey (*.mdxjourney);;JSON files (*.json)",
        )
        if not filename:
            return
        try:
            recipe=load_journey_recipe(Path(filename))
        except Exception as exc:
            QMessageBox.warning(self.page,"Could not import journey recipe",str(exc)); return
        recipe_id=str(uuid.uuid4())
        self.state.save_journey_recipe(
            recipe_id,
            str(recipe.get("name") or Path(filename).stem),
            str(recipe.get("description") or ""),
            recipe,
        )
        self.refresh()
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
                self.page,
            "Export journey recipe",
            default_name+".mdxjourney",
            "Melodex Journey (*.mdxjourney)",
        )
        if not filename:
            return
        try:
            path=save_journey_recipe(Path(filename),recipe)
        except Exception as exc:
            QMessageBox.warning(self.page,"Could not export journey recipe",str(exc)); return
        self._status(f"Exported {path.name}",4500)
    
    
    
    def _journey_recipe_delete(self):
        record=self._selected_journey_recipe_record()
        if not record:
            self._status("Select a journey recipe first",3000); return
        answer=QMessageBox.question(
                self.page,
            "Delete journey recipe",
            f"Delete {record.get('name') or 'this recipe'}?\n\nRun history is kept.",
            QMessageBox.Yes|QMessageBox.No,
            QMessageBox.No,
        )
        if answer!=QMessageBox.Yes:
            return
        recipe_id=str(record.get("id") or "")
        self.state.delete_journey_recipe(recipe_id)
        self.recipeDeleted.emit(recipe_id)
        self.refresh()
        self._status("Journey recipe deleted",3000)
    
    
    
    def _journey_run_inspect(self):
        from .journey_replay import summarize_journey_run
        run=self._selected_journey_run_record()
        if not run:
            self._status("Select a journey run first",3000); return
        events=self.state.journey_events(str(run.get("id") or ""))
        summary=summarize_journey_run(run,events)
        d=QDialog(self.page)
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
    
    
    
    def _journey_run_replay(self, which):
        run = self._selected_journey_run_record()
        if not run:
            self._status("Select a journey run first", 3000)
            return

        which = str(which or "final")
        snapshot = dict(
            run.get("original_route")
            if which == "original"
            else run.get("final_route") or {}
        )
        if not snapshot or not list(snapshot.get("tracks") or []):
            self._status(
                f"This run has no {which} route snapshot to replay",
                4000,
            )
            return
        self.replayRequested.emit(
            snapshot,
            f"{which.title()} journey replay",
        )
