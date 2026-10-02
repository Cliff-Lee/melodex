from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from melodex.library_scan_process import (
    LibraryScanProcess,
    SCAN_CHILD_FLAG,
    library_scan_child_command,
)


def test_source_scan_child_command_reenters_desktop_runner():
    command = library_scan_child_command()
    assert command[0] == sys.executable
    assert SCAN_CHILD_FLAG in command


def test_library_scan_process_round_trip_persists_index(tmp_path: Path):
    data_dir = tmp_path / "data"
    root = tmp_path / "music"
    root.mkdir()
    (root / "one.flac").write_bytes(b"not-a-real-flac")
    (root / "two.flac").write_bytes(b"not-a-real-flac-either")

    done = threading.Event()
    result_box = {}
    errors = []
    phases = []

    runner = LibraryScanProcess(
        data_dir,
        [root],
        on_progress=lambda payload: phases.append(str(payload.get("phase") or "")),
        on_done=lambda payload: (result_box.setdefault("result", payload), done.set()),
        on_error=lambda error: (errors.append(str(error)), done.set()),
        hard_cancel_after=0.2,
    )
    runner.start()

    assert done.wait(10), "isolated library scanner did not finish"
    assert errors == []

    result = dict(result_box["result"])
    assert result["cancelled"] is False
    assert result["metrics"]["process_isolated"] is True
    assert len(result["tracks"]) == 2
    assert result["persistence"]["tracks_written"] == 2
    assert (data_dir / "library-index.sqlite3").is_file()
    assert "discovering" in phases
    assert "metadata" in phases
    assert "saving" in phases


def test_hard_cancel_terminates_unresponsive_scan_worker(tmp_path: Path):
    script = tmp_path / "hung_scan_worker.py"
    script.write_text(
        "import json, sys, time\n"
        "sys.stdin.readline()\n"
        "print(json.dumps({'type':'progress','payload':{'phase':'discovering'}}), flush=True)\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )

    progress = threading.Event()
    done = threading.Event()
    result_box = {}
    errors = []

    runner = LibraryScanProcess(
        tmp_path / "data",
        [tmp_path / "nas"],
        on_progress=lambda payload: progress.set(),
        on_done=lambda payload: (result_box.setdefault("result", payload), done.set()),
        on_error=lambda error: (errors.append(str(error)), done.set()),
        command=[sys.executable, "-u", str(script)],
        hard_cancel_after=0.05,
    )
    runner.start()
    assert progress.wait(3), "test worker did not start"

    started = time.monotonic()
    runner.cancel()

    assert done.wait(3), "hard cancellation did not contain the stuck worker"
    elapsed = time.monotonic() - started
    assert elapsed < 2.0
    assert errors == []
    assert result_box["result"]["cancelled"] is True
    assert result_box["result"]["hard_cancelled"] is True
    assert runner.running is False


def test_shutdown_kills_worker_without_waiting_for_scan_completion(tmp_path: Path):
    script = tmp_path / "hung_on_shutdown.py"
    script.write_text(
        "import sys, time\n"
        "sys.stdin.readline()\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )

    runner = LibraryScanProcess(
        tmp_path / "data",
        [tmp_path / "nas"],
        on_progress=lambda payload: None,
        on_done=lambda payload: None,
        on_error=lambda error: None,
        command=[sys.executable, "-u", str(script)],
    )
    runner.start()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not runner.running:
        time.sleep(0.005)

    started = time.monotonic()
    runner.shutdown(timeout=0.05)
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert runner.running is False
