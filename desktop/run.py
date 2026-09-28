import os
import sys

# On macOS, Qt/AVFoundation can silently fail with some remote audio streams.
# Melodex uses Qt's FFmpeg backend together with its secure localhost
# playback gateway for reliable mixed-source playback.
if sys.platform == "darwin":
    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")

from melodex.app import main

if __name__ == "__main__":
    raise SystemExit(main())
