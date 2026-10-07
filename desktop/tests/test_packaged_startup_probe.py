from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "packaged_startup_probe.py"
STARTUP_SCRIPT = ROOT / "scripts" / "startup_probe.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("packaged_startup_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_startup_module():
    spec = importlib.util.spec_from_file_location("startup_probe", STARTUP_SCRIPT)
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


def test_startup_probe_contract_checks_warm_shell_and_cached_library() -> None:
    _contract_violations = _load_startup_module()._contract_violations

    good = {
        "warm_profile": {"timeline_total_ms": 450},
        "large_cached_profile": {
            "timeline_total_ms": 500,
            "first_music": {
                "journeys": {"process_to_cached_library_ms": 720},
            },
        },
    }
    assert _contract_violations(
        good, warm_limit_ms=1000, cached_limit_ms=1000
    ) == []

    slow = {
        "warm_profile": {"timeline_total_ms": 1100},
        "large_cached_profile": {
            "timeline_total_ms": 1050,
            "first_music": {
                "journeys": {"process_to_cached_library_ms": 1300},
            },
        },
    }
    violations = _contract_violations(
        slow, warm_limit_ms=1000, cached_limit_ms=1000
    )
    assert len(violations) == 3
    assert any("warm shell" in violation for violation in violations)
    assert any("cached-library shell" in violation for violation in violations)
    assert any("cached library visible" in violation for violation in violations)
