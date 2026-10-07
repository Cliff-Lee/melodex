from __future__ import annotations

import threading
import time
import os
from collections import deque
from pathlib import Path


class ScanCancelled(RuntimeError):
    """Raised cooperatively when a library scan has been cancelled."""


class ScanControl:
    """Thread-safe pause/cancel control for one library scan."""

    def __init__(self) -> None:
        self._cancelled = threading.Event()
        self._paused = threading.Event()
        self._priority_lock = threading.Lock()
        self._priority_paths: deque[str] = deque()
        self._priority_keys: set[str] = set()
        self._priority_capacity = 32

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

    def prioritize(self, path: str | Path) -> bool:
        """Move a directory ahead of background traversal, bounded to 32 paths."""
        value = os.path.abspath(os.path.expanduser(str(path or "")))
        if not value or self._cancelled.is_set():
            return False
        key = os.path.normcase(value)
        with self._priority_lock:
            if key in self._priority_keys:
                self._priority_paths = deque(
                    item for item in self._priority_paths
                    if os.path.normcase(item) != key
                )
            elif len(self._priority_paths) >= self._priority_capacity:
                removed = self._priority_paths.pop()
                self._priority_keys.discard(os.path.normcase(removed))
            self._priority_paths.appendleft(value)
            self._priority_keys.add(key)
        return True

    def take_priority_path(self, root: str | Path | None = None) -> str | None:
        root_key = (
            os.path.normcase(os.path.abspath(os.path.expanduser(str(root))))
            if root is not None
            else None
        )
        with self._priority_lock:
            selected_index = None
            for index, value in enumerate(self._priority_paths):
                if root_key is None:
                    selected_index = index
                    break
                candidate = os.path.normcase(os.path.abspath(value))
                try:
                    if os.path.commonpath((root_key, candidate)) == root_key:
                        selected_index = index
                        break
                except ValueError:
                    continue
            if selected_index is None:
                return None
            value = self._priority_paths[selected_index]
            del self._priority_paths[selected_index]
            self._priority_keys.discard(os.path.normcase(value))
            return value

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
