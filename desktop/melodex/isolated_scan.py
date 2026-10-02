from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .child_host import python_module_child_command
from .library_scan import ScanControl


class IsolatedScanError(RuntimeError):
    pass


class IsolatedLibraryScanRunner:
    """Run filesystem/tag scanning in a killable Melodex child process."""

    def __init__(
        self,
        index_path: Path,
        *,
        cancel_grace_seconds: float = 0.75,
    ) -> None:
        self.index_path = Path(index_path)
        self.cancel_grace_seconds = max(0.05, float(cancel_grace_seconds))

    @staticmethod
    def _cancelled_snapshot(*, hard_cancelled: bool) -> dict[str, Any]:
        return {
            "tracks": [],
            "index_tracks": [],
            "index_records": [],
            "root_states": [],
            "metrics": {
                "main_thread": False,
                "tracks_indexed": 0,
                "hard_cancelled": bool(hard_cancelled),
            },
            "changes": {},
            "cancelled": True,
            "hard_cancelled": bool(hard_cancelled),
        }

    @staticmethod
    def _write_message(process: subprocess.Popen[str], payload: dict[str, Any]) -> bool:
        stream = process.stdin
        if stream is None or process.poll() is not None:
            return False
        try:
            stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
            stream.flush()
            return True
        except (BrokenPipeError, OSError, ValueError):
            return False

    def _safe_error_detail(
        self,
        detail: str,
        roots: list[Path],
    ) -> str:
        """Remove private library/index paths before surfacing worker errors."""
        value = str(detail or "")
        replacements = [
            (str(self.index_path), "<library-index>"),
            *[(str(Path(root)), "<music-root>") for root in roots],
        ]
        for private, replacement in replacements:
            if private:
                value = value.replace(private, replacement)
        return value.strip()

    @staticmethod
    def _stop_process(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass
        except OSError:
            pass

    def run(
        self,
        roots: list[Path],
        *,
        overrides: dict[str, dict[str, Any]] | None = None,
        progress: Callable[[dict[str, Any]], None] | None = None,
        control: ScanControl | None = None,
    ) -> dict[str, Any]:
        control = control or ScanControl()
        command = python_module_child_command("melodex.scan_worker")
        env = os.environ.copy()

        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )

        messages: queue.Queue[str | None] = queue.Queue()
        stderr_lines: list[str] = []

        def read_stdout() -> None:
            stream = process.stdout
            if stream is None:
                messages.put(None)
                return
            try:
                for line in stream:
                    messages.put(line)
            finally:
                messages.put(None)

        def read_stderr() -> None:
            stream = process.stderr
            if stream is None:
                return
            for line in stream:
                if len(stderr_lines) < 40:
                    stderr_lines.append(line.rstrip())

        threading.Thread(
            target=read_stdout,
            name="melodex-scan-worker-stdout",
            daemon=True,
        ).start()
        threading.Thread(
            target=read_stderr,
            name="melodex-scan-worker-stderr",
            daemon=True,
        ).start()

        request = {
            "roots": [str(Path(root)) for root in roots],
            "overrides": dict(overrides or {}),
            "index_path": str(self.index_path),
        }
        if not self._write_message(process, request):
            self._stop_process(process)
            raise IsolatedScanError("could not start library scan worker")

        pause_sent = False
        cancel_sent = False
        cancel_started = 0.0
        result: dict[str, Any] | None = None
        error = ""
        stdout_closed = False

        try:
            while True:
                paused = bool(control.paused)
                if paused != pause_sent and not cancel_sent:
                    self._write_message(
                        process,
                        {"command": "pause" if paused else "resume"},
                    )
                    pause_sent = paused

                if control.cancelled and not cancel_sent:
                    cancel_sent = True
                    cancel_started = time.monotonic()
                    self._write_message(process, {"command": "cancel"})

                if (
                    cancel_sent
                    and process.poll() is None
                    and time.monotonic() - cancel_started >= self.cancel_grace_seconds
                ):
                    self._stop_process(process)
                    if progress is not None:
                        progress(
                            {
                                "phase": "cancelled",
                                "hard_cancelled": True,
                                "completed": 0,
                                "total": 0,
                            }
                        )
                    return self._cancelled_snapshot(hard_cancelled=True)

                try:
                    line = messages.get(timeout=0.05)
                except queue.Empty:
                    line = ...

                if line is None:
                    stdout_closed = True
                elif line is not ...:
                    text = str(line).strip()
                    if text:
                        try:
                            message = json.loads(text)
                        except json.JSONDecodeError:
                            continue
                        kind = str(message.get("type") or "")
                        if kind == "progress":
                            payload = dict(message.get("payload") or {})
                            if progress is not None:
                                progress(payload)
                        elif kind == "result":
                            result = dict(message.get("payload") or {})
                        elif kind == "error":
                            error = str(message.get("error") or "scan worker failed")

                returncode = process.poll()
                if result is not None:
                    if returncode is None:
                        try:
                            process.wait(timeout=1.0)
                        except subprocess.TimeoutExpired:
                            self._stop_process(process)
                    return result

                if returncode is not None and (stdout_closed or messages.empty()):
                    if cancel_sent:
                        return self._cancelled_snapshot(hard_cancelled=False)
                    detail = error or "\n".join(stderr_lines[-8:]).strip()
                    safe_detail = self._safe_error_detail(detail, roots)
                    raise IsolatedScanError(
                        safe_detail
                        or f"library scan worker exited with code {returncode}"
                    )
        finally:
            if process.poll() is None:
                self._stop_process(process)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass


__all__ = ["IsolatedLibraryScanRunner", "IsolatedScanError"]
