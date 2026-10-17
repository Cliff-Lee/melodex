"""Unit tests for repeated real-package close qualification."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "package_shutdown_soak.py"


def load():
    spec = importlib.util.spec_from_file_location("package_shutdown_soak", SCRIPT)
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(SCRIPT.parent))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fresh_and_warm_packaged_launches_are_isolated(tmp_path, monkeypatch):
    module = load()
    executable = tmp_path / "Melodex"
    executable.touch()
    calls = []

    def simulate(path, profile, trace, *, appimage, timeout_seconds):
        calls.append((path, profile, trace))
        return {
            "process_wall_ms": 100.0,
            "phases": {"first_event_loop_turn": {"elapsed_ms": 80}},
        }

    monkeypatch.setattr(module, "_run_launch", simulate)
    report = module.qualify(executable, repeats=6)
    assert report["successful_exits"] == 6
    assert [x["profile"] for x in report["attempts"]] == [
        "fresh", "warm", "fresh", "warm", "fresh", "warm",
    ]
    assert calls[0][1] == calls[1][1]
    assert calls[1][1] != calls[2][1]
    assert len({str(x[2]) for x in calls}) == 6
    assert all(x["native_exit_zero"] for x in report["attempts"])


def test_nonzero_native_exit_is_a_strict_failure(tmp_path, monkeypatch):
    module = load()
    executable = tmp_path / "Melodex"
    executable.touch()

    def fail(*args, **kwargs):
        raise RuntimeError("packaged exit -11")

    monkeypatch.setattr(module, "_run_launch", fail)
    with pytest.raises(RuntimeError, match="exit -11"):
        module.qualify(executable, repeats=2)
