from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "qualify_nas_faults.py"

spec = importlib.util.spec_from_file_location("qualify_nas_faults", SCRIPT)
assert spec is not None and spec.loader is not None
qualify_nas_faults = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualify_nas_faults)


def test_campaign_11e_nas_fault_qualification_passes():
    result = qualify_nas_faults.run_qualification(
        tracks=40,
        cancel_limit_seconds=2.0,
    )

    assert result["campaign"] == "11e"
    assert result["passed"] is True

    latency = result["cases"]["high_latency_adaptation"]
    assert latency["storage_profile"] == "high-latency"
    assert latency["metadata_worker_limit"] == 2
    assert latency["metadata_in_flight_limit"] <= 4

    transient = result["cases"]["transient_fault_recovery"]
    assert transient["io_retries"] > 0
    assert transient["root_complete"] is True

    interrupted = result["cases"]["midscan_disconnect_preserves_cache"]
    assert interrupted["tracks"] == 40
    assert interrupted["roots_incomplete"] >= 1
    assert interrupted["tracks_deleted"] == 0

    browse = result["cases"]["cached_browse_during_slow_rescan"]
    assert browse["cached_counts_stable"] is True
    assert browse["reads"] >= 3
    assert browse["max_cached_read_seconds"] < 1.0

    cancel = result["cases"]["blocked_metadata_cancel"]
    assert cancel["cancelled"] is True
    assert cancel["hard_cancelled"] is True
