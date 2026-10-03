from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from .child_host import restore_child_stdio
from .library_index import LocalLibraryIndex
from .library_scan import ScanControl
from .providers.local_files import LocalFilesProvider


SCAN_CHILD_FLAG = "--melodex-library-scan-child"


def library_scan_child_command() -> list[str]:
    """Return a command that starts the isolated built-in scan worker."""
    if getattr(sys, "frozen", False):
        return [sys.executable, SCAN_CHILD_FLAG]
    run_py = Path(__file__).resolve().parents[1] / "run.py"
    return [sys.executable, "-u", str(run_py), SCAN_CHILD_FLAG]


def _write_message(stream: Any, payload: dict[str, Any]) -> None:
    stream.write(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str)
        + "\n"
    )
    stream.flush()


def _load_overrides(data_dir: Path) -> dict[str, dict[str, Any]]:
    path = Path(data_dir) / "local-metadata-overrides.json"
    try:
        raw = json.loads(path.read_text("utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): dict(value)
        for key, value in raw.items()
        if isinstance(value, dict)
    }


def run_library_scan_child() -> int:
    """Run one local-library scan entirely outside the GUI process."""
    if not restore_child_stdio():
        return 2

    line = sys.stdin.readline()
    if not line:
        print("Missing library scan request", file=sys.stderr, flush=True)
        return 2
    try:
        request = json.loads(line)
    except json.JSONDecodeError:
        print("Invalid library scan request", file=sys.stderr, flush=True)
        return 2
    if not isinstance(request, dict):
        print("Invalid library scan request payload", file=sys.stderr, flush=True)
        return 2

    data_dir = Path(str(request.get("data_dir") or "")).expanduser()
    roots = [
        Path(str(value)).expanduser()
        for value in list(request.get("roots") or [])
        if str(value or "").strip()
    ]
    if not str(data_dir):
        print("Missing library scan data directory", file=sys.stderr, flush=True)
        return 2

    control = ScanControl()

    def read_controls() -> None:
        for raw in sys.stdin:
            try:
                command = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(command, dict):
                continue
            action = str(command.get("type") or "")
            if action == "pause":
                control.pause()
            elif action == "resume":
                control.resume()
            elif action == "cancel":
                control.cancel()

    threading.Thread(
        target=read_controls,
        name="melodex-scan-control",
        daemon=True,
    ).start()

    try:
        index = LocalLibraryIndex(data_dir / "library-index.sqlite3")
        # Reconcile configured roots inside the disposable worker so a stale
        # worker from an earlier root set cannot leave orphaned cached roots
        # behind after the fresh scan starts.
        index.sync_roots(roots)
        provider = LocalFilesProvider(
            roots,
            _load_overrides(data_dir),
            scan_on_init=False,
        )
        cached = index.load_scan_cache(roots)
        resume_cache = index.load_resume_cache(roots)
        if resume_cache:
            cached.update(resume_cache)
        cached_directories = index.load_directory_manifests(roots)
        generation_id = index.begin_scan_generation(roots)
        checkpoint_batch: list[dict[str, Any]] = []

        def flush_checkpoints() -> None:
            if not checkpoint_batch:
                return
            index.stage_scan_records(
                generation_id,
                roots,
                list(checkpoint_batch),
            )
            checkpoint_batch.clear()

        def checkpoint(record: dict[str, Any]) -> None:
            checkpoint_batch.append(dict(record or {}))
            if len(checkpoint_batch) >= 64:
                flush_checkpoints()

        def progress(payload: dict[str, Any]) -> None:
            _write_message(
                sys.stdout,
                {"type": "progress", "payload": dict(payload or {})},
            )

        snapshot = provider.scan_snapshot(
            roots,
            progress=progress,
            control=control,
            cached_entries=cached,
            cached_directories=cached_directories,
            collect_tracks=False,
            checkpoint=checkpoint,
        )
        metrics = dict(snapshot.get("metrics") or {})
        metrics["process_isolated"] = True
        snapshot["metrics"] = metrics
        if bool(snapshot.get("cancelled")) or control.cancelled:
            flush_checkpoints()
            index.finish_scan_generation(
                generation_id,
                status="cancelled",
            )
            snapshot["cancelled"] = True
            snapshot.pop("index_records", None)
            snapshot.pop("directory_manifests", None)
            snapshot.setdefault("metrics", {})["resume_staged"] = len(
                resume_cache
            )
            _write_message(
                sys.stdout,
                {"type": "result", "payload": snapshot},
            )
            return 0

        progress(
            {
                "phase": "saving",
                "audio_files_seen": int(
                    (snapshot.get("metrics") or {}).get("audio_files_seen") or 0
                ),
            }
        )
        flush_checkpoints()
        persistence = index.replace_scan(
            roots,
            snapshot,
            cancelled=lambda: control.cancelled,
        )
        if bool(persistence.get("cancelled")):
            index.finish_scan_generation(
                generation_id,
                status="cancelled",
            )
            result = {
                "tracks": [],
                "metrics": dict(snapshot.get("metrics") or {}),
                "changes": dict(snapshot.get("changes") or {}),
                "root_states": list(snapshot.get("root_states") or []),
                "cancelled": True,
            }
            _write_message(
                sys.stdout,
                {"type": "result", "payload": result},
            )
            return 0

        index.finish_scan_generation(
            generation_id,
            status="completed",
        )
        result = dict(snapshot)
        result["persistence"] = dict(persistence or {})
        result.setdefault("metrics", {})["resume_staged"] = len(resume_cache)
        # Persistence-only scan mode keeps just one collection-sized record
        # set. Release it before hydrating the completed UI catalog from SQLite
        # so the child does not retain raw persistence rows and final tracks at
        # the same time.
        result.pop("index_records", None)
        result.pop("directory_manifests", None)
        snapshot.pop("index_records", None)
        snapshot.pop("directory_manifests", None)
        result["tracks"] = provider.prepare_cached_tracks(index.load_tracks(roots))
        _write_message(
            sys.stdout,
            {"type": "result", "payload": result},
        )
        return 0
    except BaseException as exc:
        try:
            if "generation_id" in locals():
                if "checkpoint_batch" in locals():
                    flush_checkpoints()
                index.finish_scan_generation(
                    generation_id,
                    status="error",
                )
        except Exception:
            pass
        _write_message(
            sys.stdout,
            {"type": "error", "error": f"{type(exc).__name__}: {exc}"},
        )
        return 1


def maybe_run_library_scan_child_from_argv(
    argv: Sequence[str] | None = None,
) -> int | None:
    values = list(sys.argv[1:] if argv is None else argv)
    if not values or values[0] != SCAN_CHILD_FLAG:
        return None
    return run_library_scan_child()


class LibraryScanProcess:
    """Supervise a disposable scan subprocess.

    Progress/result callbacks run on a reader thread. Callers such as Qt should
    bridge those callbacks through signals before touching UI state.
    """

    def __init__(
        self,
        data_dir: Path,
        roots: list[Path],
        *,
        on_progress: Callable[[dict[str, Any]], None],
        on_done: Callable[[dict[str, Any]], None],
        on_error: Callable[[str], None],
        command: Sequence[str] | None = None,
        hard_cancel_after: float = 1.5,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.roots = [Path(root) for root in roots]
        self.on_progress = on_progress
        self.on_done = on_done
        self.on_error = on_error
        self.command = list(command or library_scan_child_command())
        self.hard_cancel_after = max(0.0, float(hard_cancel_after))

        self._process: subprocess.Popen[str] | None = None
        self._write_lock = threading.Lock()
        self._finish_lock = threading.Lock()
        self._finished = False
        self._cancel_requested = False
        self._hard_cancelled = False
        self._paused = False
        self._stderr_tail: list[str] = []

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def running(self) -> bool:
        process = self._process
        return bool(process is not None and process.poll() is None and not self._finished)

    @property
    def pid(self) -> int | None:
        return int(self._process.pid) if self._process is not None else None

    def start(self) -> None:
        if self._process is not None:
            raise RuntimeError("Library scan process has already been started")
        kwargs: dict[str, Any] = {}
        if os.name == "nt":
            creation_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if creation_flag:
                kwargs["creationflags"] = creation_flag

        self._process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **kwargs,
        )
        request = {
            "data_dir": str(self.data_dir),
            "roots": [str(root) for root in self.roots],
        }
        if not self._send(request, allow_finished=True):
            try:
                self._process.terminate()
            except OSError:
                pass
            raise RuntimeError("Could not send request to library scan worker")
        threading.Thread(
            target=self._read_stderr,
            name="melodex-library-scan-stderr",
            daemon=True,
        ).start()
        threading.Thread(
            target=self._read_stdout,
            name="melodex-library-scan-reader",
            daemon=True,
        ).start()

    def _send(self, payload: dict[str, Any], *, allow_finished: bool = False) -> bool:
        if self._finished and not allow_finished:
            return False
        process = self._process
        stream = process.stdin if process is not None else None
        if stream is None:
            return False
        try:
            with self._write_lock:
                _write_message(stream, payload)
            return True
        except (BrokenPipeError, OSError, ValueError):
            return False

    def pause(self) -> None:
        if not self.running:
            return
        self._paused = True
        self._send({"type": "pause"})

    def resume(self) -> None:
        if not self.running:
            return
        self._paused = False
        self._send({"type": "resume"})

    def cancel(self, *, hard_after: float | None = None) -> None:
        if self._finished:
            return
        self._cancel_requested = True
        self._paused = False
        self._send({"type": "cancel"})
        timeout = (
            self.hard_cancel_after
            if hard_after is None
            else max(0.0, float(hard_after))
        )
        threading.Thread(
            target=self._enforce_cancel,
            args=(timeout,),
            name="melodex-library-scan-cancel",
            daemon=True,
        ).start()

    def terminate_now(self) -> None:
        """Terminate a live worker immediately, used during application exit."""
        self._cancel_requested = True
        process = self._process
        if process is None or process.poll() is not None:
            return
        self._hard_cancelled = True
        try:
            process.terminate()
        except OSError:
            pass

    def shutdown(self, timeout: float = 0.25) -> None:
        """Synchronously stop the worker during application shutdown."""
        self._cancel_requested = True
        self._paused = False
        process = self._process
        if process is None or process.poll() is not None:
            return
        self._hard_cancelled = True
        try:
            process.terminate()
        except OSError:
            return
        try:
            process.wait(timeout=max(0.0, float(timeout)))
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            process.kill()
        except OSError:
            return
        try:
            process.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            pass

    def _enforce_cancel(self, timeout: float) -> None:
        process = self._process
        if process is None:
            return
        try:
            process.wait(timeout=timeout)
            return
        except subprocess.TimeoutExpired:
            pass

        self._hard_cancelled = True
        try:
            process.terminate()
        except OSError:
            return
        try:
            process.wait(timeout=0.75)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            process.kill()
        except OSError:
            pass

    def _read_stderr(self) -> None:
        process = self._process
        stream = process.stderr if process is not None else None
        if stream is None:
            return
        for line in stream:
            value = line.rstrip()
            if not value:
                continue
            self._stderr_tail.append(value)
            if len(self._stderr_tail) > 40:
                del self._stderr_tail[:-40]

    def _read_stdout(self) -> None:
        process = self._process
        stream = process.stdout if process is not None else None
        if stream is None:
            self._finish_error("Library scan worker did not provide stdout")
            return

        for line in stream:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            kind = str(message.get("type") or "")
            if kind == "progress":
                try:
                    self.on_progress(dict(message.get("payload") or {}))
                except Exception:
                    pass
            elif kind == "result":
                self._finish_done(dict(message.get("payload") or {}))
            elif kind == "error":
                self._finish_error(str(message.get("error") or "Library scan failed"))

        try:
            returncode = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            returncode = None

        if self._finished:
            return
        if self._cancel_requested:
            self._finish_done(
                {
                    "tracks": [],
                    "metrics": {"process_isolated": True},
                    "changes": {},
                    "cancelled": True,
                    "hard_cancelled": bool(self._hard_cancelled),
                }
            )
            return
        detail = "\n".join(self._stderr_tail[-8:]).strip()
        suffix = f": {detail}" if detail else ""
        self._finish_error(
            f"Library scan worker exited unexpectedly"
            + (f" ({returncode})" if returncode is not None else "")
            + suffix
        )

    def _finish_done(self, payload: dict[str, Any]) -> None:
        with self._finish_lock:
            if self._finished:
                return
            self._finished = True
        self._paused = False
        try:
            self.on_done(dict(payload or {}))
        except Exception:
            pass

    def _finish_error(self, error: str) -> None:
        with self._finish_lock:
            if self._finished:
                return
            self._finished = True
        self._paused = False
        try:
            self.on_error(str(error or "Library scan failed"))
        except Exception:
            pass


__all__ = [
    "LibraryScanProcess",
    "SCAN_CHILD_FLAG",
    "library_scan_child_command",
    "maybe_run_library_scan_child_from_argv",
    "run_library_scan_child",
]
