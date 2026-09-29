import os
import sys

from melodex.child_host import maybe_run_child_from_argv

# Child providers/extensions must be handled before importing the GUI. In a
# PyInstaller build this executable is also the bundled Python runtime host.
child_exit = maybe_run_child_from_argv()
if child_exit is not None:
    raise SystemExit(child_exit)

# On macOS, Qt/AVFoundation can silently fail with some remote audio streams.
# Melodex uses Qt's FFmpeg backend together with its secure localhost
# playback gateway for reliable mixed-source playback.
if sys.platform == "darwin":
    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")

from melodex.app import main

if __name__ == "__main__":
    raise SystemExit(main())
