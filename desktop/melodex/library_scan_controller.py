from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Sequence

from PySide6.QtCore import QObject, Signal

from .library_scan_status import scan_roots_key


class LibraryScanController(QObject):
    """Own the disposable local-library scan worker lifecycle.

    The worker process remains lazy-imported so startup does not pull the scan
    implementation into the cold import graph. UI state and provider snapshot
    application stay with MainWindow for now.
    """

    progress = Signal(int, object)
    done = Signal(int, object)
    failed = Signal(int, str)

    def __init__(
        self,
        data_dir: Path,
        parent: QObject | None = None,
        *,
        runner_factory: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.data_dir = Path(data_dir)
        self._runner_factory = runner_factory
        self._runner: Any | None = None
        self._sequence = 0
        self._pending = False
        self._roots_key: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return self._runner is not None

    @property
    def pending(self) -> bool:
        return self._pending

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def runner(self) -> Any | None:
        return self._runner

    @property
    def roots_key(self) -> tuple[str, ...]:
        return self._roots_key

    @property
    def paused(self) -> bool:
        return bool(self._runner is not None and self._runner.paused)

    def is_current(self, sequence: int) -> bool:
        return int(sequence) == self._sequence

    def queue_rescan(self, roots: Sequence[Path]) -> bool:
        """Queue another pass and cancel the current worker if roots changed."""
        runner = self._runner
        if runner is None:
            return False
        self._pending = True
        roots_changed = scan_roots_key(list(roots)) != scan_roots_key(runner.roots)
        if roots_changed:
            runner.cancel()
        return roots_changed

    def clear_pending(self) -> None:
        self._pending = False

    def take_pending(self) -> bool:
        pending = self._pending
        self._pending = False
        return pending

    def _new_runner(self, roots: list[Path], sequence: int) -> Any:
        factory = self._runner_factory
        if factory is None:
            from .library_scan_process import LibraryScanProcess

            factory = LibraryScanProcess
        return factory(
            self.data_dir,
            roots,
            on_progress=lambda payload: self.progress.emit(sequence, payload),
            on_done=lambda result: self.done.emit(sequence, result),
            on_error=lambda error: self.failed.emit(sequence, str(error)),
        )

    def start(self, roots: Sequence[Path]) -> int:
        if self._runner is not None:
            raise RuntimeError("Library scan is already running")
        roots_snapshot = [Path(root) for root in roots]
        self._pending = False
        self._roots_key = scan_roots_key(roots_snapshot)
        self._sequence += 1
        sequence = self._sequence
        runner = self._new_runner(roots_snapshot, sequence)
        self._runner = runner
        try:
            runner.start()
        except Exception:
            self._runner = None
            raise
        return sequence

    def finish(self, sequence: int) -> bool:
        if not self.is_current(sequence):
            return False
        self._runner = None
        return True

    def toggle_pause(self) -> bool | None:
        runner = self._runner
        if runner is None:
            return None
        if runner.paused:
            runner.resume()
            return False
        runner.pause()
        return True

    def cancel(self, *, clear_pending: bool = False) -> bool:
        runner = self._runner
        if runner is None:
            return False
        if clear_pending:
            self._pending = False
        runner.cancel()
        return True

    def shutdown(self) -> None:
        runner = self._runner
        self._pending = False
        if runner is None:
            return
        runner.shutdown()
        self._runner = None
