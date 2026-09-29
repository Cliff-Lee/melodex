from __future__ import annotations

import hashlib
from pathlib import Path


def instance_server_name(data_dir: Path) -> str:
    digest = hashlib.sha256(
        str(Path(data_dir).resolve()).encode("utf-8")
    ).hexdigest()[:16]
    return f"melodex-{digest}"


__all__ = ["instance_server_name"]
