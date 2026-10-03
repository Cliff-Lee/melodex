from __future__ import annotations

import json

from melodex.scan_outcome import scan_storage_message, scan_storage_outcome


def test_scan_storage_outcome_reports_unavailable_without_paths():
    snapshot = {
        "root_states": [
            {
                "path": "/Volumes/PrivateNAS/Music",
                "available": False,
                "complete": False,
                "io_retries": 2,
            }
        ],
        "persistence": {
            "roots_unavailable": 1,
            "roots_incomplete": 0,
        },
    }

    outcome = scan_storage_outcome(snapshot)

    assert outcome == {
        "state": "unavailable",
        "root_count": 1,
        "roots_unavailable": 1,
        "roots_incomplete": 0,
        "io_retries": 2,
        "degraded": True,
    }
    assert "PrivateNAS" not in json.dumps(outcome)
    message = scan_storage_message(outcome)
    assert "showing your last indexed library" in message
    assert "cached tracks were removed" in message


def test_scan_storage_outcome_reports_incomplete_root():
    outcome = scan_storage_outcome(
        {
            "root_states": [
                {
                    "path": "/network/music",
                    "available": True,
                    "complete": False,
                    "io_retries": 4,
                }
            ],
            "persistence": {
                "roots_unavailable": 0,
                "roots_incomplete": 1,
            },
        }
    )

    assert outcome["state"] == "incomplete"
    assert outcome["roots_incomplete"] == 1
    assert outcome["io_retries"] == 4
    assert "No partial scan was applied" in scan_storage_message(outcome)


def test_scan_storage_outcome_clean_scan():
    outcome = scan_storage_outcome(
        {
            "root_states": [
                {
                    "path": "/music",
                    "available": True,
                    "complete": True,
                    "io_retries": 1,
                }
            ],
            "persistence": {
                "roots_unavailable": 0,
                "roots_incomplete": 0,
            },
        }
    )

    assert outcome["state"] == "ok"
    assert outcome["degraded"] is False
    assert scan_storage_message(outcome) == ""
