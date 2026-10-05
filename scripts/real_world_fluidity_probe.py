from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
SCRIPTS = ROOT / "scripts"
for entry in (DESKTOP, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from large_library_probe import synthetic_catalog  # noqa: E402


def _pump_events(app: Any) -> None:
    from PySide6.QtCore import QCoreApplication, QEvent

    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    rank = max(1, math.ceil((float(percentile) / 100.0) * len(ordered)))
    return ordered[min(rank - 1, len(ordered) - 1)]


def _measure(
    label: str,
    monitor: Any,
    app: Any,
    action: Callable[[], None],
) -> float:
    token = monitor.begin_interaction(label)
    started = time.perf_counter()
    action()
    _pump_events(app)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    monitor.end_interaction(token)
    return elapsed_ms


def run_probe(
    *,
    track_count: int = 12_700,
    pan_steps: int = 80,
    resize_cycles: int = 24,
    pause_ms: int = 2,
    p99_gap_limit_ms: float = 250.0,
) -> dict[str, Any]:
    """Exercise the exact large-library UI paths reported by an external tester.

    This probe intentionally uses Qt's offscreen platform so it is reproducible in
    CI. It does not claim to reproduce macOS WindowServer behaviour or an actual
    audio device. Those two gaps are covered by the manual P14 Mac qualification.
    """

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from melodex.album_wall import AlbumWallWidget
    from melodex.album_wall_model import build_album_wall
    from melodex.library_browser import LibraryBrowser
    from melodex.responsiveness import UiResponsivenessMonitor

    track_count = max(100, int(track_count))
    pan_steps = max(1, int(pan_steps))
    resize_cycles = max(1, int(resize_cycles))
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
    wall_model = build_album_wall(catalog, max_albums=1200)
    wall.set_model(wall_model)
    wall.show()
    _pump_events(app)

    # Feed visible artwork back exactly as the real UI callback does. Using one
    # tiny local image keeps the probe deterministic while still exercising the
    # GUI-thread QPixmap decode/scale/application path.
    temp_dir = tempfile.TemporaryDirectory(prefix="melodex-p14-")
    cover_path = Path(temp_dir.name) / "cover.png"
    image = QImage(48, 48, QImage.Format_ARGB32)
    image.fill(QColor("#556677"))
    image.save(str(cover_path))

    artwork_batches = 0
    artwork_items = 0

    def apply_artwork(rows: object) -> None:
        nonlocal artwork_batches, artwork_items
        batch = [dict(row) for row in list(rows or []) if isinstance(row, dict)]
        artwork_batches += 1
        artwork_items += len(batch)
        wall.set_artwork(
            {
                str(row.get("key") or ""): str(cover_path)
                for row in batch
                if str(row.get("key") or "")
            }
        )

    wall.artworkRequested.connect(apply_artwork)

    monitor = UiResponsivenessMonitor(
        wall,
        interval_ms=20,
        long_task_threshold_ms=50,
        ci_threshold_ms=250,
        serious_threshold_ms=500,
        blocker_threshold_ms=1000,
    )
    monitor.start()
    _pump_events(app)

    search_apply_ms = _measure(
        "p14:library-search",
        monitor,
        app,
        lambda: browser.search.setText("Album 000123"),
    )
    search_clear_ms = _measure(
        "p14:library-search-clear",
        monitor,
        app,
        browser.search.clear,
    )

    # Pan to a deterministic sequence of points across the scene. centerOn is
    # intentionally used instead of synthesising wheel events because the
    # performance target is the viewport-change/artwork/render path itself.
    tiles = list(wall.tiles.values())
    pan_durations: list[float] = []
    if tiles:
        for step in range(pan_steps):
            index = int(round((len(tiles) - 1) * ((step * 37) % pan_steps) / max(1, pan_steps - 1)))
            tile = tiles[max(0, min(len(tiles) - 1, index))]
            elapsed = _measure(
                "p14:album-wall-pan",
                monitor,
                app,
                lambda target=tile: wall.view.centerOn(target),
            )
            pan_durations.append(elapsed)
            if pause_ms:
                QTest.qWait(pause_ms)
                _pump_events(app)

    resize_durations: list[float] = []
    sizes = (
        (1280, 800),
        (1040, 700),
        (1440, 860),
        (900, 650),
        (1360, 760),
    )
    for cycle in range(resize_cycles):
        width, height = sizes[cycle % len(sizes)]
        elapsed = _measure(
            "p14:library-resize",
            monitor,
            app,
            lambda w=width, h=height: browser.resize(w, h),
        )
        resize_durations.append(elapsed)
        if pause_ms:
            QTest.qWait(pause_ms)
            _pump_events(app)

    QTest.qWait(50)
    _pump_events(app)
    monitor.stop()
    responsiveness = monitor.summary()

    wall_metrics_fn = getattr(wall, "diagnostics_snapshot", None)
    wall_metrics = dict(wall_metrics_fn() or {}) if callable(wall_metrics_fn) else {}

    checks = {
        "no_release_blocker": int(responsiveness.get("release_blockers") or 0) == 0,
        "no_serious_stall": int(responsiveness.get("serious_stalls") or 0) == 0,
        "p99_event_loop_gap_within_budget": float(
            responsiveness.get("p99_event_loop_gap_ms") or 0.0
        ) <= float(p99_gap_limit_ms),
        "search_clear_under_250ms": search_clear_ms <= 250.0,
        "pan_p95_under_100ms": _percentile(pan_durations, 95.0) <= 100.0,
        "resize_p95_under_100ms": _percentile(resize_durations, 95.0) <= 100.0,
    }

    result = {
        "schema": 1,
        "campaign": "P14a-real-world-fluidity-baseline",
        "track_count": track_count,
        "album_count": int(wall_model.get("album_count") or 0),
        "passed": all(checks.values()),
        "checks": checks,
        "library_search_ms": {
            "apply": round(search_apply_ms, 3),
            "clear": round(search_clear_ms, 3),
        },
        "album_wall": {
            "pan_steps": pan_steps,
            "pan_p50_ms": round(_percentile(pan_durations, 50.0), 3),
            "pan_p95_ms": round(_percentile(pan_durations, 95.0), 3),
            "pan_max_ms": round(max(pan_durations, default=0.0), 3),
            "artwork_batches": artwork_batches,
            "artwork_items": artwork_items,
            "runtime": wall_metrics,
        },
        "resize": {
            "cycles": resize_cycles,
            "p50_ms": round(_percentile(resize_durations, 50.0), 3),
            "p95_ms": round(_percentile(resize_durations, 95.0), 3),
            "max_ms": round(max(resize_durations, default=0.0), 3),
        },
        "responsiveness": responsiveness,
        "limitations": [
            "Offscreen Qt does not reproduce macOS WindowServer maximize/move behaviour.",
            "This probe does not use a physical audio device, so audible glitches require the manual Mac qualification.",
            "Synthetic metadata complements but does not replace the tester's real 12,700-track NAS collection.",
        ],
    }

    wall.close()
    browser.close()
    _pump_events(app)
    temp_dir.cleanup()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P14 real-world fluidity baseline probe"
    )
    parser.add_argument("--tracks", type=int, default=12_700)
    parser.add_argument("--pan-steps", type=int, default=80)
    parser.add_argument("--resize-cycles", type=int, default=24)
    parser.add_argument("--pause-ms", type=int, default=2)
    parser.add_argument("--p99-gap-limit-ms", type=float, default=250.0)
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Return non-zero when any P14 baseline check fails.",
    )
    args = parser.parse_args()

    result = run_probe(
        track_count=args.tracks,
        pan_steps=args.pan_steps,
        resize_cycles=args.resize_cycles,
        pause_ms=args.pause_ms,
        p99_gap_limit_ms=args.p99_gap_limit_ms,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if args.enforce and not result["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
