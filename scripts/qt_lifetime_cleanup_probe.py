"""Diagnostic-only deterministic Qt teardown before PySide's atexit cleanup.

Tests a hypothesis; NOT production or a waiver of native exit-code failures.
"""
_qt_app = None


def pytest_sessionstart(session):
    global _qt_app
    from PySide6.QtWidgets import QApplication

    _qt_app = QApplication.instance() or QApplication([])


def pytest_sessionfinish(session, exitstatus):
    global _qt_app
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    app = _qt_app or QApplication.instance()
    if app is None:
        return

    # Ensure widgets and their deferred signal/timer events are destroyed
    # while Python, the Qt event machinery and the application are all alive.
    QApplication.closeAllWindows()
    for widget in list(QApplication.topLevelWidgets()):
        widget.close()
        widget.deleteLater()
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()

    app.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    _qt_app = None
