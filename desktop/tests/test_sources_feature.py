from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from melodex.source_policy_controller import (
    SourcePolicyController,
    SourceSelectionPresentation,
)


class FakeUserState:
    def __init__(self):
        self.values = {}

    def get_bool(self, key, default=False):
        return bool(self.values.get(key, default))

    def set_bool(self, key, value):
        self.values[key] = bool(value)


class FakePluginConfig:
    def __init__(self):
        self.statuses = {
            "needs-setup": {"ready": False},
            "searchable": {"ready": True},
        }
        self.checked = []

    def cached_status(self, plugin_id, _configuration):
        return dict(self.statuses.get(plugin_id, {"ready": True}))

    def status(self, plugin_id, declarations):
        self.checked.append(plugin_id)
        return {
            "declared": bool(declarations),
            "ready": True,
            "configured": {},
            "pending": False,
            "pending_required": [],
            "missing_required": [],
        }


def _provider(
    provider_id,
    name,
    *,
    capabilities=(),
    configuration=(),
    description="",
):
    return SimpleNamespace(
        info=SimpleNamespace(
            id=provider_id,
            name=name,
            capabilities=list(capabilities),
            configuration=list(configuration),
            description=description,
        )
    )


class FakeProviders:
    def __init__(self):
        self.settings = {"jamendo_client_id": ""}
        self.plugin_config = FakePluginConfig()
        self.providers = {
            "local": _provider("local", "Local Files"),
            "streams": _provider("streams", "My Streams"),
            "jamendo": _provider(
                "jamendo",
                "Jamendo",
                capabilities=("search",),
                configuration=({"key": "client_id"},),
            ),
            "bundled": _provider(
                "bundled",
                "Bundled Radio",
                capabilities=("search",),
                description="Bundled test source",
            ),
            "searchable": _provider(
                "searchable",
                "Searchable Source",
                capabilities=("search",),
                description="Installed searchable source",
            ),
            "needs-setup": _provider(
                "needs-setup",
                "Needs Setup",
                capabilities=("search",),
                configuration=({"key": "token"},),
            ),
        }
        self.health = {
            "bundled": {"status": "ready"},
            "searchable": {"status": "error"},
            "needs-setup": {"status": "untested"},
            "lyrics-ext": {"status": "ready"},
            "disabled-ext": {"status": "ready"},
        }
        self._extensions = [
            {
                "id": "lyrics-ext",
                "name": "Lyrics Helper",
                "enabled": True,
                "capabilities": ["lyrics"],
                "description": "Lyrics extension",
                "configuration_status": {"declared": False, "ready": True},
            },
            {
                "id": "disabled-ext",
                "name": "Disabled Artwork",
                "enabled": False,
                "capabilities": ["artwork"],
                "description": "Disabled artwork extension",
                "configuration_status": {"declared": False, "ready": True},
            },
        ]
        self.installed_paths = []
        self.removed_providers = []
        self.health_calls = []
        self.streams = [
            {"id": "stream-1", "name": "Test Radio", "url": "https://example.invalid/radio"}
        ]

    def provider_order(self):
        return ["local", "streams", "jamendo", "bundled", "searchable", "needs-setup"]

    def local_catalog(self):
        return [{"track_id": "a"}, {"track_id": "b"}]

    def user_streams(self):
        return [dict(row) for row in self.streams]

    def is_bundled_provider(self, provider_id):
        return provider_id == "bundled"

    def installation_record(self, plugin_id):
        if plugin_id == "searchable":
            return {"method": "registry"}
        if plugin_id in {"needs-setup", "lyrics-ext", "disabled-ext"}:
            return {"method": "manual"}
        return {"method": "bundled"}

    def plugin_health(self, plugin_id, cached_config=True):
        return dict(self.health.get(plugin_id, {"status": "untested"}))

    def extensions(self, cached_config=True):
        return [dict(row) for row in self._extensions]

    def quarantined_legacy_providers(self):
        return []

    def set_provider_order(self, order):
        self._order = list(order)

    def set_jamendo_client_id(self, value):
        self.settings["jamendo_client_id"] = str(value)

    def searchable_provider_ids(self):
        return ["searchable", "needs-setup"]

    def install_package(self, path):
        self.installed_paths.append(Path(path))
        return _provider("installed", "Installed Provider", capabilities=("search",))

    def install_extension(self, path):
        self.installed_paths.append(Path(path))
        return SimpleNamespace(
            id="installed-extension",
            name="Installed Extension",
            capabilities=["lyrics"],
        )

    def test_plugin_health(self, plugin_id, timeout=6.0):
        self.health_calls.append((plugin_id, timeout))
        return {
            "plugin_id": plugin_id,
            "name": self.providers.get(
                plugin_id,
                SimpleNamespace(info=SimpleNamespace(name=plugin_id)),
            ).info.name,
            "status": "ready",
            "message": "Ready",
        }

    def set_extension_enabled(self, extension_id, enabled):
        for row in self._extensions:
            if row["id"] == extension_id:
                row["enabled"] = bool(enabled)

    def remove_extension(self, extension_id):
        before = len(self._extensions)
        self._extensions = [row for row in self._extensions if row["id"] != extension_id]
        return len(self._extensions) != before

    def remove_provider(self, provider_id):
        self.removed_providers.append(provider_id)
        self.providers.pop(provider_id, None)
        return True

    def restore_bundled_providers(self):
        return []

    def add_user_stream(self, **values):
        self.streams.append({"id": f"stream-{len(self.streams)+1}", **values})

    def update_user_stream(self, stream_id, **values):
        for row in self.streams:
            if row["id"] == stream_id:
                row.update(values)

    def remove_user_stream(self, stream_id):
        self.streams = [row for row in self.streams if row["id"] != stream_id]

    def import_user_stream_playlist(self, _path):
        return []


def _feature():
    try:
        from PySide6.QtWidgets import QApplication
        from melodex.sources_feature import SourcesFeature
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    providers = FakeProviders()
    policy = SourcePolicyController(providers)
    state = FakeUserState()
    statuses = []

    def run_async(fn, done=None, failed=None, **_kwargs):
        try:
            result = fn()
        except Exception as exc:
            if failed is not None:
                failed(str(exc))
            return
        if done is not None:
            done(result)

    feature = SourcesFeature(
        providers,
        policy,
        state,
        run_async=run_async,
        diagnostics_metrics=lambda: {"test": True},
        is_active=lambda: True,
        power_tools_enabled=True,
    )
    feature.statusMessageRequested.connect(
        lambda message, timeout: statuses.append((message, timeout))
    )
    return app, feature, providers, policy, statuses


def _status_for(feature, source_id):
    from PySide6.QtWidgets import QLabel

    for row in range(feature.sources_list.count()):
        item = feature.sources_list.item(row)
        if str(item.data(0x0100) or "") != source_id:
            continue
        card = feature.sources_list.itemWidget(item)
        label = card.findChild(QLabel, "statusPill")
        return label.text() if label is not None else ""
    raise AssertionError(f"source not rendered: {source_id}")


def test_sources_feature_renders_providers_extensions_and_health():
    app, feature, _providers, _policy, _statuses = _feature()
    feature.refresh()
    app.processEvents()

    assert _status_for(feature, "local") == "2 tracks"
    assert _status_for(feature, "bundled") == "Ready"
    assert _status_for(feature, "searchable") == "Needs attention"
    assert _status_for(feature, "needs-setup") == "Setup needed"
    assert _status_for(feature, "extension:lyrics-ext") == "Ready"
    assert _status_for(feature, "extension:disabled-ext") == "Disabled"

    assert feature.select_source("needs-setup")
    assert feature.selected_source_id() == "needs-setup"
    assert feature.source_primary_button.text() == "Set up source"

    feature.deleteLater()
    app.processEvents()


def test_sources_feature_routes_primary_actions_through_policy(monkeypatch):
    app, feature, _providers, policy, _statuses = _feature()
    feature.refresh()

    music = []
    searches = []
    extensions = []
    streams = []
    configurations = []
    feature.musicFolderRequested.connect(lambda: music.append(True))
    feature.providerSearchRequested.connect(searches.append)
    feature.extensionUseRequested.connect(extensions.append)
    monkeypatch.setattr(feature, "show_streams_dialog", lambda: streams.append(True))
    monkeypatch.setattr(
        feature,
        "configure_selected_plugin",
        lambda: configurations.append(feature.selected_source_id()),
    )

    feature.select_source("local")
    feature._run_primary_action()
    feature.select_source("streams")
    feature._run_primary_action()
    feature.select_source("searchable")
    feature._run_primary_action()
    feature.select_source("extension:lyrics-ext")
    feature._run_primary_action()
    feature.select_source("needs-setup")
    feature._run_primary_action()

    assert music == [True]
    assert streams == [True]
    assert searches == ["searchable"]
    assert extensions == ["lyrics-ext"]
    assert configurations == ["needs-setup"]

    monkeypatch.setattr(
        policy,
        "selection_presentation",
        lambda _key: SourceSelectionPresentation("Policy owns this", "Policy hint"),
    )
    feature.select_source("local")
    assert feature.source_primary_button.text() == "Policy owns this"
    assert feature.source_hint.text() == "Policy hint"

    feature.deleteLater()
    app.processEvents()


def test_sources_feature_owns_install_remove_and_health_workflows(monkeypatch, tmp_path):
    try:
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import melodex.plugin_onboarding as plugin_onboarding
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app, feature, providers, _policy, statuses = _feature()
    feature.refresh()

    package = tmp_path / "test.mdxprovider"
    package.write_text("test", encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(package), "Melodex Provider"),
    )
    monkeypatch.setattr(plugin_onboarding, "plugin_needs_setup", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

    feature.install_provider()
    assert providers.installed_paths == [package]

    assert feature.select_source("searchable")
    feature.test_selected_plugin()
    assert providers.health_calls[-1][0] == "searchable"
    assert any("Ready" in message for message, _timeout in statuses)

    feature.remove_provider()
    assert providers.removed_providers == ["searchable"]

    feature.deleteLater()
    app.processEvents()


def test_sources_feature_config_refresh_updates_owned_state():
    app, feature, providers, _policy, _statuses = _feature()
    feature.refresh()

    assert feature.config_refresh_in_progress is False
    feature.refresh_config_statuses_async()
    assert feature.config_refresh_in_progress is False
    assert "needs-setup" in providers.plugin_config.checked

    feature.deleteLater()
    app.processEvents()
