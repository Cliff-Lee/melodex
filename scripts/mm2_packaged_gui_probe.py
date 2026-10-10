#!/usr/bin/env python3
"""Validate MM2's real packaged Qt controls using an isolated synthetic map.

Not a substitute for hands-on local/NAS audio playback, or a release approval.
The test fixture cannot initiate audio: it only verifies UI behaviour and
signals inside the frozen Mac/Windows/Linux executable.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run_probe(
    executable: Path,
    *,
    appimage: bool = False,
    output: Path | None = None,
    timeout_seconds: float = 90.0,
) -> dict:
    exe = executable.resolve()
    if not exe.is_file():
        raise FileNotFoundError(f"Packaged Melodex executable not found: {exe}")
    with tempfile.TemporaryDirectory(prefix="melodex-mm2-package-") as tmp:
        root = Path(tmp)
        data_dir = root / "data"
        result_path = root / "result.json"
        env = dict(os.environ)
        env.update({
            "MELODEX_DATA_DIR": str(data_dir),
            "MELODEX_MM2_PACKAGE_PROBE": str(result_path),
            "QT_QPA_PLATFORM": "offscreen",
            "HOME": str(root),
            "XDG_DATA_HOME": str(root / "xdg-data"),
            "XDG_CONFIG_HOME": str(root / "xdg-config"),
            "XDG_CACHE_HOME": str(root / "xdg-cache"),
        })
        command = [str(exe)]
        if appimage:
            command.append("--appimage-extract-and-run")
        try:
            launched = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True,
                timeout=max(10.0, float(timeout_seconds)),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"MM2 packaged GUI did not close within {timeout_seconds}s"
            ) from exc

        if not result_path.is_file():
            raise RuntimeError(
                "Packaged Melodex did not write MM2 acceptance evidence. "
                f"Exit code={launched.returncode}\n"
                f"stdout={launched.stdout[-1200:]}\n"
                f"stderr={launched.stderr[-1800:]}"
            )
        result = json.loads(result_path.read_text("utf-8"))
        result.update({
            "executable_name": exe.name,
            "appimage": bool(appimage),
            "platform": sys.platform,
            "exit_code": launched.returncode,
            "clean_shutdown": (
                launched.returncode == 0
                and "shared QObject was deleted directly" not in launched.stderr
            ),
        })
        screenshot = result_path.with_suffix(".png")
        if not screenshot.is_file() or screenshot.stat().st_size < 1000:
            raise RuntimeError("Packaged MM2 screenshot missing or empty")

        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            screenshot_dest = output.with_suffix(".png")
            screenshot_dest.write_bytes(screenshot.read_bytes())
            result["screenshot"] = str(screenshot_dest)
            output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

        if (not result.get("passed")
                or not result.get("clean_shutdown")
                or not all(result.get("checks", {}).values())):
            raise RuntimeError(
                "MM2 packaged GUI failed an acceptance check:\n"
                + json.dumps(result, indent=2)
                + f"\nstderr: {launched.stderr[-1400:]}"
            )
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--appimage", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()
    result = run_probe(
        args.executable,
        appimage=args.appimage,
        output=args.output,
        timeout_seconds=args.timeout,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
