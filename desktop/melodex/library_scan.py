from __future__ import annotations

import threading
import time


class ScanCancelled(RuntimeError):
    """Raised cooperatively when a library scan has been cancelled."""


class ScanControl:
    """Thread-safe pause/cancel control for one library scan."""

    def __init__(self) -> None:
        self._cancelled = threading.Event()
        self._paused = threading.Event()

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    @property
    def paused(self) -> bool:
        return self._paused.is_set() and not self._cancelled.is_set()

    def pause(self) -> None:
        if not self._cancelled.is_set():
            self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def cancel(self) -> None:
        self._cancelled.set()
        # Release a paused worker so it can observe cancellation immediately.
        self._paused.clear()

    def checkpoint(self, poll_seconds: float = 0.05) -> None:
        if self._cancelled.is_set():
            raise ScanCancelled("Library scan cancelled")
        while self._paused.is_set():
            if self._cancelled.wait(max(0.005, float(poll_seconds))):
                raise ScanCancelled("Library scan cancelled")
        if self._cancelled.is_set():
            raise ScanCancelled("Library scan cancelled")


class ProgressThrottle:
    """Limit high-frequency worker progress signals without hiding phase changes."""

    def __init__(self, interval_seconds: float = 0.08) -> None:
        self.interval_seconds = max(0.0, float(interval_seconds))
        self._last = 0.0

    def ready(self, *, force: bool = False) -> bool:
        now = time.monotonic()
        if force or now - self._last >= self.interval_seconds:
            self._last = now
            return True
        return False


__all__ = ["ProgressThrottle", "ScanCancelled", "ScanControl"]
