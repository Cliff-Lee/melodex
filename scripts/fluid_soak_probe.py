from __future__ import annotations

import argparse
import gc
import json
import math
import os
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
SCRIPTS = ROOT / "scripts"
for entry in (DESKTOP, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from large_library_probe import synthetic_catalog  # noqa: E402


def _scroll_to_fraction(scrollbar: Any, fraction: float) -> None:
    maximum = max(0, int(scrollbar.maximum()))
    value = int(round(maximum * max(0.0, min(1.0, float(fraction)))))
    scrollbar.setValue(value)


def _pump_events(app: Any) -> None:
    from PySide6.QtCore import QCoreApplication, QEvent

    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def _wait_scheduler_idle(app: Any, scheduler: Any, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        _pump_events(app)
        if int(scheduler.snapshot().get("pending_total") or 0) == 0 and int(
            scheduler.snapshot().get("active_total") or 0
        ) == 0:
            return True
        time.sleep(0.005)
    _pump_events(app)
    snapshot = scheduler.snapshot()
    return (
        int(snapshot.get("pending_total") or 0) == 0
        and int(snapshot.get("active_total") or 0) == 0
    )


def run_soak(
    *,
    track_count: int = 12_700,
    cycles: int = 80,
    duration_seconds: float = 0.0,
    pause_ms: int = 5,
    memory_growth_limit_mib: float = 64.0,
    p99_gap_limit_ms: float = 250.0,
    max_pending_limit: int = 12,
) -> dict[str, Any]:
    """Exercise a large synthetic library through repeated mixed UI workloads.

    Responsiveness and retained-memory phases are deliberately separated.
    tracemalloc is valuable for leak detection but adds substantial allocation
    overhead, so it must not distort the event-loop latency contract.
    """

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget

    from melodex.album_wall import AlbumWallWidget
    from melodex.album_wall_model import build_album_wall
    from melodex.background_scheduler import BackgroundScheduler
    from melodex.library_browser import LibraryBrowser
    from melodex.responsiveness import UiResponsivenessMonitor

    track_count = max(100, int(track_count))
    cycles = max(1, int(cycles))
    duration_seconds = max(0.0, float(duration_seconds))
    pause_ms = max(0, int(pause_ms))

    app = QApplication.instance() or QApplication([])
    catalog = synthetic_catalog(track_count)
    browser = LibraryBrowser()
    browser.resize(1200, 800)
    browser.show()

    browser.set_catalog(catalog, revision=track_count)
    _pump_events(app)

    wall = AlbumWallWidget()
    wall.resize(1200, 800)
    wall.set_model(build_album_wall(catalog, max_albums=1200))
    wall.show()
    _pump_events(app)
    wall_tiles = list(wall.tiles.values())
    baseline_wall_tiles = len(wall_tiles)

    # Warm every presentation plus representative filter/clear transitions
    # before taking stability baselines. This excludes legitimate one-time Qt
    # construction and deferred-delete churn from the leak signal.
    for view in ("albums", "artists", "tracks", "albums"):
        browser.set_view(view)
        _pump_events(app)
    for view, query in (
        ("tracks", "Genre 03"),
        ("artists", "Artist 00042"),
        ("albums", "Album 000123"),
    ):
        browser.set_view(view)
        browser.search.setText(query)
        _pump_events(app)
        browser.search.clear()
        _pump_events(app)
    browser.set_view("albums")
    browser.search.clear()
    QTest.qWait(20)
    _pump_events(app)
    gc.collect()
    _pump_events(app)

    baseline_widget_count = len(browser.findChildren(QWidget))
    baseline_track_rows = len(browser.track_rows)

    monitor = UiResponsivenessMonitor(
        browser,
        interval_ms=20,
        long_task_threshold_ms=50,
        ci_threshold_ms=250,
        serious_threshold_ms=500,
        blocker_threshold_ms=1000,
    )
    monitor.start()

    scheduler = BackgroundScheduler(
        max_workers=4,
        reserved_foreground_slots=1,
    )

    views = ("albums", "artists", "tracks")
    queries = (
        "",
        "Album 000123",
        "Artist 00042",
        "Genre 03",
        "Track 07",
        "",
    )
    resize_sizes = (
        (1200, 800),
        (980, 680),
        (1360, 820),
        (1040, 720),
        (1280, 760),
    )

    max_pending = 0
    max_active = 0
    max_widgets = baseline_widget_count
    max_album_cards = len(browser.cards)
    max_artist_cards = len(browser.artist_cards)
    max_album_cache = len(browser._album_card_cache)
    max_artist_cache = len(browser._artist_card_cache)
    max_track_rows = baseline_track_rows
    cycle_durations_ms: list[float] = []
    resize_mismatches = 0
    wall_pan_count = 0

    def exercise_ui(cycle: int, *, record_action: bool) -> None:
        nonlocal resize_mismatches, wall_pan_count
        view = views[cycle % len(views)]
        if record_action:
            monitor.mark_action(f"soak:view:{view}")
        browser.set_view(view)
        _pump_events(app)

        fraction = ((cycle * 37) % 101) / 100.0
        if view == "albums":
            _scroll_to_fraction(browser.album_scroll.verticalScrollBar(), fraction)
        elif view == "artists":
            _scroll_to_fraction(browser.artist_scroll.verticalScrollBar(), fraction)
        else:
            _scroll_to_fraction(browser.track_list.verticalScrollBar(), fraction)
        _pump_events(app)

        query = queries[cycle % len(queries)]
        if record_action:
            monitor.mark_action("soak:filter")
        browser.search.setText(query)
        _pump_events(app)
        if query and cycle % 3 == 0:
            if record_action:
                monitor.mark_action("soak:filter-clear")
            browser.search.clear()
            _pump_events(app)

        width, height = resize_sizes[cycle % len(resize_sizes)]
        if record_action:
            monitor.mark_action("soak:resize")
        browser.resize(width, height)
        _pump_events(app)
        if browser.width() != width or browser.height() != height:
            resize_mismatches += 1

        if wall_tiles:
            if record_action:
                monitor.mark_action("soak:album-wall-pan")
            tile = wall_tiles[(cycle * 53) % len(wall_tiles)]
            wall.view.centerOn(tile)
            wall.resize(width, height)
            _pump_events(app)
            wall_pan_count += 1

    started = time.perf_counter()
    latency_started = started

    # Phase 1: latency/scheduler soak without tracemalloc overhead. P14m may
    # request a real wall-clock duration; ordinary CI keeps the bounded cycle
    # count so pull requests remain fast.
    cycle = 0
    while cycle < cycles or (
        duration_seconds > 0.0
        and time.perf_counter() - latency_started < duration_seconds
    ):
        cycle_started = time.perf_counter()
        exercise_ui(cycle, record_action=True)

        # Two same-scope submissions deliberately create stale queued work.
        # Replacement must keep the queue bounded while foreground work can
        # still enter immediately.
        scheduler.submit(
            lambda: time.sleep(0.008),
            priority="background",
            name="soak-model-old",
            replace_key="soak:model",
        )
        scheduler.submit(
            lambda: time.sleep(0.008),
            priority="background",
            name="soak-model-new",
            replace_key="soak:model",
        )
        scheduler.submit(
            lambda: time.sleep(0.002),
            priority="prefetch",
            name="soak-prefetch",
            replace_key="soak:prefetch",
        )
        scheduler.submit(
            lambda: None,
            priority="foreground",
            name="soak-foreground",
        )

        if pause_ms:
            QTest.qWait(pause_ms)
        else:
            _pump_events(app)
        _pump_events(app)

        scheduler_snapshot = scheduler.snapshot()
        max_pending = max(
            max_pending,
            int(scheduler_snapshot.get("pending_total") or 0),
        )
        max_active = max(
            max_active,
            int(scheduler_snapshot.get("active_total") or 0),
        )
        max_widgets = max(max_widgets, len(browser.findChildren(QWidget)))
        max_album_cards = max(max_album_cards, len(browser.cards))
        max_artist_cards = max(max_artist_cards, len(browser.artist_cards))
        max_album_cache = max(max_album_cache, len(browser._album_card_cache))
        max_artist_cache = max(max_artist_cache, len(browser._artist_card_cache))
        max_track_rows = max(max_track_rows, len(browser.track_rows))
        cycle_durations_ms.append(
            (time.perf_counter() - cycle_started) * 1000.0
        )
        cycle += 1

    latency_cycles = cycle
    latency_duration_seconds = time.perf_counter() - latency_started

    browser.search.clear()
    browser.set_view("albums")
    _pump_events(app)
    scheduler_idle = _wait_scheduler_idle(app, scheduler)
    QTest.qWait(40)
    _pump_events(app)
    monitor.stop()
    responsiveness = monitor.summary()
    final_scheduler = scheduler.snapshot()
    scheduler.shutdown(wait=True)

    # Phase 2: retained-memory soak. It uses a smaller repeat count because
    # tracemalloc intentionally slows allocation-heavy Qt/Python paths.
    gc.collect()
    _pump_events(app)
    tracemalloc.start()
    gc.collect()
    baseline_memory, _ = tracemalloc.get_traced_memory()
    max_python_mib = baseline_memory / (1024 * 1024)
    memory_cycles = max(8, min(24, int(math.ceil(latency_cycles / 4))))

    for offset in range(memory_cycles):
        exercise_ui(latency_cycles + offset, record_action=False)
        QTest.qWait(1)
        _pump_events(app)
        current_memory, peak_memory = tracemalloc.get_traced_memory()
        max_python_mib = max(
            max_python_mib,
            current_memory / (1024 * 1024),
            peak_memory / (1024 * 1024),
        )
        max_widgets = max(max_widgets, len(browser.findChildren(QWidget)))
        max_album_cards = max(max_album_cards, len(browser.cards))
        max_artist_cards = max(max_artist_cards, len(browser.artist_cards))
        max_album_cache = max(max_album_cache, len(browser._album_card_cache))
        max_artist_cache = max(max_artist_cache, len(browser._artist_card_cache))
        max_track_rows = max(max_track_rows, len(browser.track_rows))

    browser.search.clear()
    browser.set_view("albums")
    QTest.qWait(30)
    _pump_events(app)
    gc.collect()
    _pump_events(app)
    final_memory, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    final_widget_count = len(browser.findChildren(QWidget))

    viewport_rows = max(
        1,
        int(math.ceil(browser.track_list.viewport().height() / browser._track_row_height)),
    )
    track_row_limit = viewport_rows + browser._track_overscan_rows * 2 + 6

    memory_growth_mib = max(
        0.0,
        (final_memory - baseline_memory) / (1024 * 1024),
    )
    peak_growth_mib = max(
        0.0,
        (peak_memory - baseline_memory) / (1024 * 1024),
    )

    checks = {
        "scheduler_drained": bool(scheduler_idle),
        "no_release_blocker": int(responsiveness.get("release_blockers") or 0) == 0,
        "no_serious_stall": int(responsiveness.get("serious_stalls") or 0) == 0,
        "p99_event_loop_gap_within_budget": float(
            responsiveness.get("p99_event_loop_gap_ms") or 0.0
        ) <= float(p99_gap_limit_ms),
        "pending_queue_bounded": max_pending <= int(max_pending_limit),
        "worker_pool_bounded": max_active <= 4,
        "album_cards_bounded": max_album_cards <= int(browser._album_batch_size),
        "artist_cards_bounded": max_artist_cards <= int(browser._artist_batch_size),
        "album_card_cache_bounded": max_album_cache <= int(browser._card_cache_limit),
        "artist_card_cache_bounded": max_artist_cache <= int(browser._card_cache_limit),
        "track_rows_bounded": max_track_rows <= int(track_row_limit),
        "widgets_stable": final_widget_count <= baseline_widget_count + 24,
        "retained_python_memory_bounded": memory_growth_mib
        <= float(memory_growth_limit_mib),
        "resize_geometry_stable": resize_mismatches == 0,
        "album_wall_tiles_stable": len(wall.tiles) == baseline_wall_tiles,
        "album_wall_exercised": wall_pan_count >= latency_cycles,
        "minimum_duration_completed": (
            duration_seconds <= 0.0
            or latency_duration_seconds >= duration_seconds
        ),
    }

    sorted_cycles = sorted(cycle_durations_ms)
    p95_index = max(0, math.ceil(len(sorted_cycles) * 0.95) - 1)
    result = {
        "schema": 2,
        "campaign": "P14m-endurance",
        "track_count": track_count,
        "cycles": latency_cycles,
        "cycles_requested": cycles,
        "cycles_completed": latency_cycles,
        "memory_cycles": memory_cycles,
        "target_duration_seconds": round(duration_seconds, 3),
        "latency_duration_seconds": round(latency_duration_seconds, 3),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "passed": all(checks.values()),
        "checks": checks,
        "responsiveness": responsiveness,
        "scheduler": {
            **final_scheduler,
            "max_pending_observed": max_pending,
            "max_active_observed": max_active,
        },
        "window": {
            "resize_mismatches": int(resize_mismatches),
            "sizes_exercised": len(resize_sizes),
        },
        "album_wall": {
            "tiles": int(len(wall.tiles)),
            "baseline_tiles": int(baseline_wall_tiles),
            "pan_iterations": int(wall_pan_count),
        },
        "widgets": {
            "baseline": baseline_widget_count,
            "final": final_widget_count,
            "max_observed": max_widgets,
            "max_album_cards": max_album_cards,
            "max_artist_cards": max_artist_cards,
            "max_album_card_cache": max_album_cache,
            "max_artist_card_cache": max_artist_cache,
            "card_cache_limit": int(browser._card_cache_limit),
            "max_track_rows": max_track_rows,
            "track_row_limit": track_row_limit,
        },
        "memory": {
            "baseline_mib": round(baseline_memory / (1024 * 1024), 3),
            "final_mib": round(final_memory / (1024 * 1024), 3),
            "retained_growth_mib": round(memory_growth_mib, 3),
            "peak_growth_mib": round(peak_growth_mib, 3),
            "max_traced_mib": round(max_python_mib, 3),
            "growth_limit_mib": float(memory_growth_limit_mib),
        },
        "cycles_ms": {
            "min": round(min(cycle_durations_ms, default=0.0), 3),
            "mean": round(
                sum(cycle_durations_ms) / max(1, len(cycle_durations_ms)),
                3,
            ),
            "p95": round(sorted_cycles[p95_index] if sorted_cycles else 0.0, 3),
            "max": round(max(cycle_durations_ms, default=0.0), 3),
        },
    }

    wall.deleteLater()
    browser.deleteLater()
    _pump_events(app)
    del catalog
    gc.collect()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run an offline large-library Fluid Melodex soak workload and "
            "check responsiveness, queue, widget and memory bounds."
        )
    )
    parser.add_argument("--tracks", type=int, default=12_700)
    parser.add_argument("--cycles", type=int, default=80)
    parser.add_argument(
        "--duration-minutes",
        type=float,
        default=0.0,
        help="Keep the latency phase running for at least this many minutes.",
    )
    parser.add_argument("--pause-ms", type=int, default=5)
    parser.add_argument("--memory-growth-limit-mib", type=float, default=64.0)
    parser.add_argument("--p99-gap-limit-ms", type=float, default=250.0)
    parser.add_argument("--max-pending-limit", type=int, default=12)
    parser.add_argument("--assert-contract", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = run_soak(
        track_count=args.tracks,
        cycles=args.cycles,
        duration_seconds=max(0.0, float(args.duration_minutes)) * 60.0,
        pause_ms=args.pause_ms,
        memory_growth_limit_mib=args.memory_growth_limit_mib,
        p99_gap_limit_ms=args.p99_gap_limit_ms,
        max_pending_limit=args.max_pending_limit,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", "utf-8")
    if args.assert_contract and not result["passed"]:
        failed = [
            name for name, passed in result["checks"].items() if not passed
        ]
        print("Fluid soak contract failed: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
