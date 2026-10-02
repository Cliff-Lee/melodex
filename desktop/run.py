import os
import sys

from melodex.runtime_smoke import maybe_run_runtime_smoke_from_argv
from melodex.library_scan_process import maybe_run_library_scan_child_from_argv
from melodex.child_host import maybe_run_child_from_argv

# Internal smoke probes, library scanner and provider/plugin workers must be
# dispatched before Qt imports or GUI startup.
_runtime_smoke_exit = maybe_run_runtime_smoke_from_argv()
if _runtime_smoke_exit is not None:
    raise SystemExit(_runtime_smoke_exit)

_scan_exit = maybe_run_library_scan_child_from_argv()
if _scan_exit is not None:
    raise SystemExit(_scan_exit)

_child_exit = maybe_run_child_from_argv()
if _child_exit is not None:
    raise SystemExit(_child_exit)

# On macOS, Qt/AVFoundation can silently fail with some remote audio streams.
# Melodex uses Qt's FFmpeg backend together with its secure localhost
# playback gateway for reliable mixed-source playback.
if sys.platform == "darwin":
    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")

from melodex.app import main

if __name__ == "__main__":
    raise SystemExit(main())
