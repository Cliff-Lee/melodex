from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageConcurrencyDecision:
    metadata_workers: int
    in_flight_limit: int
    profile: str
    average_stat_ms: float
    network_hint: bool


class StorageConcurrencyController:
    """Conservative adaptive concurrency for library scanning.

    The scanner keeps a small fixed executor, while this controller limits how
    many metadata reads may be in flight. It adapts from observed filesystem
    stat latency and path hints rather than assuming every library lives on a
    fast local SSD.
    """

    def __init__(
        self,
        roots: list[Path],
        *,
        min_workers: int = 2,
        max_workers: int = 8,
        sample_window: int = 64,
    ) -> None:
        self.min_workers = max(1, int(min_workers))
        self.max_workers = max(self.min_workers, int(max_workers))
        self.sample_window = max(8, int(sample_window))
        self.network_hint = any(self._looks_networkish(root) for root in roots)
        self._samples_ms: list[float] = []

    @staticmethod
    def _looks_networkish(path: Path) -> bool:
        value = str(path)
        if value.startswith("\\"):
            return True
        norm = value.replace("\\", "/")
        if norm.startswith("/Volumes/"):
            return True
        if norm.startswith("/net/") or norm.startswith("/network/"):
            return True
        return False

    def observe_stat(self, elapsed_seconds: float) -> None:
        value = max(0.0, float(elapsed_seconds)) * 1000.0
        self._samples_ms.append(value)
        if len(self._samples_ms) > self.sample_window:
            del self._samples_ms[:-self.sample_window]

    @property
    def average_stat_ms(self) -> float:
        if not self._samples_ms:
            return 0.0
        return sum(self._samples_ms) / len(self._samples_ms)

    def decision(self) -> StorageConcurrencyDecision:
        avg = self.average_stat_ms

        # Start conservatively, then spend more of the existing bounded
        # in-flight budget only when filesystem evidence says the storage is
        # fast. A likely NAS never scales as aggressively as local storage.
        if self.network_hint:
            workers = 2
            profile = "network-conservative"
            if len(self._samples_ms) >= 16 and avg < 1.5:
                workers = 4
                profile = "network-fast"
        elif len(self._samples_ms) < 16:
            workers = 2
            profile = "warming"
        elif avg >= 8.0:
            workers = 2
            profile = "high-latency"
        elif avg >= 2.0:
            workers = 4
            profile = "medium-latency"
        else:
            workers = 8
            profile = "low-latency"

        workers = min(self.max_workers, max(self.min_workers, workers))
        return StorageConcurrencyDecision(
            metadata_workers=workers,
            # P10/P14 keep the permanent hard cap at eight outstanding
            # metadata jobs. More workers improve cold-import throughput on
            # fast storage without allowing an unbounded read-ahead queue.
            in_flight_limit=min(8, max(workers, workers * 2)),
            profile=profile,
            average_stat_ms=round(avg, 3),
            network_hint=self.network_hint,
        )


__all__ = ["StorageConcurrencyController", "StorageConcurrencyDecision"]
