from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

CHILD_FLAG = "--melodex-python-child"
MODULE_CHILD_FLAG = "--melodex-python-module-child"


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: frozen_child_smoke.py /path/to/Melodex-executable")
    executable = Path(sys.argv[1]).resolve()
    if not executable.is_file():
        raise SystemExit(f"frozen application executable not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="melodex-child-smoke-") as temporary:
        script = Path(temporary) / "worker.py"
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
        try:
            stdout, stderr = process.communicate(json.dumps(request) + "\n", timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            raise SystemExit(
                f"frozen child did not complete within 15 seconds\n"
                f"stdout: {stdout}\nstderr: {stderr}"
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
    module_process = subprocess.run(
        [
            str(executable),
            MODULE_CHILD_FLAG,
            "melodex.scan_worker",
            "--smoke",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    module_lines = [
        line for line in module_process.stdout.splitlines()
        if line.strip()
    ]
    if module_process.returncode != 0 or not module_lines:
        raise SystemExit(
            "frozen scan-worker module child failed "
            f"with exit {module_process.returncode}\n"
            f"stdout: {module_process.stdout}\n"
            f"stderr: {module_process.stderr}"
        )
    try:
        module_response = json.loads(module_lines[-1])
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"frozen scan-worker child emitted invalid JSON: {module_process.stdout}"
        ) from exc
    if module_response != {"scan_worker_smoke": True}:
        raise SystemExit(
            f"unexpected frozen scan-worker response: {module_response!r}"
        )

    print(f"Frozen child RPC + scan-worker smoke passed: {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
