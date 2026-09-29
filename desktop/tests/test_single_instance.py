from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


def test_second_process_activates_existing_instance_and_exits(tmp_path: Path):
    desktop = Path(__file__).resolve().parents[1]
    data_dir = tmp_path / "app-data"
    data_dir.mkdir()
    ready = tmp_path / "instance-state.txt"
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(desktop), env.get("PYTHONPATH", "")])

    first_code = r"""
import sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QTimer
from melodex.single_instance import SingleInstanceGuard

app = QCoreApplication([])
guard = SingleInstanceGuard(Path(sys.argv[1]))
state = Path(sys.argv[2])
guard.activationRequested.connect(
    lambda: (state.write_text("activated", "utf-8"), app.quit())
)
if not guard.acquire():
    raise SystemExit(2)
state.write_text("ready", "utf-8")
QTimer.singleShot(10000, app.quit)
raise SystemExit(app.exec())
"""
    second_code = r"""
import sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from melodex.single_instance import SingleInstanceGuard

app = QCoreApplication([])
guard = SingleInstanceGuard(Path(sys.argv[1]))
print("primary" if guard.acquire() else "secondary", flush=True)
"""

    first = subprocess.Popen(
        [sys.executable, "-c", first_code, str(data_dir), str(ready)],
        cwd=desktop.parent,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 8
        while not ready.exists() and first.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        if not ready.exists():
            stdout, stderr = first.communicate(timeout=2)
            pytest.fail(f"First instance did not start.\nstdout: {stdout}\nstderr: {stderr}")

        second = subprocess.run(
            [sys.executable, "-c", second_code, str(data_dir)],
            cwd=desktop.parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        assert second.returncode == 0, second.stderr
        assert second.stdout.strip() == "secondary"
        assert first.wait(timeout=5) == 0
        assert ready.read_text("utf-8") == "activated"
    finally:
        if first.poll() is None:
            first.kill()
            first.communicate(timeout=3)
