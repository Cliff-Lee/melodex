#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path


def _rect(rect) -> dict[str, int]:
    return {
        "x": int(rect.x()),
        "y": int(rect.y()),
        "width": int(rect.width()),
        "height": int(rect.height()),
    }


def run_probe(screenshot_dir: Path | None = None) -> dict[str, object]:
    from PySide6.QtCore import QSettings
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    import melodex.main_window as main_window

    app = QApplication.instance() or QApplication([])
    QSettings("Melodex", "Melodex").clear()

    with tempfile.TemporaryDirectory(prefix="melodex-p14m-") as temp:
        data_dir = Path(temp)
        main_window.app_data_dir = lambda: data_dir
        main_window.MainWindow._start_local_bridge = lambda self: None

        window = main_window.MainWindow()
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        target_width = min(900, max(640, int(available.width() * 0.72))) if available else 900
        target_height = min(620, max(480, int(available.height() * 0.72))) if available else 620
        window.resize(target_width, target_height)
        if available is not None:
            window.move(
                available.x() + max(0, (available.width() - target_width) // 2),
                available.y() + max(0, (available.height() - target_height) // 2),
            )
        window.show()
        app.processEvents()

        baseline = window.geometry()
        snapshots: dict[str, dict[str, int]] = {"baseline": _rect(baseline)}
        checks: dict[str, bool] = {}

        def save_screen(name: str) -> None:
            if screenshot_dir is None or screen is None:
                return
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            screen.grabWindow(0).save(str(screenshot_dir / f"{name}.png"))

        def capture(name: str) -> None:
            geometry = window.geometry()
            snapshots[name] = _rect(geometry)
            checks[name] = geometry.size() == baseline.size()
            save_screen(name)

        save_screen("baseline")

        window.open_page("music_map")
        QTest.qWait(window._page_refresh_delay_ms + 60)
        app.processEvents()
        capture("music_map_built")

        nodes = [
            {
                "ref": f"track-{index}",
                "title": f"Track {index}",
                "artist": f"Artist {index % 7}",
                "x": ((index % 9) / 4.0) - 1.0,
                "y": ((index % 7) / 3.0) - 1.0,
                "energy": 0.5,
            }
            for index in range(60)
        ]
        ref_map = {
            node["ref"]: {
                "provider_id": "local",
                "track_id": node["ref"],
                "title": node["title"],
                "artist": node["artist"],
            }
            for node in nodes
        }
        window.journey_workspace.music_map.set_map(
            {
                "nodes": nodes,
                "edges": [],
                "analysed": len(nodes),
                "input_profiles": len(nodes),
            },
            ref_map,
        )
        app.processEvents()
        capture("music_map_hydrated")

        window.journey_workspace._toggle_music_map_tools()
        window.journey_workspace._toggle_music_journey_options()
        app.processEvents()
        capture("music_map_tools")

        for page in ("library", "now_playing", "album_wall", "music_map", "home"):
            window.open_page(page)
            QTest.qWait(window._page_refresh_delay_ms + 30)
            app.processEvents()
            capture(f"page_{page}")

        normal_before_maximize = window.geometry()
        window.showMaximized()
        app.processEvents()
        maximized_supported = bool(window.isMaximized())
        if maximized_supported:
            window.open_page("music_map")
            QTest.qWait(window._page_refresh_delay_ms + 30)
            app.processEvents()
            window.showNormal()
            app.processEvents()
            normal_after_restore = window.geometry()
            checks["maximize_restore"] = (
                abs(normal_after_restore.width() - normal_before_maximize.width()) <= 4
                and abs(normal_after_restore.height() - normal_before_maximize.height()) <= 4
            )
            snapshots["normal_after_restore"] = _rect(normal_after_restore)
            save_screen("normal_after_restore")
        else:
            checks["maximize_restore"] = True

        if available is not None:
            current = window.geometry()
            intersection = current.intersected(available)
            checks["inside_available_work_area"] = (
                intersection.width() == current.width()
                and intersection.height() == current.height()
            )
        else:
            checks["inside_available_work_area"] = True

        result = {
            "schema": 1,
            "campaign": "P14m-window-geometry-containment",
            "platform": app.platformName(),
            "available_geometry": _rect(available) if available is not None else None,
            "snapshots": snapshots,
            "checks": checks,
            "window_minimum_size_hint": {
                "width": window.minimumSizeHint().width(),
                "height": window.minimumSizeHint().height(),
            },
            "stack_minimum_size_hint": {
                "width": window.stack.minimumSizeHint().width(),
                "height": window.stack.minimumSizeHint().height(),
            },
        }
        window.close()
        app.processEvents()
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--screenshot-dir", type=Path)
    args = parser.parse_args()

    result = run_probe(args.screenshot_dir)
    encoded = json.dumps(result, indent=2, sort_keys=True)
    print(encoded)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")

    failed = [name for name, passed in result["checks"].items() if not passed]
    if failed:
        print("P14m geometry contract failed: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
