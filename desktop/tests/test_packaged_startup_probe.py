from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "packaged_startup_probe.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("packaged_startup_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packaged_probe_builds_appimage_command() -> None:
    module = _load_module()
    executable = Path("/tmp/Melodex.AppImage")

    assert module._command(executable, appimage=False) == [str(executable)]
    assert module._command(executable, appimage=True) == [
        str(executable),
        "--appimage-extract-and-run",
    ]


def test_packaged_probe_phase_map_ignores_invalid_rows() -> None:
    module = _load_module()
    mapped = module._phase_map(
        {
            "events": [
                {"phase": "app_module_ready", "elapsed_ms": 12.5, "delta_ms": 12.5},
                "invalid",
                {"phase": "", "elapsed_ms": 99},
                {"phase": "first_event_loop_turn", "elapsed_ms": 123.4, "delta_ms": 5.0},
            ]
        }
    )

    assert mapped == {
        "app_module_ready": {"elapsed_ms": 12.5, "delta_ms": 12.5},
        "first_event_loop_turn": {"elapsed_ms": 123.4, "delta_ms": 5.0},
    }
