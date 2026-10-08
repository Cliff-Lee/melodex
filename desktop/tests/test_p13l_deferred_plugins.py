from __future__ import annotations

import threading
from pathlib import Path

from melodex import capabilities, provider_manager
from melodex.provider import ProviderInstaller
from melodex.provider_manager import ProviderManager


def test_deferred_provider_manager_skips_optional_plugin_discovery(
    tmp_path: Path, monkeypatch
) -> None:
    def unexpected(*_args, **_kwargs):
        raise AssertionError("optional plugin discovery ran during construction")

    monkeypatch.setattr(provider_manager, "ensure_bundled_providers", unexpected)
    monkeypatch.setattr(ProviderInstaller, "load_installed", unexpected)
    monkeypatch.setattr(capabilities.ExtensionInstaller, "load_installed", unexpected)

    manager = ProviderManager(tmp_path / "data", defer_optional_plugins=True)

    assert set(manager.providers) == {"local", "jamendo", "streams"}
    assert manager.optional_plugins_loaded is False
    assert manager.capabilities.extensions == {}
    assert manager.capabilities._installed_loaded is False
    manager.close()


def test_optional_plugin_snapshot_applies_after_shell_initialization(
    tmp_path: Path,
) -> None:
    manager = ProviderManager(tmp_path / "data", defer_optional_plugins=True)

    manager.apply_optional_plugins_snapshot(
        {
            "bundled_ids": {"org.melodex.test"},
            "providers": {},
            "extensions": [],
            "quarantined": [{"id": "legacy", "name": "Legacy"}],
            "superseded": [],
        }
    )

    assert manager.optional_plugins_loaded is True
    assert manager.capabilities._installed_loaded is True
    assert manager.is_bundled_provider("org.melodex.test")
    assert manager.quarantined_legacy_providers() == [
        {"id": "legacy", "name": "Legacy"}
    ]
    manager.close()


def test_main_window_builds_player_before_optional_package_discovery(
    tmp_path: Path, monkeypatch
) -> None:
    try:
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        import pytest

        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)

    synchronous_loads: list[bool] = []

    def load_optional_plugins(self):
        synchronous_loads.append(
            threading.current_thread() is threading.main_thread()
        )
        return {
            "bundled_ids": set(),
            "providers": {},
            "extensions": [],
            "quarantined": [],
            "superseded": [],
        }

    monkeypatch.setattr(
        ProviderManager,
        "load_optional_plugins_snapshot",
        load_optional_plugins,
    )
    window = main_window.MainWindow()
    try:
        assert window.player is not None
        assert window.providers.optional_plugins_loaded is False
        assert synchronous_loads == []
        window.show()
        app.processEvents()
        assert window.isVisible()
    finally:
        window.close()
        app.processEvents()
