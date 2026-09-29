from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .paths import app_data_dir
from .single_instance import SingleInstanceGuard


def _activate_window(win: MainWindow) -> None:
    if win.isMinimized():
        win.showNormal()
    else:
        win.show()
    win.raise_()
    win.activateWindow()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Melodex")
    app.setOrganizationName("Melodex")

    guard = SingleInstanceGuard(app_data_dir())
    if not guard.acquire():
        # A live Melodex GUI already owns the lock. acquire() asks it to raise
        # its existing window, so this process should exit without constructing
        # providers, plugins, databases, playback or a second MainWindow.
        return 0

    icon_path = Path(__file__).resolve().parent / "assets" / "melodex-mark.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    win = MainWindow()
    guard.activationRequested.connect(lambda: _activate_window(win))
    app.aboutToQuit.connect(guard.release)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
