from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_guard():
    path = Path(__file__).resolve().parents[1] / "tools" / "check_size_regression.py"
    spec = importlib.util.spec_from_file_location("check_size_regression", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _baselines():
    return {
        "tolerance_percent": 10.0,
        "profiles": {
            "macOS-intel": {
                "installed_bytes": 1000,
                "archive_bytes": 500,
            },
            "Windows-x64": {
                "portable_zip_bytes": 800,
                "installer_bytes": 600,
            },
        },
    }


def test_macos_size_guard_passes_with_small_growth():
    guard = _load_guard()
    result = guard.evaluate(
        profile="macOS-intel",
        baselines=_baselines(),
        bundle_report={
            "total_bytes": 1075,
            "archive": {"bytes": 525},
        },
    )

    assert result["ok"] is True
    assert result["metrics"][0]["growth_percent"] == 7.5


def test_macos_size_guard_fails_large_growth():
    guard = _load_guard()
    result = guard.evaluate(
        profile="macOS-intel",
        baselines=_baselines(),
        bundle_report={
            "total_bytes": 1200,
            "archive": {"bytes": 525},
        },
    )

    assert result["ok"] is False
    installed = next(
        row for row in result["metrics"]
        if row["metric"] == "installed_bytes"
    )
    assert installed["ok"] is False
    assert installed["limit_bytes"] == 1100


def test_windows_size_guard_uses_shipping_files(tmp_path: Path):
    guard = _load_guard()
    portable = tmp_path / "portable.zip"
    installer = tmp_path / "setup.exe"
    portable.write_bytes(b"x" * 840)
    installer.write_bytes(b"x" * 620)

    result = guard.evaluate(
        profile="Windows-x64",
        baselines=_baselines(),
        portable=portable,
        installer=installer,
    )

    assert result["ok"] is True


def test_markdown_reports_baseline_actual_and_limit():
    guard = _load_guard()
    result = guard.evaluate(
        profile="macOS-intel",
        baselines=_baselines(),
        bundle_report={
            "total_bytes": 1050,
            "archive": {"bytes": 510},
        },
    )

    rendered = guard.markdown(result)

    assert "size regression check" in rendered
    assert "Baseline" in rendered
    assert "Actual" in rendered
    assert "Limit" in rendered
    assert "+5.0%" in rendered
