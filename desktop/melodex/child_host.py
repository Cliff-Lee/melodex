from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path
from typing import Sequence, TextIO

CHILD_FLAG = "--melodex-python-child"
MODULE_CHILD_FLAG = "--melodex-python-module-child"


def _open_inherited_stdio(fd: int, mode: str) -> TextIO | None:
    """Recreate a text stream for a Popen-provided standard handle."""

    descriptor: int | None = None
    try:
        if os.name == "nt":
            import ctypes
            import msvcrt

            standard_handle = {0: -10, 1: -11, 2: -12}[fd]
            get_std_handle = ctypes.windll.kernel32.GetStdHandle
            get_std_handle.argtypes = [ctypes.c_ulong]
            get_std_handle.restype = ctypes.c_void_p
            handle = get_std_handle(ctypes.c_ulong(standard_handle & 0xFFFFFFFF))
            if handle is None or handle == ctypes.c_void_p(-1).value:
                return None
            flags = os.O_BINARY | (os.O_RDONLY if mode == "r" else os.O_WRONLY)
            descriptor = msvcrt.open_osfhandle(int(handle), flags)
        else:
            descriptor = os.dup(fd)
        return os.fdopen(
            descriptor,
            mode,
            encoding="utf-8",
            errors="replace",
            buffering=1,
        )
    except (AttributeError, OSError, ValueError):
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        return None


def _restore_child_stdio() -> bool:
    """Restore inherited pipes hidden by a windowed/frozen application."""

    for name, fd, mode in (
        ("stdin", 0, "r"),
        ("stdout", 1, "w"),
        ("stderr", 2, "w"),
    ):
        if getattr(sys, name, None) is not None:
            continue
        stream = _open_inherited_stdio(fd, mode)
        if stream is None:
            return False
        setattr(sys, name, stream)
    return True


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


def python_module_child_command(module: str) -> list[str]:
    """Return a command that runs a bundled Melodex module without GUI startup."""
    module = str(module or "").strip()
    if not module:
        raise ValueError("module name is required")
    if getattr(sys, "frozen", False):
        return [sys.executable, MODULE_CHILD_FLAG, module]
    return [sys.executable, "-u", "-m", module]


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

    if not _restore_child_stdio():
        return 2

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
    if not values:
        return None

    if values[0] == CHILD_FLAG:
        if len(values) < 2:
            if _restore_child_stdio():
                print("Melodex child-worker mode requires a script path", file=sys.stderr)
            return 2
        return run_child_script(Path(values[1]), values[2:])

    if values[0] == MODULE_CHILD_FLAG:
        if len(values) < 2:
            if _restore_child_stdio():
                print("Melodex module-child mode requires a module name", file=sys.stderr)
            return 2
        if not _restore_child_stdio():
            return 2
        _line_buffer_stdio()
        os.environ["MELODEX_CHILD_PROCESS"] = "1"
        os.environ["PYTHONUNBUFFERED"] = "1"
        module = str(values[1])
        sys.argv = [module, *[str(value) for value in values[2:]]]
        try:
            runpy.run_module(module, run_name="__main__", alter_sys=True)
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

    return None


__all__ = [
    "CHILD_FLAG",
    "MODULE_CHILD_FLAG",
    "python_child_command",
    "python_module_child_command",
    "run_child_script",
    "maybe_run_child_from_argv",
]
