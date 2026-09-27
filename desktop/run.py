from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


PROVIDER_SCRIPT_FLAG = "--melodex-provider-script"


def _restore_stdio() -> None:
    """PyInstaller windowed apps may set stdio to None.

    Provider JSON-RPC uses stdin/stdout, so restore the pipe descriptors
    supplied by subprocess.Popen when running in provider mode.
    """
    specs = (
        ("stdin", 0, "r"),
        ("stdout", 1, "w"),
        ("stderr", 2, "w"),
    )

    for name, fd, mode in specs:
        if getattr(sys, name, None) is not None:
            continue
        try:
            stream = open(
                fd,
                mode,
                encoding="utf-8",
                errors="replace",
                buffering=1,
                closefd=False,
            )
            setattr(sys, name, stream)
        except Exception:
            pass


def _run_provider_if_requested() -> bool:
    if len(sys.argv) < 3 or sys.argv[1] != PROVIDER_SCRIPT_FLAG:
        return False

    script = Path(sys.argv[2]).expanduser().resolve()

    if not script.is_file():
        raise SystemExit(f"Provider script not found: {script}")

    _restore_stdio()

    # Make provider-local modules and vendored dependencies importable.
    folder = script.parent
    vendor = folder / "vendor"

    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

    if vendor.is_dir() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))

    sys.argv = [str(script), *sys.argv[3:]]
    runpy.run_path(str(script), run_name="__main__")
    return True


if __name__ == "__main__" and _run_provider_if_requested():
    raise SystemExit(0)


# Qt's AVFoundation backend can report successful playback while producing
# silence for some remote HTTP audio. FFmpeg + Melodex's playback gateway is
# the reliable macOS path.
if sys.platform == "darwin":
    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")


from melodex.app import main


if __name__ == "__main__":
    raise SystemExit(main())
