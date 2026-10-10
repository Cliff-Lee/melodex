from __future__ import annotations

"""Opt-in MM2 visual-Journey probe executed INSIDE a packaged Melodex binary.

The fixture is synthetic and cannot validate audio, a NAS or real metadata.
Never send Play or Queue: those remain manual release-acceptance checks.
"""

import json
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QTimer, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication


def _click_viewport(view, position) -> None:
    """Send an actual Qt mouse press/release without bundling QtTest.

    QtTest is intentionally omitted from Melodex's production Qt families.
    Delivering QWidget events through QtCore/QtGui exercises the same
    QGraphicsView event dispatch used by physical clicks.
    """
    viewport = view.viewport()
    local = QPointF(position)
    global_pos = QPointF(viewport.mapToGlobal(position))
    for event_type, buttons in (
        (QEvent.MouseButtonPress, Qt.LeftButton),
        (QEvent.MouseButtonRelease, Qt.NoButton),
    ):
        event = QMouseEvent(
            event_type, local, global_pos,
            Qt.LeftButton, buttons, Qt.NoModifier,
        )
        QApplication.sendEvent(viewport, event)


class PackagedMapProbe:
    def __init__(self, window, output: str):
        self.window = window
        self.output = Path(output)
        self.started = time.monotonic()
        self.checks: dict[str, bool] = {}
        self.route_started = 0.0
        self.emitted: list[str] = []
        self.finished = False

    def _check(self, label: str, condition: bool) -> None:
        self.checks[label] = bool(condition)
        if not condition:
            raise AssertionError(f"MM2 packaged GUI check failed: {label}")

    def start(self) -> None:
        try:
            self.window.resize(1024, 768)
            self.window.open_page("music_map")
            # Map is built lazily after a page-navigation debounce.
            wait_ms = int(self.window._page_refresh_delay_ms) + 200
            QTimer.singleShot(wait_ms, self._prepare)
        except Exception:
            self._finish(traceback.format_exc())

    def _prepare(self) -> None:
        try:
            ws = self.window.journey_workspace
            canvas = ws.music_map
            self._check("map page built", bool(ws.music_map_built))
            nodes = [
                {
                    "ref": f"f{i}",
                    "x": -0.52 + (i % 9) * 0.014,
                    "y": 0.4 + (i // 9) * 0.012,
                    "title": f"Fixture {i}",
                    "artist": "Fixture Artist",
                }
                for i in range(100)
            ]
            nodes += [
                {"ref": "a", "x": -0.7, "y": -0.65,
                 "title": "Start", "artist": "Start Artist"},
                {"ref": "b", "x": 0.7, "y": -0.65,
                 "title": "End", "artist": "End Artist"},
            ]
            tracks = {
                node["ref"]: {
                    "provider_id": "local",
                    "track_id": node["ref"],
                    "title": node["title"],
                    "artist": node["artist"],
                }
                for node in nodes
            }
            canvas.set_map({
                "nodes": nodes,
                "edges": [{"a": "a", "b": "b", "similarity": 0.98}],
                "analysed": len(nodes),
            }, tracks)
            QApplication.processEvents()
            self._check("cluster overview", bool(canvas._cluster_items))
            cluster = canvas._cluster_items[0]
            # Cluster is a UI control, not a point; at Fit its play target
            # must remain legible in viewport pixels.
            self._check(
                "fixed pixel cluster controls",
                bool(cluster.flags() & cluster.GraphicsItemFlag.ItemIgnoresTransformations),
            )
            bounds = cluster.deviceTransform(
                canvas.view.viewportTransform()
            ).mapRect(cluster.boundingRect())
            self._check("readable cluster tile width", 101 <= bounds.width() <= 107)
            self._check("visible region play glyph", cluster.play_rect().width() >= 22)

            ws.playTracksRequested.connect(lambda *_: self.emitted.append("play"))
            ws.queueTracksRequested.connect(lambda *_: self.emitted.append("queue"))
            canvas._select_ref("a")
            QApplication.processEvents()
            self._check("selection does not start audio", not self.emitted)

            # Drill to the real map points and use an actual viewport click
            # to set destination, not the shortcut endpoint setter.
            canvas.view.resetTransform()
            canvas.view.scale(1.55, 1.55)
            canvas._refresh_clusters()
            QApplication.processEvents()
            ws.music_map_start_journey_button.click()
            QApplication.processEvents()
            self._check("quick journey strip", ws.music_map_quick_route_panel.isVisible())
            self._check("start selection", ws.music_path_start_ref == "a")
            self._check("not playing while planning", not self.emitted)
            original_viewport = canvas.geometry()
            canvas.focus_ref("b")
            QApplication.processEvents()
            self._check("focus does not set destination", not ws.music_path_end_ref)
            item = canvas.node_items["b"]
            point = canvas.view.mapFromScene(
                item.mapToScene(item.boundingRect().center())
            )
            _click_viewport(canvas.view, point)
            QApplication.processEvents()
            self._check("viewport click chooses destination", ws.music_path_end_ref == "b")
            self._check("preview button enabled", ws.music_map_quick_preview_button.isEnabled())
            self._check("no audio from destination click", not self.emitted)
            self._check("map viewport unchanged by journey", canvas.geometry() == original_viewport)
            self.route_started = time.monotonic()
            ws.music_map_quick_preview_button.click()
            QApplication.processEvents()
            self._check("route request remains in same map", canvas.geometry() == original_viewport)
            QTimer.singleShot(30, self._await_route)
        except Exception:
            self._finish(traceback.format_exc())

    def _await_route(self) -> None:
        if self.finished:
            return
        try:
            ws = self.window.journey_workspace
            canvas = ws.music_map
            if ws._quick_route_pending:
                if time.monotonic() - self.route_started > 12:
                    raise TimeoutError("background route preview exceeded 12 seconds")
                QTimer.singleShot(40, self._await_route)
                return
            self._check("route preview succeeded", bool(ws.music_path_result.get("found")))
            self._check("drawn route begins at A", ws.music_path_result["path_refs"][0] == "a")
            self._check("drawn route ends at B", ws.music_path_result["path_refs"][-1] == "b")
            self._check("map has route geometry", bool(canvas.route_items))
            self._check("play/queue available only after preview",
                        ws.music_map_quick_play_button.isEnabled()
                        and ws.music_map_quick_queue_button.isEnabled())
            self._check("preview does not start audio", not self.emitted)
            canvas.set_route_progress(0)
            self._check("visual progress position", canvas._route_progress_index == 0)

            self.output.parent.mkdir(parents=True, exist_ok=True)
            screenshot = self.output.with_suffix(".png")
            self._check("full-window visual capture", self.window.grab().save(str(screenshot)))
            ws._cancel_quick_music_route()
            QApplication.processEvents()
            self._check("cancel clears route", not canvas.route_result)
            self._check("cancel does not start audio", not self.emitted)
            self._finish()
        except Exception:
            self._finish(traceback.format_exc())

    def _finish(self, error: str = "") -> None:
        if self.finished:
            return
        self.finished = True
        data = {
            "schema": 1,
            "scope": "packaged synthetic MM2 GUI only; no actual audio testing",
            "passed": not bool(error) and bool(self.checks) and all(self.checks.values()),
            "checks": self.checks,
            "duration_ms": round((time.monotonic() - self.started) * 1000, 3),
            "error": error,
            "screenshot": str(self.output.with_suffix(".png")),
        }
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        QTimer.singleShot(0, self.window.close)
        QTimer.singleShot(200, QApplication.instance().quit)


def start_packaged_probe(window, output: str) -> None:
    # Keep reference alive across Qt QTimer callbacks.
    window._mm2_packaged_probe = PackagedMapProbe(window, output)
    window._mm2_packaged_probe.start()
