from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path
from typing import Sequence

CHILD_FLAG = "--melodex-python-child"


def python_child_command(script: Path) -> list[str]:
    """Return a command that runs a Python provider/plugin script safely.

    In a source checkout sys.executable is the Python interpreter.
    In a PyInstaller build sys.executable is the Melodex executable itself, so
    frozen builds re-enter Melodex with an explicit child-worker flag.
    """

    script = Path(script).resolve()
    if getattr(sys, "frozen", False):
        return [sys.executable, CHILD_FLAG, str(script)]
    return [sys.executable, "-u", str(script)]


def _line_buffer_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(line_buffering=True, write_through=True)
            except Exception:
                pass


def run_child_script(script: Path, argv: Sequence[str] = ()) -> int:
    """Execute a provider/plugin script inside the bundled Python runtime."""

    target = Path(script).resolve()
    if not target.is_file():
        print(f"Melodex child script not found: {target}", file=sys.stderr, flush=True)
        return 2

    folder = target.parent
    vendor = folder / "vendor"
    prepend = [str(folder)]
    if vendor.is_dir():
        prepend.insert(0, str(vendor))
    for value in reversed(prepend):
        if value not in sys.path:
            sys.path.insert(0, value)

    os.environ["MELODEX_CHILD_PROCESS"] = "1"
    os.environ["PYTHONUNBUFFERED"] = "1"
    _line_buffer_stdio()
    sys.argv = [str(target), *[str(value) for value in argv]]

    try:
        runpy.run_path(str(target), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return int(code)
        print(str(code), file=sys.stderr, flush=True)
        return 1
    except BaseException:
        import traceback

        traceback.print_exc(file=sys.stderr)
        return 1
    return 0


def maybe_run_child_from_argv(argv: Sequence[str] | None = None) -> int | None:
    """Handle frozen child-worker mode before QApplication is imported."""

    values = list(sys.argv[1:] if argv is None else argv)
    if not values or values[0] != CHILD_FLAG:
        return None
    if len(values) < 2:
        print("Melodex child-worker mode requires a script path", file=sys.stderr)
        return 2
    return run_child_script(Path(values[1]), values[2:])


__all__ = [
    "CHILD_FLAG",
    "python_child_command",
    "run_child_script",
    "maybe_run_child_from_argv",
]
