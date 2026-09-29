import os
import sys

from melodex.child_host import maybe_run_child_from_argv

# Frozen provider/plugin workers must be dispatched before Qt imports or GUI startup.
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
