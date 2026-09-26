from __future__ import annotations

import os
import sys
from pathlib import Path


def app_data_dir() -> Path:
    if sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "Melodex"
    elif os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home())) / "Melodex"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "melodex"
    root.mkdir(parents=True, exist_ok=True)
    return root
