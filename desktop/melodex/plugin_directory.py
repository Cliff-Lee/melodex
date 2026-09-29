from __future__ import annotations

import threading
from typing import Any, Callable

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from .plugin_configuration_dialog import configure_plugin
from .plugin_onboarding import (
    configuration_state,
    configuration_summary,
    plugin_configuration_info,
)
from .plugin_health import health_badge, health_summary

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


class _Signals(QObject):
    done = Signal(object)
    error = Signal(str)


class PluginDirectoryDialog(QDialog):
    def __init__(
        self,
        provider_manager,
        on_installed: Callable[[], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.manager = provider_manager
        self.on_installed = on_installed
        self.plugins: list[dict[str, Any]] = []
        self._signals: list[_Signals] = []

        self.setWindowTitle("Melodex Plugin Directory")
        self.resize(920, 660)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Browse providers and capability extensions from the Melodex registry. "
            "Review source, permissions and verification details before installing."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search plugins, capabilities or publishers…")
        self.kind = QComboBox()
        self.kind.addItem("All types", "all")
        self.kind.addItem("Music providers", "provider")
        self.kind.addItem("Enrichment", "enrichment")
        self.capability = QComboBox()
        self.capability.addItem("All capabilities", "all")
        for value in (
            "search",
            "playback",
            "offline",
            "recommendations",
            "identity",
            "metadata",
            "artwork",
            "lyrics",
        ):
            self.capability.addItem(value, value)
        self.refresh_button = QPushButton("Refresh")
        filters.addWidget(self.search, 1)
        filters.addWidget(self.kind)
        filters.addWidget(self.capability)
        filters.addWidget(self.refresh_button)
        layout.addLayout(filters)

        self.status = QLabel("Loading registry…")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#aab0ba")
        layout.addWidget(self.status)

        body = QHBoxLayout()
        self.rows = QListWidget()
        self.rows.setMinimumWidth(410)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        body.addWidget(self.rows, 1)
        body.addWidget(self.details, 1)
        layout.addLayout(body, 1)

        actions = QHBoxLayout()
        self.install_button = QPushButton("Install")
        self.configure_button = QPushButton("Configure…")
        self.test_button = QPushButton("Test plugin")
        self.source_button = QPushButton("View source")
        self.review_button = QPushButton("View review")
        close_button = QPushButton("Close")
        self.install_button.setEnabled(False)
        self.configure_button.setEnabled(False)
        self.test_button.setEnabled(False)
        self.source_button.setEnabled(False)
        self.review_button.setEnabled(False)
        actions.addWidget(self.install_button)
        actions.addWidget(self.configure_button)
        actions.addWidget(self.test_button)
        actions.addWidget(self.source_button)
        actions.addWidget(self.review_button)
        actions.addStretch(1)
        actions.addWidget(close_button)
        layout.addLayout(actions)

        self.rows.currentItemChanged.connect(lambda *_: self._show_details())
        self.search.textChanged.connect(lambda *_: self._apply_filter())
        self.kind.currentIndexChanged.connect(lambda *_: self._apply_filter())
        self.capability.currentIndexChanged.connect(lambda *_: self._apply_filter())
        self.refresh_button.clicked.connect(lambda: self.load_registry(force=True))
        self.install_button.clicked.connect(self._install_selected)
        self.configure_button.clicked.connect(self._configure_selected)
        self.test_button.clicked.connect(self._test_selected)
        self.source_button.clicked.connect(self._open_source)
        self.review_button.clicked.connect(self._open_review)
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
            self.status.setText(message)
            self.install_button.setEnabled(False)
            self.configure_button.setEnabled(False)
            self.test_button.setEnabled(False)
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

    def _installed_ids(self) -> tuple[set[str], set[str]]:
        providers = set(self.manager.providers)
        extensions = {str(row.get("id") or "") for row in self.manager.extensions()}
        return providers, extensions

    def _is_installed(self, entry: dict[str, Any]) -> bool:
        providers, extensions = self._installed_ids()
        plugin_id = str(entry.get("id") or "")
        return plugin_id in (providers if entry.get("kind") == "provider" else extensions)

    def _installed_version(self, entry: dict[str, Any]) -> str:
        plugin_id = str(entry.get("id") or "")
        record = self.manager.installation_record(plugin_id)
        if record.get("version"):
            return str(record.get("version") or "")
        if entry.get("kind") == "provider":
            provider = self.manager.providers.get(plugin_id)
            return str(provider.info.version) if provider is not None else ""
        extension = next(
            (
                row
                for row in self.manager.extensions()
                if str(row.get("id") or "") == plugin_id
            ),
            None,
        )
        return str((extension or {}).get("version") or "")

    def _update_available(self, entry: dict[str, Any]) -> bool:
        if not self._is_installed(entry):
            return False
        return self.manager.registry.update_available(
            entry, self._installed_version(entry)
        )

    def _selected(self) -> dict[str, Any]:
        item = self.rows.currentItem()
        value = item.data(Qt.UserRole) if item else None
        return dict(value or {}) if isinstance(value, dict) else {}

    def load_registry(self, force: bool = False) -> None:
        self.status.setText("Refreshing registry…" if force else "Loading registry…")
        self.rows.clear()
        self.details.clear()
        self.install_button.setEnabled(False)
        self._run_async(
            lambda: self.manager.plugin_registry(force=force).as_dict(),
            self._registry_loaded,
        )

    def _registry_loaded(self, result: Any) -> None:
        result = dict(result or {})
        self.plugins = [
            dict(item) for item in result.get("plugins") or [] if isinstance(item, dict)
        ]
        if result.get("stale"):
            self.status.setText(
                "Using cached registry because refresh failed: "
                + str(result.get("error") or "unknown error")
            )
        else:
            origin = (
                "cached registry"
                if result.get("source") == "cache"
                else "Melodex registry"
            )
            self.status.setText(
                f"Loaded {len(self.plugins)} entries from {origin}. "
                "Installable packages are SHA-256 verified."
            )
        self._apply_filter()

    def _apply_filter(self) -> None:
        self.rows.clear()
        plugins = self.manager.registry.filter_plugins(
            self.plugins,
            self.search.text(),
            str(self.kind.currentData() or "all"),
            str(self.capability.currentData() or "all"),
        )
        providers, extensions = self._installed_ids()
        for entry in plugins:
            plugin_id = str(entry.get("id") or "")
            installed = plugin_id in (
                providers if entry.get("kind") == "provider" else extensions
            )
            capabilities = ", ".join(str(x) for x in entry.get("capabilities") or [])
            update_available = installed and self._update_available(entry)
            config_info = (
                plugin_configuration_info(self.manager, plugin_id)
                if installed
                else {}
            )
            config_state = configuration_state(config_info)
            health = (
                self.manager.plugin_health(plugin_id)
                if installed
                else {}
            )
            health_state = health_badge(health) if installed else ""
            badge = (
                "UPDATE · SETUP NEEDED"
                if update_available and config_state == "setup_needed"
                else "UPDATE"
                if update_available
                else "SETUP NEEDED"
                if installed and config_state == "setup_needed"
                else f"INSTALLED · {health_state}"
                if installed and health_state
                else "INSTALLED"
                if installed
                else str(entry.get("status") or "").upper()
            )
            item = QListWidgetItem(
                f"{entry.get('name') or plugin_id}    ·    {badge}\n"
                f"{entry.get('kind','')} · {capabilities}"
            )
            item.setData(Qt.UserRole, entry)
            self.rows.addItem(item)
        if self.rows.count():
            self.rows.setCurrentRow(0)
        else:
            self.details.setPlainText("No registry entries match these filters.")
            self.install_button.setEnabled(False)
            self.configure_button.setEnabled(False)
            self.test_button.setEnabled(False)
            self.source_button.setEnabled(False)
            self.review_button.setEnabled(False)

    def _show_details(self) -> None:
        entry = self._selected()
        if not entry:
            self.details.clear()
            self.install_button.setEnabled(False)
            self.configure_button.setEnabled(False)
            self.test_button.setEnabled(False)
            self.source_button.setEnabled(False)
            self.review_button.setEnabled(False)
            return

        distribution = dict(entry.get("distribution") or {})
        source = dict(entry.get("source") or {})
        review = dict(entry.get("review") or {})
        capabilities = ", ".join(str(x) for x in entry.get("capabilities") or []) or "—"
        permissions = (
            "\n".join("• " + str(x) for x in entry.get("permissions") or [])
            or "None declared"
        )
        installed = self._is_installed(entry)
        installed_version = self._installed_version(entry) if installed else ""
        update_available = self._update_available(entry) if installed else False
        plugin_id = str(entry.get("id") or "")
        installation = self.manager.installation_record(plugin_id)
        config_info = (
            plugin_configuration_info(self.manager, plugin_id)
            if installed
            else {}
        )
        config_text = configuration_summary(config_info) if installed else "Not installed"
        health = self.manager.plugin_health(plugin_id) if installed else {}
        health_text = health_summary(health) if installed else "Not installed"
        compatible, compatibility_reason = self.manager.registry.compatibility(entry)
        sha256 = str(distribution.get("sha256") or "")
        if installation:
            if installation.get("registry_verified"):
                install_origin = "Registry — package SHA-256 verified at install"
            elif installation.get("method") == "manual":
                install_origin = "Manual file — local SHA-256 recorded; not registry-verified"
            else:
                install_origin = str(installation.get("method") or "unknown")
            install_hash = str(installation.get("package_sha256") or "not recorded")
            installed_at = str(installation.get("installed_at") or "not recorded")
        elif installed:
            install_origin = "Unknown — installed before provenance tracking"
            install_hash = "not recorded"
            installed_at = "not recorded"
        else:
            install_origin = "Not installed"
            install_hash = "—"
            installed_at = "—"
        text = (
            f"{entry.get('name','')}\n"
            f"{entry.get('id','')}\n\n"
            f"{entry.get('description','')}\n\n"
            f"Publisher: {entry.get('publisher') or 'Not specified'}\n"
            f"Version: {entry.get('version','')}\n"
            f"Registry status: {str(entry.get('status') or '').upper()}\n"
            f"License: {entry.get('license') or 'Not specified'}\n"
            f"Capabilities: {capabilities}\n"
            f"Installed: {'Yes' if installed else 'No'}\n"
            f"Installed version: {installed_version or '—'}\n"
            f"Update available: {'Yes' if update_available else 'No'}\n"
            f"Configuration: {config_text}\n"
            f"Health: {health_text}\n"
            f"Install origin: {install_origin}\n"
            f"Installed at: {installed_at}\n"
            f"Installed package SHA-256: {install_hash}\n"
            f"Compatible: {'Yes' if compatible else 'No'}"
            + (f" — {compatibility_reason}" if compatibility_reason else "")
            + "\n\n"
            f"Declared permissions:\n{permissions}\n\n"
            f"Package: {distribution.get('format') or '—'}\n"
            f"Size: {distribution.get('size_bytes') or 'not supplied'} bytes\n"
            f"SHA-256: {sha256 or 'not supplied'}\n"
            f"Source policy: {entry.get('source_policy') or 'not supplied'}\n"
            f"Repository: {source.get('repository') or 'not supplied'}\n"
            f"Last registry review: {review.get('last_reviewed_at') or 'not supplied'}\n"
            f"Review record: {review.get('record') or 'not supplied'}"
        )
        self.details.setPlainText(text)

        package_url = str(distribution.get("package_url") or "")
        self.install_button.setEnabled(
            bool(
                package_url
                and sha256
                and compatible
                and entry.get("status") != "blocked"
            )
        )
        self.install_button.setText(
            "Update" if update_available else "Reinstall" if installed else "Install"
        )
        self.configure_button.setEnabled(
            bool(installed and list(config_info.get("fields") or []))
        )
        self.test_button.setEnabled(bool(installed))
        self.source_button.setEnabled(bool(source.get("repository")))
        self.review_button.setEnabled(bool(review.get("record")))

    def _install_selected(self) -> None:
        entry = self._selected()
        if not entry:
            return
        if entry.get("status") == "deprecated":
            if (
                QMessageBox.question(
                    self,
                    "Deprecated plugin",
                    "This plugin is marked deprecated. Install it anyway?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                != QMessageBox.Yes
            ):
                return

        permissions = (
            "\n".join("• " + str(x) for x in entry.get("permissions") or [])
            or "None declared"
        )
        distribution = dict(entry.get("distribution") or {})
        if (
            QMessageBox.question(
                self,
                "Install plugin",
                f"Install {entry.get('name')} {entry.get('version')}?\n\n"
                f"Status: {str(entry.get('status') or '').upper()}\n"
                f"Publisher: {entry.get('publisher') or 'Not specified'}\n"
                f"License: {entry.get('license') or 'Not specified'}\n\n"
                f"Declared permissions:\n{permissions}\n\n"
                "The downloaded package must match this SHA-256:\n"
                f"{distribution.get('sha256')}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return

        self.status.setText(f"Downloading and verifying {entry.get('name')}…")
        self.install_button.setEnabled(False)
        self._run_async(
            lambda: self.manager.download_registry_entry(entry),
            lambda package: self._install_downloaded(entry, package),
        )

    def _install_downloaded(self, entry: dict[str, Any], package: Any) -> None:
        try:
            result = self.manager.install_downloaded_registry_entry(entry, package)
        except Exception as exc:
            self.status.setText(f"Install failed: {exc}")
            self.install_button.setEnabled(True)
            return
        self._installed(entry, result)

    def _installed(self, entry: dict[str, Any], result: Any) -> None:
        result = dict(result or {})
        plugin_id = str(result.get("id") or entry.get("id") or "")
        name = str(result.get("name") or entry.get("name") or plugin_id)
        if self.on_installed:
            self.on_installed()
        self._apply_filter()

        config_info = plugin_configuration_info(self.manager, plugin_id)
        if configuration_state(config_info) == "setup_needed":
            self.status.setText(
                f"Installed {name}; setup is required before it is ready."
            )
            configure_plugin(self, self.manager, plugin_id, setup=True)
            if self.on_installed:
                self.on_installed()
            self._apply_filter()
            config_info = plugin_configuration_info(self.manager, plugin_id)

        ready = configuration_state(config_info) != "setup_needed"
        self.status.setText(
            f"Installed {name}. "
            + (
                "Ready to use."
                if ready
                else "Setup is still required; select it and choose Configure…."
            )
        )
        QMessageBox.information(
            self,
            "Plugin installed",
            f"Installed {name} successfully.\n\n"
            + (
                "Ready to use."
                if ready
                else "Setup is still required before this plugin is ready."
            ),
        )

    def _configure_selected(self) -> None:
        entry = self._selected()
        if not entry or not self._is_installed(entry):
            return
        plugin_id = str(entry.get("id") or "")
        result = configure_plugin(self, self.manager, plugin_id)
        if self.on_installed:
            self.on_installed()
        self._apply_filter()
        if result and result.get("ready", True):
            self.status.setText(
                f"{entry.get('name') or plugin_id} is configured and ready."
            )

    def _test_selected(self) -> None:
        entry = self._selected()
        if not entry or not self._is_installed(entry):
            return
        plugin_id = str(entry.get("id") or "")
        self.status.setText(f"Testing {entry.get('name') or plugin_id}…")
        self.test_button.setEnabled(False)
        self._run_async(
            lambda: self.manager.test_plugin_health(plugin_id),
            lambda result: self._health_tested(entry, result),
        )

    def _health_tested(self, entry: dict[str, Any], result: Any) -> None:
        result = dict(result or {})
        self._apply_filter()
        self.status.setText(
            f"{entry.get('name') or entry.get('id')}: {health_summary(result)}"
        )

    def _open_source(self) -> None:
        entry = self._selected()
        source = dict(entry.get("source") or {})
        url = str(source.get("repository") or "")
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _open_review(self) -> None:
        entry = self._selected()
        review = dict(entry.get("review") or {})
        url = str(review.get("record") or "")
        if url:
            QDesktopServices.openUrl(QUrl(url))
