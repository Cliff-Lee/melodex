from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "desktop" / "tools" / "qualify_large_library.py"


def _module():
    spec = importlib.util.spec_from_file_location("p10i_qualification", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_p10i_small_profile_exercises_full_contract():
    module = _module()

    row = module.qualify_profile(
        120,
        tracks_per_directory=20,
        stat_delay_ms=0.0,
        directory_delay_ms=0.0,
        metadata_delay_ms=0.0,
        delta_changed=5,
        delta_added=3,
        delta_deleted=2,
        cancellation_after=8,
    )

    assert row["tracks"] == 120
    assert row["tracks_after_delta"] == 121
    assert row["cold"]["metadata_reads"] == 120
    assert row["unchanged"]["metadata_reads"] == 0
    assert row["unchanged"]["rows_written"] == 0
    assert row["delta"]["metadata_reads"] <= 8
    assert row["delta"]["rows_deleted"] == 2
    assert row["cold"]["queue_peak"] <= row["cold"]["queue_capacity"]
    assert all(row["checks"].values())


def test_p10i_release_profiles_include_one_million():
    module = _module()

    assert module.DEFAULT_PROFILES == (12_700, 100_000)
    assert module.RELEASE_PROFILES == (250_000, 500_000, 1_000_000)
