from __future__ import annotations


def test_window_state_event_during_geometry_restore_does_not_crash(
    monkeypatch, tmp_path,
):
    """A macOS state-change callback can arrive before PlaybackFeature exists."""
    import pytest

    try:
        from PySide6.QtCore import QEvent, QSettings
        from PySide6.QtWidgets import QApplication
        import melodex.main_window as main_window
    except ImportError as exc:
        pytest.skip(f"Qt desktop runtime unavailable: {exc}")

    app = QApplication.instance() or QApplication([])
    settings = QSettings("Melodex", "Melodex")
    settings.clear()
    settings.setValue("window/geometry", b"trigger-restore")
    monkeypatch.setattr(main_window, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(main_window.MainWindow, "_start_local_bridge", lambda self: None)

    events_seen = []

    def restore_geometry_with_early_event(self, geometry):
        assert not hasattr(self, "playback_feature")
        events_seen.append(True)
        self.changeEvent(QEvent(QEvent.WindowStateChange))
        return False

    monkeypatch.setattr(
        main_window.MainWindow, "restoreGeometry", restore_geometry_with_early_event
    )

    try:
        window = main_window.MainWindow()
        assert events_seen, "The regression scenario did not run"
        assert window.playback_feature is not None
        window.close()
        app.processEvents()
    finally:
        settings.clear()
