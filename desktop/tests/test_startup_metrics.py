from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

from pathlib import Path

import pytest

from melodex.startup_metrics import StartupTimeline


def test_startup_timeline_records_monotonic_deltas(tmp_path) -> None:
    timeline = StartupTimeline(started_at=10.0)
    timeline.mark("module_ready", now=10.125)
    timeline.mark("ui_ready", now=10.300)

    summary = timeline.summary()
    assert summary["schema"] == 1
    assert summary["total_ms"] == pytest.approx(300.0)
    assert summary["events"] == [
        {
            "phase": "module_ready",
            "elapsed_ms": pytest.approx(125.0),
            "delta_ms": pytest.approx(125.0),
        },
        {
            "phase": "ui_ready",
            "elapsed_ms": pytest.approx(300.0),
            "delta_ms": pytest.approx(175.0),
        },
    ]

    path = timeline.write_json(tmp_path / "startup.json")
    stored = json.loads(path.read_text("utf-8"))
    assert stored["events"][1]["phase"] == "ui_ready"


def test_startup_timeline_rejects_empty_phase() -> None:
    timeline = StartupTimeline(started_at=0.0)
    with pytest.raises(ValueError):
        timeline.mark("   ", now=1.0)


def test_main_window_does_not_eager_import_heavy_page_modules() -> None:
    path = Path(__file__).resolve().parents[1] / "melodex" / "main_window.py"
    tree = ast.parse(path.read_text("utf-8"))
    imported = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module
    }
    forbidden = {
        "library_browser",
        "rich_now_playing",
        "living_canvas",
        "album_wall",
        "album_wall_model",
        "music_map",
        "music_map_model",
        "visualization_models",
        "plugin_directory",
        # P9d: Home/playback startup must not import optional feature graphs.
        "mind",
        "local_intelligence",
        "music_knowledge",
        "music_pathfinder",
        "music_journey",
        "music_journey_live",
        "journey_recipe",
        "journey_replay",
        "llm_bridge",
        "metadata",
        "playlist_io",
        "plugin_configuration_dialog",
        "plugin_onboarding",
        "diagnostics",
        "library_scan_process",
    }
    assert forbidden.isdisjoint(imported), imported & forbidden


def test_provider_manager_keeps_plugin_registry_lazy(tmp_path) -> None:
    from melodex.provider_manager import ProviderManager

    manager = ProviderManager(tmp_path / "data")
    try:
        assert manager._registry is None
        registry = manager.registry
        assert registry is manager._registry
    finally:
        manager.close()


def test_flow_import_keeps_numpy_cold() -> None:
    desktop = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    existing = str(env.get("PYTHONPATH") or "")
    env["PYTHONPATH"] = (
        str(desktop)
        if not existing
        else str(desktop) + os.pathsep + existing
    )
    code = (
        "import sys; import melodex.flow; "
        "assert 'numpy' not in sys.modules, 'Flow eagerly imported NumPy'"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        cwd=desktop.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
