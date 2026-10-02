from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any

from .library_index import LocalLibraryIndex
from .library_scan import ScanControl
from .providers.local_files import LocalFilesProvider


def _send(payload: dict[str, Any]) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
        flush=True,
    )


def _control_reader(control: ScanControl) -> None:
    for line in sys.stdin:
        text = line.strip()
        if not text:
            continue
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            continue
        command = str(message.get("command") or "")
        if command == "pause":
            control.pause()
        elif command == "resume":
            control.resume()
        elif command == "cancel":
            control.cancel()
            return


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if values and values[0] == "--smoke":
        _send({"scan_worker_smoke": True})
        return 0

    first = sys.stdin.readline()
    if not first:
        _send({"type": "error", "error": "missing scan request"})
        return 2

    try:
        request = json.loads(first)
        roots = [Path(value) for value in list(request.get("roots") or [])]
        overrides = {
            str(key): dict(value)
            for key, value in dict(request.get("overrides") or {}).items()
            if isinstance(value, dict)
        }
        raw_index_path = str(request.get("index_path") or "").strip()
        if not raw_index_path:
            raise ValueError("missing library index path")
        index_path = Path(raw_index_path)
    except Exception as exc:
        _send({"type": "error", "error": f"invalid scan request: {exc}"})
        return 2

    control = ScanControl()
    command_thread = threading.Thread(
        target=_control_reader,
        args=(control,),
        name="melodex-scan-control",
        daemon=True,
    )
    command_thread.start()

    try:
        index = LocalLibraryIndex(index_path)
        cache = index.load_scan_cache(roots)
        provider = LocalFilesProvider(
            roots,
            overrides,
            scan_on_init=False,
        )
        snapshot = provider.scan_snapshot(
            roots,
            progress=lambda payload: _send(
                {"type": "progress", "payload": dict(payload or {})}
            ),
            control=control,
            cached_entries=cache,
        )
        _send({"type": "result", "payload": snapshot})
        return 0
    except Exception as exc:
        _send({"type": "error", "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
