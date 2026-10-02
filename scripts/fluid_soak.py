from __future__ import annotations

import argparse
import gc
import json
import os
import statistics
import sys
import time
from concurrent.futures import CancelledError
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
SCRIPTS = ROOT / "scripts"
for path in (DESKTOP, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from large_library_probe import synthetic_catalog  # noqa: E402
from melodex.background_scheduler import (  # noqa: E402
    BackgroundScheduler,
    StaleTaskError,
)


DEFAULT_BUDGETS = {
    "max_ci_violations": 0,
    "max_serious_stalls": 0,
    "max_release_blockers": 0,
    "max_rss_growth_mib": 128.0,
    "max_gc_object_growth": 5000,
    "max_allocated_block_growth": 50000,
    "max_scheduler_pending_end": 0,
    "max_scheduler_active_end": 0,
    "max_scheduler_queue_high_water": 32,
    "max_cycle_median_growth_ratio": 2.5,
}


def current_rss_mib() -> float:
    """Best-effort current RSS without adding a psutil dependency."""
    status = Path("/proc/self/status")
    if status.exists():
        try:
            for line in status.read_text("utf-8", errors="ignore").splitlines():
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return round(float(parts[1]) / 1024.0, 3)
        except Exception:
            pass

    try:
        import resource

        rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # macOS reports bytes; Linux and most BSD CI environments report KiB.
        if sys.platform == "darwin":
            rss /= 1024.0 * 1024.0
        else:
            rss /= 1024.0
        return round(rss, 3)
    except Exception:
        return 0.0


def _drain_qt(app, *, turns: int = 1) -> None:
    """Process normal events and DeferredDelete events like the real Qt loop."""
    from PySide6.QtCore import QCoreApplication, QEvent

    for _ in range(max(1, int(turns))):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    rank = max(1, int((float(percentile) / 100.0) * len(ordered) + 0.999999))
    return ordered[min(rank - 1, len(ordered) - 1)]


def _quarter_median(values: list[float], *, tail: bool = False) -> float:
    if not values:
        return 0.0
    width = max(1, len(values) // 4)
    sample = values[-width:] if tail else values[:width]
    return float(statistics.median(sample))


class SoakCacheBridge:
    """Synthetic cache bridge that still uses the real scheduler/invalidation path."""

    def __init__(self, browser: Any, scheduler: BackgroundScheduler):
        from PySide6.QtCore import QObject, Signal

        class _Signals(QObject):
            albumReady = Signal(object)
            artistReady = Signal(object)

        self.browser = browser
        self.scheduler = scheduler
        self.signals = _Signals(browser)
        self.signals.albumReady.connect(browser.set_artwork)
        self.signals.artistReady.connect(browser.set_artist_images)
        browser.artworkRequested.connect(self._album_requested)
        browser.artistImageCacheRequested.connect(self._artist_requested)
        browser.cachedArtworkInvalidated.connect(self._invalidated)

    def _deliver(self, future, signal) -> None:
        try:
            result = future.result()
        except (CancelledError, StaleTaskError):
            return
        except Exception:
            return
        signal.emit(result)

    @staticmethod
    def _cache_payload(rows: list[dict[str, Any]]) -> dict[str, str]:
        # A tiny delay lets scroll/catalog invalidation race with real queued/running
        # work. Returning empty paths mirrors a cache miss without touching disk.
        time.sleep(0.004)
        return {
            str(row.get("key") or ""): ""
            for row in rows
            if str(row.get("key") or "")
        }

    def _album_requested(self, requests: object) -> None:
        rows = [dict(row) for row in list(requests or []) if isinstance(row, dict)]
        if not rows:
            return
        future = self.scheduler.submit(
            lambda: self._cache_payload(rows),
            priority="visible",
            lane="disk",
            label="soak-viewport-album-artwork",
            key="viewport-album-artwork",
            replace=True,
        )
        future.add_done_callback(
            lambda done: self._deliver(done, self.signals.albumReady)
        )

    def _artist_requested(self, requests: object) -> None:
        rows = [dict(row) for row in list(requests or []) if isinstance(row, dict)]
        if not rows:
            return
        future = self.scheduler.submit(
            lambda: self._cache_payload(rows),
            priority="visible",
            lane="disk",
            label="soak-viewport-artist-photo",
            key="viewport-artist-photo",
            replace=True,
        )
        future.add_done_callback(
            lambda done: self._deliver(done, self.signals.artistReady)
        )

    def _invalidated(self, kind: str) -> None:
        kind = str(kind or "")
        if kind == "artists":
            self.scheduler.cancel_key("viewport-artist-photo")
            self.browser.cached_artwork_batch_cancelled("artists")
        elif kind == "albums":
            self.scheduler.cancel_key("viewport-album-artwork")
            self.browser.cached_artwork_batch_cancelled("albums")


def _submit_latest_wins_churn(
    scheduler: BackgroundScheduler,
    cycle: int,
) -> None:
    """Exercise P8c/P8d lanes with replaceable work, never network/filesystem."""
    specs = (
        ("soak-search", "foreground", "network", 0.003),
        ("soak-prefetch", "prefetch", "prefetch", 0.005),
        ("soak-context", "visible", "disk", 0.004),
        ("soak-analysis", "foreground", "analysis", 0.004),
    )
    for key, priority, lane, delay in specs:
        # Three generations per cycle forces queued cancellation and occasional
        # running-result suppression while keeping only the newest generation useful.
        for generation in range(3):
            scheduler.submit(
                lambda d=delay, value=(cycle, generation): (
                    time.sleep(d),
                    value,
                )[1],
                priority=priority,
                lane=lane,
                label=key,
                key=key,
                replace=True,
            )


def _measure_action(
    app,
    monitor,
    samples: dict[str, list[float]] | None,
    label: str,
    fn,
) -> float:
    token = monitor.begin_interaction(f"soak:{label}") if monitor is not None else None
    started = time.perf_counter()
    fn()
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if monitor is not None:
        monitor.end_interaction(token)
    if samples is not None:
        samples.setdefault(str(label), []).append(elapsed_ms)
    # A real user cannot perform the next action before Qt gets another turn.
    _drain_qt(app)
    return elapsed_ms


def _run_interaction_cycle(
    app,
    browser: Any,
    scheduler: BackgroundScheduler,
    catalog: list[dict[str, Any]],
    cycle: int,
    *,
    pace_ms: int,
    monitor=None,
    action_samples: dict[str, list[float]] | None = None,
) -> float:
    started = time.perf_counter()
    phase = cycle % 6

    if phase in {0, 3}:
        view = "albums"
        _measure_action(
            app,
            monitor,
            action_samples,
            "view:albums",
            lambda: browser.set_view("albums"),
        )
        bar = browser.album_scroll.verticalScrollBar()
        target = bar.maximum() if phase == 3 else 0
        _measure_action(
            app,
            monitor,
            action_samples,
            "scroll:albums",
            lambda: bar.setValue(target),
        )
    elif phase in {1, 4}:
        view = "artists"
        _measure_action(
            app,
            monitor,
            action_samples,
            "view:artists",
            lambda: browser.set_view("artists"),
        )
        bar = browser.artist_scroll.verticalScrollBar()
        target = bar.maximum() if phase == 4 else 0
        _measure_action(
            app,
            monitor,
            action_samples,
            "scroll:artists",
            lambda: bar.setValue(target),
        )
    else:
        view = "tracks"
        _measure_action(
            app,
            monitor,
            action_samples,
            "view:tracks",
            lambda: browser.set_view("tracks"),
        )
        bar = browser.track_list.verticalScrollBar()
        target = bar.maximum() if phase == 5 else 0
        _measure_action(
            app,
            monitor,
            action_samples,
            "scroll:tracks",
            lambda: bar.setValue(target),
        )

    # Alternate a narrow query and a clear. Treat it as a separate user action
    # rather than combining it with navigation in the same GUI turn.
    if cycle % 4 == 0 and catalog:
        row = catalog[(cycle * 97) % len(catalog)]
        query = str(row.get("album") or row.get("artist") or "")
        _measure_action(
            app,
            monitor,
            action_samples,
            f"filter:{view}:set",
            lambda: browser.search.setText(query),
        )
    else:
        _measure_action(
            app,
            monitor,
            action_samples,
            f"filter:{view}:clear",
            browser.search.clear,
        )

    _submit_latest_wins_churn(scheduler, cycle)
    _drain_qt(app)

    if pace_ms > 0:
        time.sleep(float(pace_ms) / 1000.0)
    _drain_qt(app)

    return (time.perf_counter() - started) * 1000.0


def evaluate_report(
    report: dict[str, Any],
    *,
    budgets: dict[str, float | int] | None = None,
) -> tuple[bool, list[str]]:
    limits = dict(DEFAULT_BUDGETS)
    limits.update(dict(budgets or {}))
    failures: list[str] = []

    responsiveness = dict(report.get("responsiveness") or {})
    memory = dict(report.get("memory") or {})
    scheduler = dict(report.get("scheduler") or {})
    cycles = dict(report.get("cycles") or {})
    widgets = dict(report.get("widgets") or {})

    checks = (
        (
            int(responsiveness.get("ci_violations") or 0)
            <= int(limits["max_ci_violations"]),
            "event-loop CI violations",
        ),
        (
            int(responsiveness.get("serious_stalls") or 0)
            <= int(limits["max_serious_stalls"]),
            "serious event-loop stalls",
        ),
        (
            int(responsiveness.get("release_blockers") or 0)
            <= int(limits["max_release_blockers"]),
            "release-blocker stalls",
        ),
        (
            float(memory.get("rss_growth_mib") or 0.0)
            <= float(limits["max_rss_growth_mib"]),
            "RSS growth",
        ),
        (
            int(memory.get("gc_object_growth") or 0)
            <= int(limits["max_gc_object_growth"]),
            "retained GC object growth",
        ),
        (
            int(memory.get("allocated_block_growth") or 0)
            <= int(limits["max_allocated_block_growth"]),
            "allocated Python block growth",
        ),
        (
            int(scheduler.get("pending_total") or 0)
            <= int(limits["max_scheduler_pending_end"]),
            "scheduler pending work at end",
        ),
        (
            int(scheduler.get("active_total") or 0)
            <= int(limits["max_scheduler_active_end"]),
            "scheduler active work at end",
        ),
        (
            int(scheduler.get("queue_high_water") or 0)
            <= int(limits["max_scheduler_queue_high_water"]),
            "scheduler queue high-water mark",
        ),
        (
            float(cycles.get("median_growth_ratio") or 0.0)
            <= float(limits["max_cycle_median_growth_ratio"]),
            "cycle-time degradation",
        ),
        (
            int(widgets.get("hydrated_track_rows") or 0)
            <= int(widgets.get("hydrated_track_row_budget") or 0),
            "hydrated TrackRow bound",
        ),
    )

    for passed, label in checks:
        if not passed:
            failures.append(label)

    if int(scheduler.get("invalidations") or 0) <= 0:
        failures.append("soak did not exercise scheduler invalidation")
    if (
        int(scheduler.get("stale_queued_cancelled") or 0)
        + int(scheduler.get("stale_results_suppressed") or 0)
        <= 0
    ):
        failures.append("soak did not create stale work to eliminate")

    return not failures, failures


def run_soak(
    *,
    track_count: int = 12_700,
    minimum_cycles: int = 240,
    duration_seconds: float = 12.0,
    warmup_cycles: int = 12,
    pace_ms: int = 8,
) -> dict[str, Any]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from melodex.library_browser import LibraryBrowser
    from melodex.responsiveness import UiResponsivenessMonitor

    app = QApplication.instance() or QApplication([])
    catalog = synthetic_catalog(int(track_count))

    browser = LibraryBrowser()
    browser.resize(1200, 800)
    browser.show()

    scheduler = BackgroundScheduler(
        max_workers=4,
        foreground_reserve=1,
        lane_limits={
            "default": 4,
            "disk": 2,
            "network": 2,
            "analysis": 1,
            "prefetch": 1,
            "idle": 1,
        },
        thread_name_prefix="melodex-soak",
    )
    bridge = SoakCacheBridge(browser, scheduler)

    load_started = time.perf_counter()
    browser.set_catalog(catalog, revision=int(track_count))
    _drain_qt(app, turns=2)
    catalog_load_seconds = time.perf_counter() - load_started

    for cycle in range(max(0, int(warmup_cycles))):
        _run_interaction_cycle(
            app,
            browser,
            scheduler,
            catalog,
            cycle,
            pace_ms=max(0, int(pace_ms)),
        )
    scheduler.wait_for_idle(5.0)
    _drain_qt(app, turns=3)
    gc.collect()
    _drain_qt(app)

    rss_start = current_rss_mib()
    gc_objects_start = len(gc.get_objects())
    allocated_blocks_start = (
        int(sys.getallocatedblocks())
        if hasattr(sys, "getallocatedblocks")
        else 0
    )

    monitor = UiResponsivenessMonitor(browser)
    monitor.start()

    cycle_ms: list[float] = []
    action_samples: dict[str, list[float]] = {}
    checkpoints: list[dict[str, Any]] = []
    soak_started = time.perf_counter()
    cycle = 0
    while (
        cycle < max(1, int(minimum_cycles))
        or time.perf_counter() - soak_started < max(0.0, float(duration_seconds))
    ):
        cycle_ms.append(
            _run_interaction_cycle(
                app,
                browser,
                scheduler,
                catalog,
                cycle + int(warmup_cycles),
                pace_ms=max(0, int(pace_ms)),
                monitor=monitor,
                action_samples=action_samples,
            )
        )
        cycle += 1
        if cycle % 50 == 0:
            checkpoints.append(
                {
                    "cycle": cycle,
                    "elapsed_seconds": round(time.perf_counter() - soak_started, 3),
                    "rss_mib": current_rss_mib(),
                    "scheduler": scheduler.snapshot(),
                    "track_rows": len(browser.track_rows),
                }
            )

    scheduler.wait_for_idle(10.0)
    for _ in range(5):
        _drain_qt(app)
        time.sleep(0.001)
    monitor.stop()
    gc.collect()
    _drain_qt(app, turns=2)

    responsiveness = monitor.summary()
    scheduler_summary = scheduler.snapshot()

    rss_end = current_rss_mib()
    gc_objects_end = len(gc.get_objects())
    allocated_blocks_end = (
        int(sys.getallocatedblocks())
        if hasattr(sys, "getallocatedblocks")
        else 0
    )

    first_median = _quarter_median(cycle_ms)
    last_median = _quarter_median(cycle_ms, tail=True)
    median_growth_ratio = (
        last_median / max(1.0, first_median)
        if cycle_ms
        else 0.0
    )

    viewport_rows = max(
        1,
        browser.track_list.viewport().height() // browser._track_row_height + 3,
    )
    hydrated_budget = viewport_rows + browser._track_overscan_rows * 2

    action_summary = {
        label: {
            "count": len(values),
            "median_ms": round(statistics.median(values), 3) if values else 0.0,
            "p95_ms": round(_percentile(values, 95.0), 3),
            "max_ms": round(max(values, default=0.0), 3),
        }
        for label, values in sorted(action_samples.items())
    }

    report = {
        "schema": 1,
        "profile_tracks": int(track_count),
        "catalog_load_seconds": round(catalog_load_seconds, 6),
        "warmup_cycles": int(warmup_cycles),
        "duration_seconds": round(time.perf_counter() - soak_started, 3),
        "cycles_completed": cycle,
        "actions": action_summary,
        "cycles": {
            "median_ms": round(statistics.median(cycle_ms), 3) if cycle_ms else 0.0,
            "p95_ms": round(_percentile(cycle_ms, 95.0), 3),
            "max_ms": round(max(cycle_ms, default=0.0), 3),
            "first_quarter_median_ms": round(first_median, 3),
            "last_quarter_median_ms": round(last_median, 3),
            "median_growth_ratio": round(median_growth_ratio, 3),
        },
        "memory": {
            "rss_start_mib": round(rss_start, 3),
            "rss_end_mib": round(rss_end, 3),
            "rss_growth_mib": round(max(0.0, rss_end - rss_start), 3),
            "gc_objects_start": int(gc_objects_start),
            "gc_objects_end": int(gc_objects_end),
            "gc_object_growth": max(0, int(gc_objects_end - gc_objects_start)),
            "allocated_blocks_start": int(allocated_blocks_start),
            "allocated_blocks_end": int(allocated_blocks_end),
            "allocated_block_growth": max(
                0,
                int(allocated_blocks_end - allocated_blocks_start),
            ),
        },
        "responsiveness": responsiveness,
        "scheduler": scheduler_summary,
        "widgets": {
            "hydrated_track_rows": len(browser.track_rows),
            "hydrated_track_row_budget": hydrated_budget,
            "album_cards": len(browser.cards),
            "artist_cards": len(browser.artist_cards),
        },
        "artwork_priority": dict(browser.last_artwork_priority_metrics),
        "track_virtualization": dict(browser.last_track_virtualization_metrics),
        "checkpoints": checkpoints,
    }

    passed, failures = evaluate_report(report)
    report["verdict"] = {
        "passed": passed,
        "failures": failures,
        "budgets": dict(DEFAULT_BUDGETS),
    }

    scheduler.shutdown(wait=True, cancel_pending=True)
    del bridge
    browser.deleteLater()
    _drain_qt(app, turns=2)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a deterministic Fluid Melodex endurance scenario against a "
            "synthetic library and emit memory/responsiveness/scheduler metrics."
        )
    )
    parser.add_argument("--tracks", type=int, default=12_700)
    parser.add_argument("--cycles", type=int, default=240)
    parser.add_argument("--duration-seconds", type=float, default=12.0)
    parser.add_argument("--warmup-cycles", type=int, default=12)
    parser.add_argument("--pace-ms", type=int, default=8)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Always exit zero even if the soak verdict exceeds a budget.",
    )
    args = parser.parse_args()

    report = run_soak(
        track_count=args.tracks,
        minimum_cycles=args.cycles,
        duration_seconds=args.duration_seconds,
        warmup_cycles=args.warmup_cycles,
        pace_ms=args.pace_ms,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", "utf-8")

    passed = bool((report.get("verdict") or {}).get("passed"))
    return 0 if passed or args.no_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
