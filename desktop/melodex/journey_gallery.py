from __future__ import annotations

import threading
from typing import Any, Callable

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from .journey_registry import JourneyRegistryClient, recipe_sha256


class _Signals(QObject):
    done = Signal(object)
    error = Signal(str)


class JourneyGalleryDialog(QDialog):
    def __init__(
        self,
        state,
        data_dir,
        on_added: Callable[[], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.state = state
        self.client = JourneyRegistryClient(data_dir)
        self.on_added = on_added
        self.recipes: list[dict[str, Any]] = []
        self._signals: list[_Signals] = []

        self.setWindowTitle("Melodex Journey Recipe Gallery")
        self.resize(940, 660)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Browse reusable Journey Recipes. Recipes are validated data, not executable "
            "plugins: Melodex verifies the recipe schema and SHA-256 before adding one "
            "to your local Journey Library."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search recipes, authors, descriptions or tags…")
        self.tag = QComboBox()
        self.tag.addItem("All tags", "all")
        self.refresh_button = QPushButton("Refresh")
        filters.addWidget(self.search, 1)
        filters.addWidget(self.tag)
        filters.addWidget(self.refresh_button)
        layout.addLayout(filters)

        self.status = QLabel("Loading Journey Recipe registry…")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#aab0ba")
        layout.addWidget(self.status)

        body = QHBoxLayout()
        self.rows = QListWidget()
        self.rows.setMinimumWidth(400)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        body.addWidget(self.rows, 1)
        body.addWidget(self.details, 1)
        layout.addLayout(body, 1)

        actions = QHBoxLayout()
        self.add_button = QPushButton("Add to Library")
        self.source_button = QPushButton("View source")
        close_button = QPushButton("Close")
        self.add_button.setEnabled(False)
        self.source_button.setEnabled(False)
        actions.addWidget(self.add_button)
        actions.addWidget(self.source_button)
        actions.addStretch(1)
        actions.addWidget(close_button)
        layout.addLayout(actions)

        self.rows.currentItemChanged.connect(lambda *_: self._show_details())
        self.search.textChanged.connect(lambda *_: self._apply_filter())
        self.tag.currentIndexChanged.connect(lambda *_: self._apply_filter())
        self.refresh_button.clicked.connect(lambda: self.load_registry(force=True))
        self.add_button.clicked.connect(self._add_selected)
        self.source_button.clicked.connect(self._open_source)
        close_button.clicked.connect(self.accept)

        self.load_registry(force=False)

    def _run_async(self, fn, done) -> None:
        signals = _Signals(self)
        self._signals.append(signals)

        def finish(value):
            try:
                done(value)
            finally:
                if signals in self._signals:
                    self._signals.remove(signals)

        def failed(message):
            self.status.setText(str(message))
            self.add_button.setEnabled(False)
            if signals in self._signals:
                self._signals.remove(signals)

        signals.done.connect(finish)
        signals.error.connect(failed)

        def work():
            try:
                signals.done.emit(fn())
            except Exception as exc:
                signals.error.emit(str(exc))

        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _library_id(entry: dict[str, Any]) -> str:
        return "gallery:" + str(entry.get("id") or "").strip()

    def _local_state(self, entry: dict[str, Any]) -> str:
        recipe_id = self._library_id(entry)
        record = self.state.get_journey_recipe(recipe_id)
        if not record:
            return ""
        payload = dict(record.get("payload") or {})
        try:
            local_hash = recipe_sha256(payload)
        except Exception:
            return "UPDATE"
        return "ADDED" if local_hash == str(entry.get("sha256") or "") else "UPDATE"

    def _selected(self) -> dict[str, Any]:
        item = self.rows.currentItem()
        value = item.data(Qt.UserRole) if item else None
        return dict(value or {}) if isinstance(value, dict) else {}

    def load_registry(self, force: bool = False) -> None:
        self.status.setText("Refreshing Journey Recipe registry…" if force else "Loading Journey Recipe registry…")
        self.rows.clear()
        self.details.clear()
        self.add_button.setEnabled(False)
        self._run_async(
            lambda: self.client.fetch(force=force).as_dict(),
            self._registry_loaded,
        )

    def _registry_loaded(self, result: Any) -> None:
        result = dict(result or {})
        self.recipes = [
            dict(row)
            for row in list(result.get("recipes") or [])
            if isinstance(row, dict)
        ]
        tags = sorted(
            {
                str(tag)
                for row in self.recipes
                for tag in list(row.get("tags") or [])
                if str(tag)
            },
            key=str.casefold,
        )
        current = str(self.tag.currentData() or "all")
        self.tag.blockSignals(True)
        self.tag.clear()
        self.tag.addItem("All tags", "all")
        for value in tags:
            self.tag.addItem(value, value.casefold())
        index = self.tag.findData(current)
        self.tag.setCurrentIndex(index if index >= 0 else 0)
        self.tag.blockSignals(False)

        source = str(result.get("source") or "")
        if source == "bundled":
            self.status.setText(
                f"Using {len(self.recipes)} bundled starter Recipes"
                + (
                    " because the online registry could not be reached: "
                    + str(result.get("error") or "")
                    if result.get("error")
                    else "."
                )
            )
        elif result.get("stale"):
            self.status.setText(
                f"Using cached Journey Recipe registry · {len(self.recipes)} entries · "
                + str(result.get("error") or "")
            )
        else:
            origin = "cached registry" if source == "cache" else "Melodex Journey Recipe registry"
            self.status.setText(
                f"Loaded {len(self.recipes)} Recipes from {origin}. "
                "Recipe schema and SHA-256 are verified before adding."
            )
        self._apply_filter()

    def _apply_filter(self) -> None:
        rows = self.client.filter_recipes(
            self.recipes,
            self.search.text(),
            str(self.tag.currentData() or "all"),
        )
        self.rows.clear()
        for entry in rows:
            local = self._local_state(entry)
            badge = local or str(entry.get("status") or "").upper()
            tags = ", ".join(str(x) for x in list(entry.get("tags") or []))
            item = QListWidgetItem(
                f"{entry.get('name') or entry.get('id')}    ·    {badge}\n"
                f"{entry.get('author') or 'Unknown author'} · {tags}"
            )
            item.setData(Qt.UserRole, entry)
            self.rows.addItem(item)
        if self.rows.count():
            self.rows.setCurrentRow(0)
        else:
            self.details.setPlainText("No Journey Recipes match these filters.")
            self.add_button.setEnabled(False)
            self.source_button.setEnabled(False)

    def _show_details(self) -> None:
        entry = self._selected()
        if not entry:
            self.details.clear()
            self.add_button.setEnabled(False)
            self.source_button.setEnabled(False)
            return

        compatible, reason = self.client.compatible(entry)
        recipe = dict(entry.get("recipe") or {})
        stages = [
            dict(stage)
            for stage in list(recipe.get("stages") or [])
            if isinstance(stage, dict)
        ]
        stage_lines = []
        for index, stage in enumerate(stages, start=1):
            if str(stage.get("type") or "") == "track":
                selector = dict(stage.get("selector") or {})
                label = str(stage.get("label") or selector.get("title") or "Exact track")
                stage_lines.append(f"{index}. Exact track · {label}")
            else:
                stage_lines.append(
                    f"{index}. {stage.get('label') or stage.get('constraint') or 'Stage'}"
                )
        local = self._local_state(entry)
        source = dict(entry.get("source") or {})
        text = (
            f"{entry.get('name') or ''}\n"
            f"{entry.get('id') or ''}\n\n"
            f"{entry.get('description') or ''}\n\n"
            f"Author: {entry.get('author') or 'Not specified'}\n"
            f"Version: {entry.get('version') or '—'}\n"
            f"Status: {str(entry.get('status') or '').upper()}\n"
            f"License: {entry.get('license') or 'Not specified'}\n"
            f"Tags: {', '.join(str(x) for x in list(entry.get('tags') or [])) or '—'}\n"
            f"Routing mode: {recipe.get('routing_mode') or 'balanced'}\n"
            f"Compatible: {'Yes' if compatible else 'No'}"
            + (f" — {reason}" if reason else "")
            + f"\nLocal state: {local or 'Not added'}\n"
            f"SHA-256: {entry.get('sha256') or '—'}\n"
            f"Source: {source.get('repository') or '—'}\n\n"
            "Journey stages:\n"
            + ("\n".join(stage_lines) if stage_lines else "No stages")
            + "\n\n"
            "Recipes contain data only. Adding a Recipe does not execute third-party code."
        )
        self.details.setPlainText(text)
        self.add_button.setEnabled(bool(compatible and entry.get("status") != "blocked"))
        self.add_button.setText(
            "Update Library copy" if local == "UPDATE"
            else "Added" if local == "ADDED"
            else "Add to Library"
        )
        if local == "ADDED":
            self.add_button.setEnabled(False)
        self.source_button.setEnabled(bool(source.get("repository")))

    def _add_selected(self) -> None:
        entry = self._selected()
        if not entry:
            return
        if str(entry.get("status") or "") == "deprecated":
            if (
                QMessageBox.question(
                    self,
                    "Deprecated Journey Recipe",
                    "This Recipe is marked deprecated. Add it anyway?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                != QMessageBox.Yes
            ):
                return
        try:
            recipe = self.client.recipe_for_entry(entry)
        except Exception as exc:
            QMessageBox.warning(self, "Could not add Journey Recipe", str(exc))
            return

        self.state.save_journey_recipe(
            self._library_id(entry),
            str(recipe.get("name") or entry.get("name") or "Journey Recipe"),
            str(recipe.get("description") or entry.get("description") or ""),
            recipe,
        )
        if self.on_added:
            self.on_added()
        self._apply_filter()
        self.status.setText(
            f"Added {recipe.get('name') or entry.get('name')} to your Journey Library."
        )

    def _open_source(self) -> None:
        entry = self._selected()
        source = dict(entry.get("source") or {})
        url = str(source.get("repository") or "")
        if url:
            QDesktopServices.openUrl(QUrl(url))


__all__ = ["JourneyGalleryDialog"]
