from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "desktop" / "tools" / "profile_library_scale_matrix.py"


def _module():
    spec = importlib.util.spec_from_file_location("library_scale_matrix", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_p10_scale_profiles_cover_small_realistic_and_release_stress_sizes():
    module = _module()

    assert module.DEFAULT_PROFILES[:3] == (500, 5_000, 12_700)
    assert 100_000 in module.DEFAULT_PROFILES
    assert module.RELEASE_PROFILES == (250_000, 500_000, 1_000_000)


def test_p10_contract_protects_small_libraries_and_ui_responsiveness():
    module = _module()
    contract = module.SCALE_CONTRACT

    assert contract["interaction_ack_p95_ms"] == 100
    assert contract["small_library_max_regression_pct"] <= 10
    assert "small libraries must not materially regress" in contract["rules"]
    assert "queues and worker counts must stay bounded" in contract["rules"]


def test_profile_parser_accepts_human_friendly_counts():
    module = _module()

    assert module.parse_profiles("500, 5_000,12700") == (500, 5_000, 12_700)
