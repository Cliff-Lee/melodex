from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator


@dataclass
class ScanMetrics:
    started_at: str
    thread_name: str
    main_thread: bool
    root_count: int
    roots_checked: int = 0
    roots_missing: int = 0
    directories_seen: int = 0
    files_seen: int = 0
    audio_files_seen: int = 0
    metadata_attempts: int = 0
    metadata_seconds: float = 0.0
    metadata_work_seconds: float = 0.0
    total_seconds: float = 0.0
    tracks_indexed: int = 0

    def as_dict(self) -> dict[str, object]:
        """Return path-free scan telemetry suitable for support diagnostics."""
        non_metadata = max(0.0, self.total_seconds - self.metadata_seconds)
        return {
            "started_at": self.started_at,
            "thread_name": self.thread_name,
            "main_thread": self.main_thread,
            "root_count": self.root_count,
            "roots_checked": self.roots_checked,
            "roots_missing": self.roots_missing,
            "directories_seen": self.directories_seen,
            "files_seen": self.files_seen,
            "audio_files_seen": self.audio_files_seen,
            "metadata_attempts": self.metadata_attempts,
            "metadata_seconds": round(self.metadata_seconds, 6),
            "metadata_work_seconds": round(self.metadata_work_seconds, 6),
            "non_metadata_seconds": round(non_metadata, 6),
            "total_seconds": round(self.total_seconds, 6),
            "tracks_indexed": self.tracks_indexed,
        }


class ScanProbe:
    """Low-overhead measurements for the existing synchronous library scanner.

    The probe deliberately records counts and timings only. It never stores root,
    directory or file names, so the snapshot can be included in redacted support
    diagnostics without exposing a listener's library layout.
    """

    def __init__(self, root_count: int):
        current = threading.current_thread()
        self.metrics = ScanMetrics(
            started_at=datetime.now(timezone.utc).isoformat(),
            thread_name=current.name,
            main_thread=current is threading.main_thread(),
            root_count=max(0, int(root_count)),
        )
        self._started = time.perf_counter()
        self._finished = False

    def root_checked(self, *, exists: bool) -> None:
        self.metrics.roots_checked += 1
        if not exists:
            self.metrics.roots_missing += 1

    def directory_seen(self) -> None:
        self.metrics.directories_seen += 1

    def file_seen(self, *, audio: bool) -> None:
        self.metrics.files_seen += 1
        if audio:
            self.metrics.audio_files_seen += 1

    @contextmanager
    def metadata_read(self) -> Iterator[None]:
        self.metrics.metadata_attempts += 1
        started = time.perf_counter()
        try:
            yield
        finally:
            self.metrics.metadata_seconds += max(0.0, time.perf_counter() - started)

    def metadata_submitted(self) -> None:
        self.metrics.metadata_attempts += 1

    def record_metadata_result(self, elapsed_seconds: float) -> None:
        self.metrics.metadata_work_seconds += max(
            0.0,
            float(elapsed_seconds),
        )

    def finish(self, *, tracks_indexed: int) -> dict[str, object]:
        if not self._finished:
            self.metrics.total_seconds = max(0.0, time.perf_counter() - self._started)
            self.metrics.tracks_indexed = max(0, int(tracks_indexed))
            self._finished = True
        return self.metrics.as_dict()


__all__ = ["ScanMetrics", "ScanProbe"]
