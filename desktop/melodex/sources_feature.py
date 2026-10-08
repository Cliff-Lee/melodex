from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .plugin_health import health_summary
from .source_policy_controller import SourcePolicyController
from .ux_components import SourceCard, set_help


class SourcesFeature(QWidget):
    """Sources page presentation and source/plugin lifecycle orchestration.

    SourcePolicyController remains the authority for Qt-free source/plugin
    decisions. This widget owns the Sources page, feature-specific state and
    operational workflows without depending on MainWindow.
    """

    musicFolderRequested = Signal()
    providerSearchRequested = Signal(str)
    extensionUseRequested = Signal(str)
    bridgeRequested = Signal()
    pluginPresenceChanged = Signal()
    sourceCatalogChanged = Signal()
    actionMarked = Signal(str)
    statusMessageRequested = Signal(str, int)

    def __init__(
        self,
        providers: Any,
        policy: SourcePolicyController,
        user_state: Any,
        *,
        run_async: Callable[..., Any],
        diagnostics_metrics: Callable[[], dict[str, Any]],
        is_active: Callable[[], bool],
        power_tools_enabled: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.providers = providers
        self.policy = policy
        self.user_state = user_state
        self._run_async = run_async
        self._diagnostics_metrics = diagnostics_metrics
        self._is_active = is_active
        self._config_refresh_in_progress = False
        self._power_tools_enabled = bool(power_tools_enabled)

        self.title_label: QLabel
        self.source_welcome: QFrame
        self.source_check_all: QPushButton
        self.sources_overview: QLabel
        self.source_primary_button: QPushButton
        self.source_feature_picker: QFrame
        self.source_feature_buttons: dict[str, QPushButton] = {}
        self.sources_list: QListWidget
        self.source_hint: QLabel
        self.legacy_source_notice: QLabel
        self.source_power_panel: QFrame

        self._build_page()

    @property
    def config_refresh_in_progress(self) -> bool:
        return self._config_refresh_in_progress

    def _status(self, message: str, timeout_ms: int = 0) -> None:
        self.statusMessageRequested.emit(str(message), int(timeout_ms))

    def _optional_integrations_ready(self) -> bool:
        if bool(getattr(self.providers, "optional_plugins_loaded", True)):
            return True
        self._status(
            "Optional integrations are still loading. Try again in a moment.",
            3500,
        )
        return False

    def _build_page(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        self.title_label = QLabel("Sources & plugins")
        self.title_label.setObjectName("pageTitle")
        layout.addWidget(self.title_label)

        subtitle = QLabel("Choose where your music and extra features come from.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        self.source_welcome = QFrame()
        self.source_welcome.setObjectName("sourceFirstRun")
        welcome_l = QHBoxLayout(self.source_welcome)
        welcome_l.setContentsMargins(16, 13, 16, 13)
        welcome_l.setSpacing(12)

        welcome_text = QVBoxLayout()
        welcome_text.setSpacing(3)
        welcome_title = QLabel("Nothing else is required")
        welcome_title.setObjectName("sourceFirstRunTitle")
        welcome_body = QLabel(
            "Your library works on its own. Add sources or plugins only when you want them."
        )
        welcome_body.setObjectName("sourceFirstRunBody")
        welcome_body.setWordWrap(True)
        welcome_text.addWidget(welcome_title)
        welcome_text.addWidget(welcome_body)
        welcome_l.addLayout(welcome_text, 1)

        welcome_plugins = QPushButton("Browse optional features")
        welcome_plugins.setObjectName("secondaryButton")
        welcome_plugins.clicked.connect(self.open_plugin_directory)
        welcome_done = QPushButton("Got it")
        welcome_done.setObjectName("quietButton")
        welcome_done.clicked.connect(self.dismiss_intro)
        welcome_l.addWidget(welcome_plugins)
        welcome_l.addWidget(welcome_done)

        self.source_welcome.setVisible(
            not self.user_state.get_bool("sources_intro_seen", False)
        )
        layout.addWidget(self.source_welcome)

        overview = QFrame()
        overview.setObjectName("sourceOverview")
        overview_l = QVBoxLayout(overview)
        overview_l.setContentsMargins(18, 16, 18, 16)
        overview_l.setSpacing(12)

        overview_head = QHBoxLayout()
        overview_title = QLabel("Your sources")
        overview_title.setStyleSheet("font-size:18px;font-weight:720")
        overview_head.addWidget(overview_title)
        overview_head.addStretch(1)
        self.source_check_all = QPushButton("Check connections")
        self.source_check_all.setObjectName("quietButton")
        self.source_check_all.setVisible(self._power_tools_enabled)
        self.source_check_all.clicked.connect(self.test_all_plugins)
        set_help(
            self.source_check_all,
            "Check installed sources and plugins",
            "Runs bounded connection/runtime checks for installed plugins. It does not change your setup.",
        )
        overview_head.addWidget(self.source_check_all)
        overview_l.addLayout(overview_head)

        self.sources_overview = QLabel(
            "Local music first. Add other sources and features when they are useful."
        )
        self.sources_overview.setWordWrap(True)
        self.sources_overview.setObjectName("mutedText")
        overview_l.addWidget(self.sources_overview)
        layout.addWidget(overview)

        actions = QHBoxLayout()
        local = QPushButton("+ Add my music")
        local.setObjectName("primaryButton")
        local.clicked.connect(
            lambda _checked=False: self.musicFolderRequested.emit()
        )
        directory = QPushButton("Add features…")
        directory.setObjectName("secondaryButton")
        directory.clicked.connect(self.toggle_feature_picker)
        streams = QPushButton("My streams")
        streams.clicked.connect(self.show_streams_dialog)
        self.source_primary_button = QPushButton("Use selected")
        self.source_primary_button.clicked.connect(self._run_primary_action)
        self.source_primary_button.setEnabled(False)
        self.source_primary_button.hide()
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
        layout.addLayout(actions)

        self.source_feature_picker = QFrame()
        self.source_feature_picker.setObjectName("pluginFeaturePicker")
        feature_l = QHBoxLayout(self.source_feature_picker)
        feature_l.setContentsMargins(14, 10, 14, 10)
        feature_l.setSpacing(8)
        feature_text = QVBoxLayout()
        feature_text.setSpacing(1)
        feature_title = QLabel("What would you like to add?")
        feature_title.setObjectName("pluginFeatureTitle")
        feature_subtitle = QLabel("Browse plugins by what they add.")
        feature_subtitle.setObjectName("pluginFeatureSubtitle")
        feature_text.addWidget(feature_title)
        feature_text.addWidget(feature_subtitle)
        feature_l.addLayout(feature_text, 1)

        for label, capability in (
            ("All features", ""),
            ("More music", "search"),
            ("Lyrics", "lyrics"),
            ("Artwork", "artwork"),
            ("Recommendations", "recommendations"),
            ("Context", "context"),
        ):
            button = QPushButton(label)
            button.setObjectName("featureChip")
            button.clicked.connect(
                lambda _checked=False, value=capability: self.open_plugin_directory(value)
            )
            self.source_feature_buttons[capability] = button
            feature_l.addWidget(button)
        self.source_feature_picker.hide()
        layout.addWidget(self.source_feature_picker)

        self.sources_list = QListWidget()
        self.sources_list.setObjectName("sourcesList")
        self.sources_list.setSpacing(5)
        self.sources_list.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.sources_list, 1)

        self.source_hint = QLabel("Select a source for its available actions.")
        self.source_hint.setWordWrap(True)
        self.source_hint.setObjectName("subtleText")
        self.source_hint.hide()
        layout.addWidget(self.source_hint)

        support_row = QHBoxLayout()
        diagnostics = QPushButton("Export redacted diagnostics…")
        diagnostics.setObjectName("quietButton")
        diagnostics.clicked.connect(self.export_diagnostics)
        set_help(
            diagnostics,
            "Export redacted diagnostics",
            "Save a support snapshot with version, indexing, NAS/storage and responsiveness metrics. "
            "Melodex omits library paths, filenames, credentials, stream URLs and raw scan errors.",
        )
        support_row.addWidget(diagnostics)
        support_note = QLabel("Useful for beta reports · review the JSON before sharing")
        support_note.setStyleSheet("color:#8793a4")
        support_row.addWidget(support_note)
        support_row.addStretch(1)
        layout.addLayout(support_row)

        self.legacy_source_notice = QLabel()
        self.legacy_source_notice.setWordWrap(True)
        self.legacy_source_notice.setStyleSheet(
            "color:#d5b26f;background:#241d12;border:1px solid #4f3d1d;"
            "border-radius:8px;padding:8px"
        )
        self.legacy_source_notice.hide()
        layout.addWidget(self.legacy_source_notice)

        self.source_power_panel = QFrame()
        self.source_power_panel.setObjectName("powerPanel")
        power = QVBoxLayout(self.source_power_panel)
        power.setContentsMargins(14, 12, 14, 12)
        power.setSpacing(8)

        title = QLabel("Power tools")
        title.setStyleSheet("font-size:15px;font-weight:700")
        power.addWidget(title)

        provider_row = QHBoxLayout()
        jam = QPushButton("Jamendo settings…")
        jam.clicked.connect(self._jamendo_settings)
        inst = QPushButton("Install .mdxprovider…")
        inst.clicked.connect(self.install_provider)
        ext = QPushButton("Install .mdxplugin…")
        ext.clicked.connect(self.install_extension)
        bridge = QPushButton("Provider Bridge…")
        bridge.clicked.connect(
            lambda _checked=False: self.bridgeRequested.emit()
        )
        provider_row.addWidget(jam)
        provider_row.addWidget(inst)
        provider_row.addWidget(ext)
        provider_row.addWidget(bridge)
        provider_row.addStretch(1)
        power.addLayout(provider_row)

        priority = QHBoxLayout()
        up = QPushButton("Prefer source ↑")
        down = QPushButton("Prefer source ↓")
        configure = QPushButton("Configure selected…")
        configure.clicked.connect(self.configure_selected_plugin)
        toggle_ext = QPushButton("Enable / disable extension")
        toggle_ext.clicked.connect(self.toggle_extension)
        remove_ext = QPushButton("Remove extension")
        remove_ext.clicked.connect(self.remove_extension)
        test_plugin = QPushButton("Test selected")
        test_plugin.clicked.connect(self.test_selected_plugin)
        up.clicked.connect(lambda: self.move_source(-1))
        down.clicked.connect(lambda: self.move_source(1))
        priority.addWidget(up)
        priority.addWidget(down)
        priority.addWidget(configure)
        priority.addWidget(test_plugin)
        priority.addWidget(toggle_ext)
        priority.addStretch(1)
        power.addLayout(priority)

        provider_actions = QHBoxLayout()
        remove_provider = QPushButton("Remove selected provider")
        remove_provider.clicked.connect(self.remove_provider)
        restore_bundled = QPushButton("Restore bundled sources")
        restore_bundled.clicked.connect(self.restore_bundled_sources)
        provider_actions.addWidget(remove_provider)
        provider_actions.addWidget(remove_ext)
        provider_actions.addWidget(restore_bundled)
        provider_actions.addStretch(1)
        power.addLayout(provider_actions)

        self.source_power_panel.setVisible(self._power_tools_enabled)
        layout.addWidget(self.source_power_panel)

    def dismiss_intro(self) -> None:
        self.user_state.set_bool("sources_intro_seen", True)
        self.source_welcome.hide()

    def set_power_tools_visible(self, enabled: bool) -> None:
        self._power_tools_enabled = bool(enabled)
        self.source_power_panel.setVisible(self._power_tools_enabled)
        self.source_check_all.setVisible(self._power_tools_enabled)

    def selected_source_id(self) -> str:
        item = self.sources_list.currentItem()
        return str(item.data(Qt.UserRole) or "") if item else ""

    def selected_plugin_id(self) -> str:
        return self.policy.selected_plugin_id(self.selected_source_id())

    def selected_extension_id(self) -> str:
        value = self.selected_source_id()
        return value.split(":", 1)[1] if value.startswith("extension:") else ""

    def selected_provider_id(self) -> str:
        value = self.selected_source_id()
        if value.startswith("extension:") or value in {"", "local", "jamendo", "streams"}:
            return ""
        return value

    def select_source(self, source_id: str) -> bool:
        wanted = str(source_id or "")
        for row in range(self.sources_list.count()):
            item = self.sources_list.item(row)
            if str(item.data(Qt.UserRole) or "") == wanted:
                self.sources_list.setCurrentRow(row)
                return True
        return False

    def refresh(self) -> None:
        self.sources_list.clear()

        def heading(text: str) -> None:
            item = QListWidgetItem(str(text).upper())
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(QColor("#718096"))
            self.sources_list.addItem(item)

        def add_provider(pid: str, *, origin: str, section_kind: str) -> None:
            provider = self.providers.providers[pid]
            name = provider.info.name.replace(" (reference provider)", "")
            if pid == "local":
                count = len(self.providers.local_catalog())
                status = f"{count:,} tracks" if count else "Add music"
                kind = "Your library"
                icon_key = "local"
            elif pid == "jamendo":
                configured = bool(
                    str(self.providers.settings.get("jamendo_client_id", "")).strip()
                )
                status = "Ready" if configured else "Setup needed"
                kind = "Optional catalogue"
                icon_key = "provider"
            elif pid == "streams":
                count = len(self.providers.user_streams())
                status = f"{count} stream" if count == 1 else f"{count} streams"
                kind = "Your links"
                icon_key = "stream"
            else:
                config_status = (
                    self.providers.plugin_config.cached_status(
                        pid,
                        provider.info.configuration,
                    )
                    if provider.info.configuration
                    else {"ready": True}
                )
                health = self.providers.plugin_health(pid, cached_config=True)
                health_state = str(health.get("status") or "untested")
                config_ready = config_status.get("ready", True)
                if config_ready is None:
                    status = "Checking…"
                elif config_ready is False:
                    status = "Setup needed"
                elif health_state in {"error", "stopped", "unhealthy", "unavailable"}:
                    status = "Needs attention"
                elif health_state in {"ready", "ok"}:
                    status = "Ready"
                elif health_state == "disabled":
                    status = "Disabled"
                else:
                    status = "Not tested"
                caps = [str(value) for value in list(provider.info.capabilities or []) if value]
                if "recommendations" in caps and "search" not in caps:
                    kind = "Recommendations"
                    icon_key = "recommendation"
                elif "search" in caps:
                    kind = "Music source"
                    icon_key = (
                        "radio"
                        if any(token in name.casefold() for token in ("radio", "somafm"))
                        else "provider"
                    )
                else:
                    kind = section_kind
                    icon_key = "provider"

            friendly_descriptions = {
                "local": "Your own music on this computer. Nothing is uploaded.",
                "streams": "Direct radio or audio links that you add yourself.",
                "jamendo": "Optional connection to Jamendo's independent-music catalogue.",
            }
            lower_name = name.casefold()
            if "internet archive" in lower_name:
                description = "Explore recordings, live music and spoken audio from Internet Archive."
            elif "librivox" in lower_name:
                description = "Public-domain audiobooks read by volunteers."
            elif "radio browser" in lower_name:
                description = "Search a worldwide community directory of internet radio stations."
            elif "somafm" in lower_name:
                description = "Curated listener-supported internet radio from SomaFM."
            elif "wikimedia" in lower_name:
                description = "Openly licensed and public-domain audio from Wikimedia Commons."
            elif "ccmixter" in lower_name:
                description = "Creative Commons music, samples and remixes."
            else:
                description = friendly_descriptions.get(
                    pid,
                    str(provider.info.description or ""),
                )

            item = QListWidgetItem()
            item.setData(Qt.UserRole, pid)
            card = SourceCard(
                name,
                description,
                status,
                kind=kind,
                icon_key=icon_key,
                origin=origin,
            )
            item.setSizeHint(card.sizeHint())
            self.sources_list.addItem(item)
            self.sources_list.setItemWidget(item, card)

        order = self.providers.provider_order()
        builtins = [
            pid
            for pid in ("local", "streams", "jamendo")
            if pid in self.providers.providers
        ]
        bundled = [
            pid
            for pid in order
            if pid not in builtins and self.providers.is_bundled_provider(pid)
        ]
        optional = [
            pid
            for pid in order
            if pid not in builtins and pid not in bundled
        ]

        heading("Your music & connections")
        for pid in builtins:
            add_provider(
                pid,
                origin="Built in" if pid != "jamendo" else "Optional",
                section_kind="Built in",
            )

        if bundled:
            heading("Included with Melodex")
            for pid in bundled:
                add_provider(pid, origin="Included", section_kind="Included source")

        if optional:
            heading("Installed music plugins")
            for pid in optional:
                installation = self.providers.installation_record(pid)
                method = str(installation.get("method") or "")
                origin = (
                    "Registry"
                    if method == "registry"
                    else "Manual"
                    if method == "manual"
                    else "Installed"
                )
                add_provider(pid, origin=origin, section_kind="Plugin source")

        extensions = self.providers.extensions(cached_config=True)
        if extensions:
            heading("Installed enhancements")
            for extension in extensions:
                extension_id = str(extension.get("id") or "")
                enabled = bool(extension.get("enabled", True))
                config_status = dict(extension.get("configuration_status") or {})
                health = self.providers.plugin_health(
                    extension_id,
                    cached_config=True,
                )
                health_state = str(health.get("status") or "untested")
                config_ready = config_status.get("ready", True)
                if not enabled:
                    status = "Disabled"
                elif config_status.get("declared") and config_ready is None:
                    status = "Checking…"
                elif config_status.get("declared") and config_ready is False:
                    status = "Setup needed"
                elif health_state in {"error", "stopped", "unhealthy", "unavailable"}:
                    status = "Needs attention"
                elif health_state in {"ready", "ok"}:
                    status = "Ready"
                else:
                    status = "Not tested"

                raw_capabilities = [
                    str(value)
                    for value in list(extension.get("capabilities") or [])
                    if value
                ]
                capabilities = ", ".join(
                    self.policy.capability_label(value)
                    for value in raw_capabilities
                ) or "Adds extra Melodex capabilities"
                description = str(extension.get("description") or capabilities)
                if "library_suggestions" in raw_capabilities:
                    kind = "Recommendations"
                    icon_key = "recommendation"
                elif "artwork" in raw_capabilities:
                    kind = "Artwork"
                    icon_key = "artwork"
                elif "lyrics" in raw_capabilities:
                    kind = "Lyrics"
                    icon_key = "lyrics"
                elif "context" in raw_capabilities:
                    kind = "Context"
                    icon_key = "context"
                elif any(value in raw_capabilities for value in ("metadata", "identity")):
                    kind = "Metadata"
                    icon_key = "metadata"
                else:
                    kind = "Enhancement"
                    icon_key = "plugin"

                installation = self.providers.installation_record(extension_id)
                method = str(installation.get("method") or "")
                origin = (
                    "Registry"
                    if method == "registry"
                    else "Manual"
                    if method == "manual"
                    else "Installed"
                )

                item = QListWidgetItem()
                item.setData(Qt.UserRole, "extension:" + extension_id)
                card = SourceCard(
                    str(extension.get("name") or extension_id),
                    description,
                    status,
                    kind=kind,
                    icon_key=icon_key,
                    origin=origin,
                )
                item.setSizeHint(card.sizeHint())
                self.sources_list.addItem(item)
                self.sources_list.setItemWidget(item, card)

        active_included = len(bundled)
        optional_count = len(optional) + len(extensions)
        setup_needed = 0
        for pid in optional + bundled:
            provider = self.providers.providers.get(pid)
            if provider is not None and provider.info.configuration:
                config = self.providers.plugin_config.cached_status(
                    pid,
                    provider.info.configuration,
                )
                if config.get("ready") is False:
                    setup_needed += 1
        for extension in extensions:
            config = dict(extension.get("configuration_status") or {})
            if config.get("declared") and config.get("ready") is False:
                setup_needed += 1

        local_count = len(self.providers.local_catalog())
        plugin_text = (
            f"{optional_count} plugin{'s' if optional_count != 1 else ''}"
            if optional_count
            else "no plugins"
        )
        summary = (
            f"{local_count:,} local track{'s' if local_count != 1 else ''} · "
            f"{active_included} included source{'s' if active_included != 1 else ''} · "
            f"{plugin_text}"
        )
        if setup_needed:
            summary += f" · {setup_needed} need setup"
        self.sources_overview.setText(summary)

        legacy = self.providers.quarantined_legacy_providers()
        if legacy:
            names = ", ".join(
                str(row.get("name") or row.get("id") or "legacy provider")
                for row in legacy
            )
            self.legacy_source_notice.setText(
                "Legacy development provider disabled: "
                + names
                + ". It is not part of public Melodex and will not be searched or played. "
                "Its old local files have been left untouched."
            )
            self.legacy_source_notice.show()
        else:
            self.legacy_source_notice.hide()

        self.sourceCatalogChanged.emit()
        self._selection_changed()

    def refresh_config_statuses_async(self) -> None:
        if self._config_refresh_in_progress or not self._is_active():
            return
        self._config_refresh_in_progress = True

        def load() -> None:
            for pid in self.providers.provider_order():
                provider = self.providers.providers.get(pid)
                if (
                    provider is not None
                    and pid not in {"local", "jamendo", "streams"}
                    and provider.info.configuration
                ):
                    self.providers.plugin_config.status(
                        pid,
                        provider.info.configuration,
                    )
            self.providers.extensions(cached_config=False)

        def done(_result: object) -> None:
            self._config_refresh_in_progress = False
            if self._is_active():
                self.refresh()
                self.pluginPresenceChanged.emit()

        def failed(_error: str) -> None:
            self._config_refresh_in_progress = False
            if self._is_active():
                self._status(
                    "Some source configuration checks are still unavailable",
                    4000,
                )

        self._run_async(
            load,
            done,
            failed,
            priority="visible",
            task_name="source-config-status",
        )

    def _selection_changed(self) -> None:
        self.actionMarked.emit("sources:selection")
        key = self.selected_source_id()
        enabled = bool(key)
        self.source_primary_button.setEnabled(enabled)
        self.source_primary_button.setVisible(enabled)
        self.source_hint.setVisible(enabled)

        presentation = self.policy.selection_presentation(key)
        self.source_primary_button.setText(presentation.button_text)
        if presentation.hint:
            self.source_hint.setText(presentation.hint)

    def _run_primary_action(self) -> None:
        action = self.policy.primary_action(self.selected_source_id())

        if action.kind == "choose_music_folder":
            self.musicFolderRequested.emit()
        elif action.kind == "jamendo_settings":
            self._jamendo_settings()
        elif action.kind == "manage_streams":
            self.show_streams_dialog()
        elif action.kind == "configure_plugin":
            self.configure_selected_plugin()
        elif action.kind == "use_extension":
            self.extensionUseRequested.emit(action.target)
        elif action.kind == "open_provider_search":
            self.providerSearchRequested.emit(action.target)
        elif action.kind == "test_plugin":
            self.test_selected_plugin()

    def move_source(self, delta: int) -> None:
        if not self._optional_integrations_ready():
            return
        item = self.sources_list.currentItem()
        if not item:
            return
        provider_id = str(item.data(Qt.UserRole) or "")
        order = self.providers.provider_order()
        if provider_id not in order:
            return
        index = order.index(provider_id)
        target = max(0, min(len(order) - 1, index + int(delta)))
        if index == target:
            return
        order[index], order[target] = order[target], order[index]
        self.providers.set_provider_order(order)
        self.refresh()
        self.sources_list.setCurrentRow(target)
        self._status("Source priority updated", 2500)

    def _jamendo_settings(self) -> None:
        value, ok = QInputDialog.getText(
            self,
            "Jamendo reference provider",
            "Your Jamendo developer client ID:",
            text=str(self.providers.settings.get("jamendo_client_id", "")),
        )
        if ok:
            self.providers.set_jamendo_client_id(value.strip())
            self._status("Jamendo source updated", 3000)

    def toggle_feature_picker(self) -> None:
        visible = not self.source_feature_picker.isVisible()
        self.source_feature_picker.setVisible(visible)
        self._status(
            "Choose what you want to add" if visible else "Feature picker hidden",
            1800,
        )

    def open_plugin_directory(self, capability: str = "") -> None:
        if not self._optional_integrations_ready():
            return
        from .plugin_directory import PluginDirectoryDialog

        dialog = PluginDirectoryDialog(
            self.providers,
            on_installed=self._plugin_directory_changed,
            on_use=self._use_plugin_directory_entry,
            initial_capability=str(capability or ""),
            parent=self,
        )
        dialog.exec()

    def _plugin_directory_changed(self) -> None:
        self.refresh()
        self.pluginPresenceChanged.emit()

    def _use_plugin_directory_entry(self, entry: dict[str, Any]) -> None:
        plugin_id = str(entry.get("id") or "")
        if not plugin_id:
            return
        if str(entry.get("kind") or "") == "provider":
            self.providerSearchRequested.emit(plugin_id)
        else:
            self.extensionUseRequested.emit(plugin_id)

    def export_diagnostics(self) -> None:
        from .diagnostics import write_diagnostics

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export redacted diagnostics",
            "melodex-diagnostics.json",
            "JSON files (*.json)",
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")

        try:
            write_diagnostics(
                path,
                self.providers,
                ui_metrics=dict(self._diagnostics_metrics() or {}),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Could not export diagnostics", str(exc))
            return

        QMessageBox.information(
            self,
            "Diagnostics exported",
            f"Saved redacted diagnostics to:\n{path}\n\n"
            "The export is designed to omit credentials, local library paths, "
            "stream URLs and playback secrets. Review the file before sharing it.",
        )
        self._status(f"Exported {path.name}", 4000)

    def install_provider(self) -> None:
        if not self._optional_integrations_ready():
            return
        from .plugin_configuration_dialog import configure_plugin
        from .plugin_onboarding import plugin_needs_setup

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Install provider",
            filter="Melodex Provider (*.mdxprovider *.zip)",
        )
        if not path:
            return
        try:
            provider = self.providers.install_package(Path(path))
            self.refresh()
            if plugin_needs_setup(self.providers, provider.info.id):
                configure_plugin(self, self.providers, provider.info.id, setup=True)
                self.refresh()
            QMessageBox.information(
                self,
                "Provider installed",
                f"Installed {provider.info.name}"
                + (
                    "\n\nSetup is still required before this provider is ready."
                    if plugin_needs_setup(self.providers, provider.info.id)
                    else "\n\nReady to use."
                ),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Could not install provider", str(exc))

    def install_extension(self) -> None:
        if not self._optional_integrations_ready():
            return
        from .plugin_configuration_dialog import configure_plugin
        from .plugin_onboarding import plugin_needs_setup

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Install capability extension",
            filter="Melodex Extension (*.mdxplugin *.zip)",
        )
        if not path:
            return
        try:
            info = self.providers.install_extension(Path(path))
            self.refresh()
            if plugin_needs_setup(self.providers, info.id):
                configure_plugin(self, self.providers, info.id, setup=True)
                self.refresh()
            QMessageBox.information(
                self,
                "Extension installed",
                f"Installed {info.name}\n\nCapabilities: {', '.join(info.capabilities)}"
                + (
                    "\n\nSetup is still required before this extension is ready."
                    if plugin_needs_setup(self.providers, info.id)
                    else "\n\nReady to use."
                ),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Could not install extension", str(exc))

    def test_all_plugins(self) -> None:
        if not self._optional_integrations_ready():
            return
        plugin_ids = [
            pid
            for pid in self.providers.provider_order()
            if pid not in {"local", "jamendo", "streams"}
        ]
        plugin_ids.extend(
            str(row.get("id") or "")
            for row in self.providers.extensions()
            if str(row.get("id") or "")
        )
        plugin_ids = list(dict.fromkeys(plugin_ids))
        if not plugin_ids:
            self._status("No installed plugins to check", 3000)
            return

        self.source_check_all.setEnabled(False)
        self.source_check_all.setText(f"Checking 0/{len(plugin_ids)}…")
        self._status(
            f"Checking {len(plugin_ids)} installed source/plugin connections…"
        )

        def work() -> list[dict[str, Any]]:
            results = []
            total = len(plugin_ids)
            for index, plugin_id in enumerate(plugin_ids, 1):
                try:
                    result = dict(
                        self.providers.test_plugin_health(plugin_id, timeout=6.0) or {}
                    )
                except Exception as exc:
                    result = {
                        "plugin_id": plugin_id,
                        "name": plugin_id,
                        "status": "error",
                        "message": str(exc),
                    }
                result["_index"] = index
                result["_total"] = total
                results.append(result)
            return results

        def done(results: object) -> None:
            rows = [
                dict(value)
                for value in list(results or [])
                if isinstance(value, dict)
            ]
            self.source_check_all.setEnabled(True)
            self.source_check_all.setText("Check installed")
            self.refresh()
            ready = sum(
                1
                for row in rows
                if str(row.get("status") or "") in {"ready", "ok"}
            )
            setup = sum(
                1
                for row in rows
                if str(row.get("status") or "") == "setup_required"
            )
            attention = len(rows) - ready - setup
            bits = [f"{ready} ready"]
            if setup:
                bits.append(f"{setup} need setup")
            if attention:
                bits.append(f"{attention} need attention or are unavailable")
            summary = " · ".join(bits)
            self._status("Plugin check complete · " + summary, 7000)
            QMessageBox.information(
                self,
                "Installed plugin check",
                "Checked the installed optional sources and enhancements.\n\n"
                + summary
                + "\n\nSelect any item marked Not tested/Needs attention for its individual details.",
            )

        def failed(error: str) -> None:
            self.source_check_all.setEnabled(True)
            self.source_check_all.setText("Check installed")
            self._status(f"Plugin check stopped: {error}", 5000)

        self._run_async(
            work,
            done,
            failed,
            priority="background",
            task_name="plugin-health-all",
        )

    def test_selected_plugin(self) -> None:
        if not self._optional_integrations_ready():
            return
        plugin_id = self.selected_plugin_id()
        if not plugin_id:
            self._status(
                "Select an installed third-party provider or extension first",
                3000,
            )
            return
        self._status("Testing plugin…")
        self._run_async(
            lambda: self.providers.test_plugin_health(plugin_id),
            lambda result: self._finish_plugin_health_test(plugin_id, result),
            priority="foreground",
            task_name="plugin-health-selected",
        )

    def _finish_plugin_health_test(self, plugin_id: str, result: object) -> None:
        from .plugin_configuration_dialog import configure_plugin

        health = dict(result or {})
        self.refresh()
        self._status(health_summary(health), 6000)
        if health.get("status") == "setup_required":
            answer = QMessageBox.question(
                self,
                "Plugin setup required",
                f"{health.get('name') or plugin_id} needs setup before it can be tested.\n\nConfigure it now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                configure_plugin(self, self.providers, plugin_id, setup=True)
                self.refresh()
            return
        QMessageBox.information(
            self,
            "Plugin health",
            f"{health.get('name') or plugin_id}\n\n{health_summary(health)}",
        )

    def configure_selected_plugin(self) -> None:
        if not self._optional_integrations_ready():
            return
        from .plugin_configuration_dialog import configure_plugin

        plugin_id = self.selected_plugin_id()
        if not plugin_id:
            self._status("Select an installed provider or extension first", 3000)
            return
        result = configure_plugin(self, self.providers, plugin_id)
        self.refresh()
        if result is not None and result.get("ready", True):
            self._status("Plugin configuration updated", 3000)

    def toggle_extension(self) -> None:
        if not self._optional_integrations_ready():
            return
        extension_id = self.selected_extension_id()
        if not extension_id:
            self._status("Select a capability extension first", 2500)
            return
        extension = next(
            (
                value
                for value in self.providers.extensions()
                if str(value.get("id") or "") == extension_id
            ),
            None,
        )
        if not extension:
            return
        enabled = not bool(extension.get("enabled", True))
        self.providers.set_extension_enabled(extension_id, enabled)
        self.refresh()
        self._status(
            f"{extension.get('name') or extension_id} {'enabled' if enabled else 'disabled'}",
            3000,
        )

    def remove_extension(self) -> None:
        if not self._optional_integrations_ready():
            return
        extension_id = self.selected_extension_id()
        if not extension_id:
            self._status("Select a capability extension first", 2500)
            return
        extension = next(
            (
                value
                for value in self.providers.extensions()
                if str(value.get("id") or "") == extension_id
            ),
            {},
        )
        name = str(extension.get("name") or extension_id)
        answer = QMessageBox.question(
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
            self.refresh()
            self._status(f"Removed {name}", 3000)

    def remove_provider(self) -> None:
        if not self._optional_integrations_ready():
            return
        plugin_id = self.selected_provider_id()
        if not plugin_id:
            self._status("Select an installed provider first", 2500)
            return
        provider = self.providers.providers.get(plugin_id)
        if provider is None:
            return
        bundled = self.providers.is_bundled_provider(plugin_id)
        details = (
            " The bundled copy will stay removed until you choose Restore bundled sources."
            if bundled
            else ""
        )
        answer = QMessageBox.question(
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
            self.refresh()
            self._status(f"Removed {provider.info.name}", 3000)

    def restore_bundled_sources(self) -> None:
        if not self._optional_integrations_ready():
            return
        restored = self.providers.restore_bundled_providers()
        self.refresh()
        message = (
            f"Restored {len(restored)} bundled source(s)."
            if restored
            else "Bundled sources are already installed."
        )
        QMessageBox.information(self, "Bundled sources", message)

    def _stream_prompt(
        self,
        existing: dict[str, Any] | None = None,
    ) -> dict[str, str] | None:
        current = existing or {}
        name, ok = QInputDialog.getText(
            self,
            "User Stream",
            "Name:",
            text=str(current.get("name") or ""),
        )
        if not ok:
            return None
        url, ok = QInputDialog.getText(
            self,
            "User Stream",
            "HTTP(S) stream URL:",
            text=str(current.get("url") or ""),
        )
        if not ok:
            return None
        genre, ok = QInputDialog.getText(
            self,
            "User Stream",
            "Genre (optional):",
            text=str(current.get("genre") or ""),
        )
        if not ok:
            return None
        return {
            "name": name.strip() or "Untitled stream",
            "url": url.strip(),
            "genre": genre.strip(),
            "description": str(current.get("description") or ""),
        }

    def show_streams_dialog(self) -> None:
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

        def refresh_rows() -> None:
            rows.clear()
            for entry in self.providers.user_streams():
                detail = entry.get("genre") or entry.get("url") or ""
                item = QListWidgetItem(
                    f"{entry.get('name', 'Untitled stream')}\n{detail}"
                )
                item.setData(Qt.UserRole, entry)
                rows.addItem(item)

        def add_url() -> None:
            values = self._stream_prompt()
            if not values:
                return
            try:
                self.providers.add_user_stream(**values)
                refresh_rows()
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(dialog, "Could not add stream", str(exc))

        def edit_selected() -> None:
            current = rows.currentItem()
            if not current:
                return
            entry = dict(current.data(Qt.UserRole) or {})
            values = self._stream_prompt(entry)
            if not values:
                return
            try:
                self.providers.update_user_stream(
                    str(entry.get("id") or ""),
                    **values,
                )
                refresh_rows()
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(dialog, "Could not update stream", str(exc))

        def import_playlist() -> None:
            filename, _ = QFileDialog.getOpenFileName(
                dialog,
                "Import stream playlist",
                filter="Stream playlists (*.m3u *.m3u8 *.pls)",
            )
            if not filename:
                return
            try:
                added = self.providers.import_user_stream_playlist(Path(filename))
                refresh_rows()
                self.refresh()
                QMessageBox.information(
                    dialog,
                    "Playlist imported",
                    f"Added {len(added)} new stream(s).",
                )
            except Exception as exc:
                QMessageBox.critical(dialog, "Could not import playlist", str(exc))

        def remove_selected() -> None:
            current = rows.currentItem()
            if not current:
                return
            entry = dict(current.data(Qt.UserRole) or {})
            if (
                QMessageBox.question(
                    dialog,
                    "Remove stream",
                    f"Remove {entry.get('name', 'this stream')}?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                != QMessageBox.Yes
            ):
                return
            self.providers.remove_user_stream(str(entry.get("id") or ""))
            refresh_rows()
            self.refresh()

        buttons = QHBoxLayout()
        add_button = QPushButton("Add URL")
        add_button.clicked.connect(add_url)
        edit_button = QPushButton("Edit")
        edit_button.clicked.connect(edit_selected)
        import_button = QPushButton("Import playlist")
        import_button.clicked.connect(import_playlist)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(remove_selected)
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        for button in (add_button, edit_button, import_button, remove_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        rows.itemDoubleClicked.connect(lambda _item: edit_selected())
        refresh_rows()
        dialog.exec()
