from __future__ import annotations

import html
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
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QStyle,
    QVBoxLayout,
)


class _Signals(QObject):
    done = Signal(object)
    error = Signal(str)


class PluginDirectoryCard(QFrame):
    """Visual registry row for normal users; technical detail lives elsewhere."""

    def __init__(
        self,
        entry: dict[str, Any],
        badge: str,
        *,
        installed: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("pluginDirectoryCard")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row=QHBoxLayout(self)
        row.setContentsMargins(12,10,12,10)
        row.setSpacing(11)

        capabilities=[str(x) for x in list(entry.get("capabilities") or []) if x]
        capability=capabilities[0] if capabilities else ""
        icon_map={
            "lyrics":QStyle.SP_FileIcon,
            "artwork":QStyle.SP_FileDialogContentsView,
            "metadata":QStyle.SP_FileDialogDetailedView,
            "identity":QStyle.SP_FileDialogInfoView,
            "context":QStyle.SP_MessageBoxInformation,
            "library_suggestions":QStyle.SP_BrowserReload,
            "recommendations":QStyle.SP_BrowserReload,
            "search":QStyle.SP_DriveNetIcon,
            "playback":QStyle.SP_MediaPlay,
        }
        icon_label=QLabel()
        icon_label.setObjectName("pluginDirectoryIcon")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(44,44)
        icon= self.style().standardIcon(icon_map.get(capability,QStyle.SP_CommandLink))
        icon_label.setPixmap(icon.pixmap(25,25))
        row.addWidget(icon_label)

        text=QVBoxLayout()
        text.setSpacing(3)
        title_row=QHBoxLayout()
        title_row.setSpacing(7)
        title=QLabel(str(entry.get("name") or entry.get("id") or "Plugin"))
        title.setObjectName("pluginDirectoryTitle")
        title_row.addWidget(title)
        status=str(entry.get("status") or "").casefold()
        type_label="Reference" if status=="example" else "Community" if status=="community" else "Reviewed" if status=="reviewed" else status.title()
        if type_label:
            pill=QLabel(type_label)
            pill.setObjectName("pluginDirectoryType")
            title_row.addWidget(pill)
        title_row.addStretch(1)
        text.addLayout(title_row)

        desc=QLabel(str(entry.get("description") or ""))
        desc.setObjectName("pluginDirectoryDescription")
        desc.setWordWrap(True)
        text.addWidget(desc)

        human_caps=[]
        for value in capabilities[:3]:
            human_caps.append({
                "library_suggestions":"recommendations",
                "identity":"track matching",
                "metadata":"metadata",
                "artwork":"artwork",
                "lyrics":"lyrics",
                "context":"context",
                "search":"search",
                "playback":"playback",
                "offline":"offline",
                "recommendations":"recommendations",
            }.get(value,value.replace("_"," ")))
        meta=QLabel(" · ".join(human_caps))
        meta.setObjectName("pluginDirectoryMeta")
        text.addWidget(meta)
        row.addLayout(text,1)

        state=QLabel(str(badge or ("Installed" if installed else "Optional")))
        state.setObjectName("statusPill")
        row.addWidget(state)


class PluginDirectoryDialog(QDialog):
    def __init__(
        self,
        provider_manager,
        on_installed: Callable[[], None] | None = None,
        on_use: Callable[[dict[str, Any]], None] | None = None,
        initial_capability: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.manager = provider_manager
        self.on_installed = on_installed
        self.on_use = on_use
        self.initial_capability = str(initial_capability or "")
        self.plugins: list[dict[str, Any]] = []
        self._signals: list[_Signals] = []

        self.setWindowTitle("Melodex Plugin Centre")
        self.resize(1080, 720)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18,18,18,16)
        layout.setSpacing(12)

        hero=QFrame()
        hero.setObjectName("pluginCentreHero")
        hero_l=QHBoxLayout(hero)
        hero_l.setContentsMargins(16,14,16,14)
        hero_l.setSpacing(12)
        hero_icon=QLabel()
        hero_icon.setObjectName("pluginCentreHeroIcon")
        hero_icon.setAlignment(Qt.AlignCenter)
        hero_icon.setFixedSize(46,46)
        hero_icon.setPixmap(self.style().standardIcon(QStyle.SP_CommandLink).pixmap(27,27))
        hero_l.addWidget(hero_icon)
        hero_text=QVBoxLayout()
        hero_text.setSpacing(2)
        hero_title=QLabel("Add capabilities, not clutter")
        hero_title.setStyleSheet("font-size:18px;font-weight:720")
        hero_text.addWidget(hero_title)
        intro = QLabel(
            "Music sources find things to play. Enhancements add artwork, lyrics, metadata, context or smarter local recommendations. "
            "Nothing here is required for ordinary local playback."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#9da8b8")
        hero_text.addWidget(intro)
        hero_l.addLayout(hero_text,1)
        layout.addWidget(hero)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search optional plugins…")
        self.kind = QComboBox()
        self.kind.addItem("Everything", "all")
        self.kind.addItem("Music sources", "provider")
        self.kind.addItem("Enhancements", "enrichment")
        self.kind.addItem("Local intelligence", "tool")
        self.capability = QComboBox()
        self.capability.addItem("Any feature", "all")
        for label,value in (
            ("Search & playback","search"),
            ("Recommendations","recommendations"),
            ("Track matching","identity"),
            ("Metadata","metadata"),
            ("Artwork","artwork"),
            ("Lyrics","lyrics"),
            ("Context","context"),
            ("Local suggestions","library_suggestions"),
        ):
            self.capability.addItem(label, value)
        self.refresh_button = QPushButton("Refresh")
        filters.addWidget(self.search, 1)
        filters.addWidget(self.kind)
        filters.addWidget(self.capability)
        filters.addWidget(self.refresh_button)
        layout.addLayout(filters)

        self.status = QLabel("Loading plugin catalogue…")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#8996a8")
        layout.addWidget(self.status)

        body = QHBoxLayout()
        body.setSpacing(14)
        self.rows = QListWidget()
        self.rows.setObjectName("pluginDirectoryList")
        self.rows.setMinimumWidth(500)
        self.rows.setSpacing(5)
        body.addWidget(self.rows, 3)

        detail_panel=QFrame()
        detail_panel.setObjectName("pluginDetailPanel")
        detail_l=QVBoxLayout(detail_panel)
        detail_l.setContentsMargins(16,15,16,15)
        detail_l.setSpacing(9)
        self.details = QTextBrowser()
        self.details.setObjectName("pluginDetails")
        self.details.setOpenExternalLinks(True)
        detail_l.addWidget(self.details,1)

        self.tech_button=QPushButton("Technical details")
        self.tech_button.setCheckable(True)
        self.tech_button.setObjectName("quietButton")
        detail_l.addWidget(self.tech_button)
        self.tech_details=QTextBrowser()
        self.tech_details.setObjectName("pluginTechnicalDetails")
        self.tech_details.setOpenExternalLinks(True)
        self.tech_details.setMaximumHeight(210)
        self.tech_details.hide()
        detail_l.addWidget(self.tech_details)
        self.tech_button.toggled.connect(self.tech_details.setVisible)
        body.addWidget(detail_panel,2)
        layout.addLayout(body, 1)

        actions = QHBoxLayout()
        self.install_button = QPushButton("Install")
        self.install_button.setObjectName("primaryButton")
        self.use_button = QPushButton("Use plugin")
        self.configure_button = QPushButton("Configure…")
        self.test_button = QPushButton("Check connection")
        self.source_button = QPushButton("Source code")
        self.review_button = QPushButton("Review record")
        close_button = QPushButton("Close")
        self.install_button.setEnabled(False)
        self.use_button.setEnabled(False)
        self.configure_button.setEnabled(False)
        self.test_button.setEnabled(False)
        self.source_button.setEnabled(False)
        self.review_button.setEnabled(False)
        actions.addWidget(self.install_button)
        actions.addWidget(self.use_button)
        actions.addWidget(self.configure_button)
        actions.addWidget(self.test_button)
        actions.addStretch(1)
        actions.addWidget(self.source_button)
        actions.addWidget(self.review_button)
        actions.addWidget(close_button)
        layout.addLayout(actions)

        self.setStyleSheet(
            self.styleSheet()
            + """
            QFrame#pluginCentreHero{
                background:#121b26;border:1px solid #2b3c50;border-radius:14px;
            }
            QLabel#pluginCentreHeroIcon{
                background:#193354;border:1px solid #2f5d8f;border-radius:12px;
            }
            QListWidget#pluginDirectoryList{
                background:#0e141d;border:1px solid #263344;border-radius:12px;padding:6px;
            }
            QListWidget#pluginDirectoryList::item{
                background:transparent;border:0;padding:0;
            }
            QListWidget#pluginDirectoryList::item:selected{
                background:#18263a;border:1px solid #31547d;border-radius:10px;
            }
            QFrame#pluginDirectoryCard{background:transparent;border:0}
            QLabel#pluginDirectoryIcon{
                background:#19283b;border:1px solid #304c6c;border-radius:11px;
            }
            QLabel#pluginDirectoryTitle{font-size:14px;font-weight:700}
            QLabel#pluginDirectoryDescription{color:#8f9bad;font-size:11px}
            QLabel#pluginDirectoryMeta{color:#6fa8ed;font-size:10px}
            QLabel#pluginDirectoryType{
                color:#9aacbf;background:#17202c;border:1px solid #2a394b;
                border-radius:6px;padding:2px 5px;font-size:9px;
            }
            QFrame#pluginDetailPanel{
                background:#101720;border:1px solid #273548;border-radius:12px;
            }
            QTextBrowser#pluginDetails,QTextBrowser#pluginTechnicalDetails{
                background:transparent;border:0;color:#e6e9ee;
            }
            """
        )

        self.rows.currentItemChanged.connect(lambda *_: self._show_details())
        self.search.textChanged.connect(lambda *_: self._apply_filter())
        self.kind.currentIndexChanged.connect(lambda *_: self._apply_filter())
        self.capability.currentIndexChanged.connect(lambda *_: self._apply_filter())
        self.refresh_button.clicked.connect(lambda: self.load_registry(force=True))
        self.install_button.clicked.connect(self._install_selected)
        self.use_button.clicked.connect(self._use_selected)
        self.configure_button.clicked.connect(self._configure_selected)
        self.test_button.clicked.connect(self._test_selected)
        self.source_button.clicked.connect(self._open_source)
        self.review_button.clicked.connect(self._open_review)
        close_button.clicked.connect(self.accept)

        if self.initial_capability:
            index=self.capability.findData(self.initial_capability)
            if index >= 0:
                self.capability.setCurrentIndex(index)

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
            self.use_button.setEnabled(False)
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
            update_available = installed and self._update_available(entry)
            config_info = (
                plugin_configuration_info(self.manager, plugin_id)
                if installed
                else {}
            )
            config_state = configuration_state(config_info)
            health = self.manager.plugin_health(plugin_id) if installed else {}
            health_state = health_badge(health) if installed else ""
            badge = (
                "Update · setup"
                if update_available and config_state == "setup_needed"
                else "Update available"
                if update_available
                else "Setup needed"
                if installed and config_state == "setup_needed"
                else health_state.title()
                if installed and health_state
                else "Installed"
                if installed
                else "Optional"
            )
            item = QListWidgetItem()
            item.setData(Qt.UserRole, entry)
            card=PluginDirectoryCard(entry,badge,installed=installed)
            item.setSizeHint(card.sizeHint())
            self.rows.addItem(item)
            self.rows.setItemWidget(item,card)
        if self.rows.count():
            self.rows.setCurrentRow(0)
        else:
            self.details.setHtml(
                "<h3>No matching plugins</h3>"
                "<p style='color:#8f9bad'>Try clearing a filter or searching for a different feature.</p>"
            )
            self.tech_details.clear()
            self.install_button.setEnabled(False)
            self.use_button.setEnabled(False)
            self.configure_button.setEnabled(False)
            self.test_button.setEnabled(False)
            self.source_button.setEnabled(False)
            self.review_button.setEnabled(False)

    def _show_details(self) -> None:
        entry = self._selected()
        if not entry:
            self.details.clear()
            self.tech_details.clear()
            self.install_button.setEnabled(False)
            self.use_button.setEnabled(False)
            self.configure_button.setEnabled(False)
            self.test_button.setEnabled(False)
            self.source_button.setEnabled(False)
            self.review_button.setEnabled(False)
            return

        distribution = dict(entry.get("distribution") or {})
        source = dict(entry.get("source") or {})
        review = dict(entry.get("review") or {})
        capability_values=[str(x) for x in list(entry.get("capabilities") or []) if x]
        capability_labels=[
            {
                "search":"search music",
                "track":"track details",
                "playback":"play music",
                "offline":"offline downloads",
                "recommendations":"recommendations",
                "identity":"track matching",
                "metadata":"metadata",
                "artwork":"artwork",
                "lyrics":"lyrics",
                "context":"context",
                "library_suggestions":"local recommendations",
            }.get(value,value.replace("_"," "))
            for value in capability_values
        ]
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
        config_state=configuration_state(config_info) if installed else "not_installed"
        config_text = configuration_summary(config_info) if installed else "Not installed"
        health = self.manager.plugin_health(plugin_id) if installed else {}
        health_text = health_summary(health) if installed else "Not installed"
        compatible, compatibility_reason = self.manager.registry.compatibility(entry)
        sha256 = str(distribution.get("sha256") or "")

        status=str(entry.get("status") or "").casefold()
        if status=="example":
            trust_text=(
                "Reference plugin. It is included in the Melodex registry as an "
                "open example you can inspect, install and test; it is not preinstalled."
            )
        elif status=="reviewed":
            trust_text="Reviewed registry entry. Review records are available below."
        elif status=="community":
            trust_text="Community registry entry. Inspect permissions and source before installing."
        else:
            trust_text=f"Registry status: {status or 'unspecified'}."

        duplicate_note=""
        if plugin_id in {
            "org.melodex.example.radio-browser",
            "org.melodex.example.librivox",
        }:
            duplicate_note=(
                "<p style='color:#e0b66b'><b>Already included:</b> Melodex ships "
                "an audited bundled version of this source. Install this reference "
                "package only if you are testing the plugin ecosystem.</p>"
            )
        elif plugin_id in {
            "org.melodex.example.musicbrainz",
            "org.melodex.example.cover-art-archive",
            "org.melodex.example.wikimedia-commons",
        }:
            duplicate_note=(
                "<p style='color:#e0b66b'><b>Core already has related support:</b> "
                "this reference extension demonstrates how the same kind of capability "
                "can be supplied by a plugin.</p>"
            )
        elif plugin_id=="org.melodex.example.public-domain-lyrics":
            duplicate_note=(
                "<p style='color:#e0b66b'><b>Limited demo corpus:</b> this plugin "
                "contains a small public-domain lyrics catalogue for testing the Lyrics "
                "API. It is not a general modern-song lyrics service.</p>"
            )

        if installed:
            state=(
                "<span style='color:#7bd88f'><b>Installed</b></span>"
                if config_state!="setup_needed"
                else "<span style='color:#e0b66b'><b>Installed · setup needed</b></span>"
            )
            if update_available:
                state += " · <span style='color:#6fa8ed'>update available</span>"
        else:
            state="<span style='color:#8f9bad'><b>Optional · not installed</b></span>"

        permissions=list(entry.get("permissions") or [])
        if not permissions:
            permission_text="No extra permissions declared."
        else:
            friendly=[]
            for raw in permissions:
                value=str(raw)
                if value.startswith("network:"):
                    friendly.append("Internet access: "+value.split(":",1)[1])
                elif value=="offline_downloads":
                    friendly.append("May save supported media for offline use")
                else:
                    friendly.append(value.replace("_"," "))
            permission_text="<br>".join("• "+html.escape(x) for x in friendly)

        kind=str(entry.get("kind") or "")
        kind_name={
            "provider":"Music source",
            "enrichment":"Enhancement",
            "tool":"Local intelligence",
        }.get(kind,kind.title() or "Plugin")
        capabilities=", ".join(capability_labels) or "No user-facing capabilities listed"
        main_html=(
            f"<h2 style='margin-bottom:2px'>{html.escape(str(entry.get('name') or plugin_id))}</h2>"
            f"<p style='color:#6fa8ed;margin-top:0'>{html.escape(kind_name)} · "
            f"{html.escape(capabilities)}</p>"
            f"<p>{html.escape(str(entry.get('description') or ''))}</p>"
            f"{duplicate_note}"
            f"<p>{state}</p>"
            f"<h3>What it can do</h3>"
            f"<p>{html.escape(capabilities)}</p>"
            f"<h3>Access it requests</h3>"
            f"<p>{permission_text}</p>"
            f"<h3>About this plugin</h3>"
            f"<p>{html.escape(trust_text)}</p>"
            f"<p style='color:#8f9bad'>Publisher: "
            f"{html.escape(str(entry.get('publisher') or 'Not specified'))}<br>"
            f"Licence: {html.escape(str(entry.get('license') or 'Not specified'))}</p>"
        )
        self.details.setHtml(main_html)

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

        technical=(
            f"<b>Plugin ID</b><br>{html.escape(plugin_id)}<br><br>"
            f"<b>Version</b><br>{html.escape(str(entry.get('version') or ''))}<br><br>"
            f"<b>Installed version</b><br>{html.escape(installed_version or '—')}<br><br>"
            f"<b>Configuration</b><br>{html.escape(config_text)}<br><br>"
            f"<b>Health</b><br>{html.escape(health_text)}<br><br>"
            f"<b>Compatibility</b><br>{'Yes' if compatible else 'No'}"
            + (f" — {html.escape(compatibility_reason)}" if compatibility_reason else "")
            + "<br><br>"
            f"<b>Install origin</b><br>{html.escape(install_origin)}<br>"
            f"Installed at: {html.escape(installed_at)}<br>"
            f"Local package SHA-256: {html.escape(install_hash)}<br><br>"
            f"<b>Package</b><br>{html.escape(str(distribution.get('format') or '—'))}<br>"
            f"Size: {html.escape(str(distribution.get('size_bytes') or 'not supplied'))} bytes<br>"
            f"Registry SHA-256: {html.escape(sha256 or 'not supplied')}<br><br>"
            f"<b>Source policy</b><br>{html.escape(str(entry.get('source_policy') or 'not supplied'))}<br><br>"
            f"<b>Repository</b><br>{html.escape(str(source.get('repository') or 'not supplied'))}<br><br>"
            f"<b>Last registry review</b><br>{html.escape(str(review.get('last_reviewed_at') or 'not supplied'))}<br>"
            f"Review record: {html.escape(str(review.get('record') or 'not supplied'))}"
        )
        self.tech_details.setHtml(technical)

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
        ready = installed and config_state != "setup_needed"
        self.use_button.setEnabled(bool(ready and self.on_use))
        self.use_button.setText(
            "Use source"
            if kind == "provider"
            else "Use plugin"
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
                "Ready. Select it and choose Use plugin/source to open the feature where it is used."
                if ready
                else "Setup is still required; select it and choose Configure…."
            )
        )
        QMessageBox.information(
            self,
            "Plugin installed",
            f"Installed {name} successfully.\n\n"
            + (
                "Ready. Choose Use plugin/source in the directory, or close it and use the plugin from Sources & plugins."
                if ready
                else "Setup is still required before this plugin is ready."
            ),
        )

    def _use_selected(self) -> None:
        entry = self._selected()
        if not entry or not self._is_installed(entry) or not self.on_use:
            return
        self.accept()
        self.on_use(dict(entry))

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
