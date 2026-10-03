from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "qualify_nas_beta.py"

spec = importlib.util.spec_from_file_location("qualify_nas_beta", SCRIPT)
assert spec is not None and spec.loader is not None
qualify_nas_beta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualify_nas_beta)


def test_campaign_11c_small_nas_qualification_passes():
    result = qualify_nas_beta.run_qualification(
        tracks=6,
        cancel_limit_seconds=2.0,
    )

    assert result["campaign"] == "11c"
    assert result["passed"] is True
    assert result["cases"]["initial_scan"]["tracks"] == 6
    assert result["cases"]["offline_cache_preservation"]["tracks"] == 6
    assert result["cases"]["offline_cache_preservation"]["incomplete_roots"] >= 1
    assert result["cases"]["reconnect_rescan"]["tracks"] == 6
    assert result["cases"]["hung_worker_cancel"]["hard_cancelled"] is True
