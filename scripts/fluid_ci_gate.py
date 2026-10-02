from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"

FLUID_GATE_TESTS = [
    "desktop/tests/test_background_scheduler.py",
    "desktop/tests/test_responsiveness.py",
    "desktop/tests/test_responsiveness_gate.py",
    "desktop/tests/test_motion.py",
    "desktop/tests/test_fluid_soak_probe.py",
    "desktop/tests/test_library_index.py::test_provider_manager_defers_cached_catalog_hydration_until_first_use",
    "desktop/tests/test_plugin_config.py::test_default_secret_store_is_deferred_until_secret_access",
    "desktop/tests/test_gui_redesign.py::test_slow_source_config_check_keeps_qt_event_loop_responsive",
    "desktop/tests/test_gui_redesign.py::test_navigation_shell_changes_before_slow_page_population",
    "desktop/tests/test_gui_redesign.py::test_heavy_pages_build_once_after_navigation_shell",
    "desktop/tests/test_gui_redesign.py::test_rapid_navigation_drops_stale_page_population",
    "desktop/tests/test_gui_redesign.py::test_search_keeps_previous_results_visible_while_refreshing",
    "desktop/tests/test_gui_redesign.py::test_fast_search_never_flashes_delayed_loading_placeholder",
    "desktop/tests/test_gui_redesign.py::test_search_failure_preserves_stale_useful_results",
    "desktop/tests/test_gui_redesign.py::test_library_reuses_rendered_state_for_same_catalog_revision",
    "desktop/tests/test_gui_redesign.py::test_large_library_progressively_renders_widgets",
    "desktop/tests/test_gui_redesign.py::test_cached_album_artwork_prioritizes_viewport_and_scroll_target",
    "desktop/tests/test_gui_redesign.py::test_cached_artist_photos_use_same_viewport_priority",
    "desktop/tests/test_gui_redesign.py::test_run_async_replace_key_drops_stale_completion",
    "desktop/tests/test_gui_redesign.py::test_navigation_invalidates_hidden_page_build",
    "desktop/tests/test_gui_redesign.py::test_global_scan_activity_persists_across_navigation",
    "desktop/tests/test_gui_redesign.py::test_slow_library_scan_keeps_qt_event_loop_responsive",
    "desktop/tests/test_gui_redesign.py::test_love_and_keep_acknowledge_before_persistence",
    "desktop/tests/test_gui_redesign.py::test_optimistic_taste_action_rolls_back_if_persistence_fails",
    "desktop/tests/test_gui_redesign.py::test_next_track_prefetch_is_local_only_and_consumed_on_advance",
    "desktop/tests/test_gui_redesign.py::test_next_track_prefetch_yields_to_large_library_scan",
    "desktop/tests/test_gui_redesign.py::test_navigation_motion_happens_after_immediate_shell_change",
]


def _qt_preflight() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:
        raise SystemExit(
            "Fluid Melodex gate cannot run: Qt Widgets runtime is unavailable: "
            f"{exc}"
        ) from exc

    app = QApplication.instance() or QApplication([])
    app.processEvents()


def main() -> int:
    _qt_preflight()

    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    current_pythonpath = env.get("PYTHONPATH", "")
    desktop_path = str(DESKTOP)
    env["PYTHONPATH"] = (
        desktop_path
        if not current_pythonpath
        else desktop_path + os.pathsep + current_pythonpath
    )

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--maxfail=1",
        *FLUID_GATE_TESTS,
    ]
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
