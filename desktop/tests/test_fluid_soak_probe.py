from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fluid_soak_probe import run_soak


def test_small_fluid_soak_contract() -> None:
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
    except ImportError as exc:
        import pytest
        pytest.skip(f"Qt desktop runtime is unavailable: {exc}")

    result = run_soak(
        track_count=1_000,
        cycles=8,
        pause_ms=1,
        memory_growth_limit_mib=32.0,
        p99_gap_limit_ms=500.0,
        max_pending_limit=12,
    )

    assert result["passed"], result
    assert result["scheduler"]["max_active_observed"] <= 4
    assert result["widgets"]["max_album_cards"] <= 120
    assert result["widgets"]["max_artist_cards"] <= 120
    assert result["widgets"]["max_track_rows"] <= result["widgets"]["track_row_limit"]
    assert result["memory"]["retained_growth_mib"] <= 32.0
