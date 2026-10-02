from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

CHILD_FLAG = "--melodex-python-child"
SCAN_CHILD_FLAG = "--melodex-library-scan-child"


def _communicate(
    process: subprocess.Popen[str],
    payload: dict,
    *,
    label: str,
    timeout: float = 20,
) -> tuple[str, str]:
    try:
        return process.communicate(json.dumps(payload) + "\n", timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        raise SystemExit(
            f"{label} did not complete within {timeout:.0f} seconds\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )


def _smoke_python_child(executable: Path, temporary: Path) -> None:
    script = temporary / "worker.py"
    script.write_text(
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    request = json.loads(line)\n"
        "    print(json.dumps({'jsonrpc':'2.0','id':request.get('id'),"
        "'result':{'frozen_child':True}}), flush=True)\n"
        "    break\n",
        encoding="utf-8",
    )
    request = {"jsonrpc": "2.0", "id": 1, "method": "smoke", "params": {}}
    process = subprocess.Popen(
        [str(executable), CHILD_FLAG, str(script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    stdout, stderr = _communicate(
        process,
        request,
        label="frozen Python child",
        timeout=15,
    )
    lines = [line for line in stdout.splitlines() if line.strip()]
    if process.returncode != 0 or not lines:
        raise SystemExit(
            f"frozen child failed with exit {process.returncode}\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )
    try:
        response = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise SystemExit(f"frozen child emitted invalid JSON: {stdout}") from exc
    expected = {"jsonrpc": "2.0", "id": 1, "result": {"frozen_child": True}}
    if response != expected:
        raise SystemExit(f"unexpected frozen child response: {response!r}")


def _smoke_library_scan_child(executable: Path, temporary: Path) -> None:
    root = temporary / "music"
    root.mkdir()
    (root / "smoke.flac").write_bytes(b"not-a-real-flac")
    data_dir = temporary / "data"

    process = subprocess.Popen(
        [str(executable), SCAN_CHILD_FLAG],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    stdout, stderr = _communicate(
        process,
        {
            "data_dir": str(data_dir),
            "roots": [str(root)],
        },
        label="frozen library scan child",
    )
    messages = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            messages.append(value)

    results = [
        dict(message.get("payload") or {})
        for message in messages
        if message.get("type") == "result"
    ]
    if process.returncode != 0 or not results:
        raise SystemExit(
            f"frozen scan child failed with exit {process.returncode}\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )
    result = results[-1]
    if bool(result.get("cancelled")) or len(list(result.get("tracks") or [])) != 1:
        raise SystemExit(f"unexpected frozen scan result: {result!r}")
    if not (data_dir / "library-index.sqlite3").is_file():
        raise SystemExit("frozen scan child did not persist library-index.sqlite3")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: frozen_child_smoke.py /path/to/Melodex-executable")
    executable = Path(sys.argv[1]).resolve()
    if not executable.is_file():
        raise SystemExit(f"frozen application executable not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="melodex-child-smoke-") as temporary:
        folder = Path(temporary)
        _smoke_python_child(executable, folder)
        _smoke_library_scan_child(executable, folder)

    print(f"Frozen child RPC + library scan smoke passed: {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
