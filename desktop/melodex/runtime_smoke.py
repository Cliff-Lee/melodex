from __future__ import annotations

import json
import ssl
import sys
from pathlib import Path
from typing import Sequence

RUNTIME_SMOKE_FLAG = "--melodex-runtime-smoke"


def runtime_report() -> dict[str, object]:
    """Exercise non-Qt runtime dependencies that frozen Melodex relies on."""
    import keyring  # type: ignore
    import numpy as np
    import requests

    values = np.asarray([0.0, 1.0, 0.5, 0.25], dtype=np.float32)
    spectrum = np.fft.rfft(values)
    percentile = float(np.percentile(values, 75))

    session = requests.Session()
    ca_path = Path(requests.certs.where())
    backend = keyring.get_keyring()
    priority = float(getattr(backend, "priority", 0) or 0)

    return {
        "numpy_version": str(np.__version__),
        "numpy_fft_bins": int(len(spectrum)),
        "numpy_percentile": percentile,
        "requests_version": str(requests.__version__),
        "ca_bundle_exists": ca_path.is_file(),
        "openssl": ssl.OPENSSL_VERSION,
        "keyring_backend": (
            f"{backend.__class__.__module__}.{backend.__class__.__name__}"
        ),
        "keyring_priority": priority,
        "platform": sys.platform,
    }


def maybe_run_runtime_smoke_from_argv(
    argv: Sequence[str] | None = None,
) -> int | None:
    values = list(sys.argv[1:] if argv is None else argv)
    if not values or values[0] != RUNTIME_SMOKE_FLAG:
        return None

    try:
        report = runtime_report()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            ),
            flush=True,
        )
        return 1

    ok = bool(report.get("ca_bundle_exists"))
    # macOS and Windows release builds are expected to retain their native
    # system-keyring backend after removing blanket keyring collection.
    if sys.platform in {"darwin", "win32"}:
        ok = ok and float(report.get("keyring_priority") or 0) > 0

    print(json.dumps({"ok": ok, **report}), flush=True)
    return 0 if ok else 2


__all__ = [
    "RUNTIME_SMOKE_FLAG",
    "maybe_run_runtime_smoke_from_argv",
    "runtime_report",
]
