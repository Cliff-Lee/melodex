"""Test-only hypothesis: retain one QApplication Python wrapper for full pytest session.

Does not suppress warnings, monkeypatch Qt, waive a test, or change production.
Loaded only by qt_lifetime_isolation.py --pin-app as a pytest -p plugin.
"""
_qt_app = None


def pytest_sessionstart(session):
    global _qt_app
    from PySide6.QtWidgets import QApplication
    _qt_app = QApplication.instance() or QApplication([])
