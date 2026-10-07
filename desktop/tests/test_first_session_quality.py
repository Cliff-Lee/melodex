from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_first_session_quality_qualification_passes() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "qualify_first_session_quality.py"
    )
    result = subprocess.run(
        [sys.executable, str(script), "--seeds", "8"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads(result.stdout)
    assert report["passed"] is True
    assert len(report["profiles"]) == 7
    assert all(row["all_tracks_preserved"] for row in report["profiles"])
