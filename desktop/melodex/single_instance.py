from __future__ import annotations

import hashlib
import time
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def instance_server_name(data_dir: Path) -> str:
    digest = hashlib.sha256(str(Path(data_dir).resolve()).encode("utf-8")).hexdigest()[:16]
    return f"melodex-{digest}"


class SingleInstanceGuard(QObject):
    """Cross-platform single-GUI-instance guard with activation messaging."""

    activationRequested = Signal()

    def __init__(self, data_dir: Path, parent: QObject | None = None):
        super().__init__(parent)
        self.data_dir = Path(data_dir)
        self.name = instance_server_name(self.data_dir)
        self.lock = QLockFile(str(self.data_dir / "melodex-instance.lock"))
        self.lock.setStaleLockTime(30_000)
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._accept_connections)
        self._owned = False

    def acquire(self) -> bool:
        """Return True only for the process that owns the GUI instance."""

        if self.lock.tryLock(0):
            self._owned = True
            return self._listen()

        # QLockFile can safely decide whether the recorded PID is stale. Do not
        # remove a live process's socket merely because it has not started
        # listening yet.
        if self.lock.removeStaleLockFile() and self.lock.tryLock(0):
            self._owned = True
            return self._listen()

        self.notify_existing()
        return False

    def _listen(self) -> bool:
        # Holding the lock proves there is no other live Melodex GUI owner, so
        # removing a leftover local-server endpoint here is safe.
        QLocalServer.removeServer(self.name)
        if self.server.listen(self.name):
            return True
        self.lock.unlock()
        self._owned = False
        return False

    def notify_existing(self, attempts: int = 5, timeout_ms: int = 180) -> bool:
        for attempt in range(max(1, int(attempts))):
            socket = QLocalSocket()
            socket.connectToServer(self.name)
            if socket.waitForConnected(max(20, int(timeout_ms))):
                socket.write(b"activate\n")
                socket.flush()
                socket.waitForBytesWritten(max(20, int(timeout_ms)))
                socket.disconnectFromServer()
                return True
            if attempt + 1 < attempts:
                time.sleep(0.08)
        return False

    def _accept_connections(self) -> None:
        received = False
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is None:
                continue
            socket.waitForReadyRead(40)
            socket.readAll()
            socket.disconnectFromServer()
            received = True
        if received:
            self.activationRequested.emit()

    def release(self) -> None:
        if self.server.isListening():
            self.server.close()
        if self._owned:
            self.lock.unlock()
            self._owned = False


__all__ = ["SingleInstanceGuard", "instance_server_name"]
