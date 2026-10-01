from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path


# Rebuild from the known-good public 0.1.2 bundle; never hand-edit ZIP bytes.
def rebuild(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source, "r") as zin:
        files = {name: zin.read(name) for name in zin.namelist() if not name.endswith("/")}

    manifest = json.loads(files["manifest.json"].decode("utf-8"))
    manifest["version"] = "0.1.3"
    manifest["rpc_timeout_seconds"] = 40
    files["manifest.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")

    provider = files["provider.py"].decode("utf-8")

    provider, version_count = re.subn(
        r'VERSION\s*=\s*["\']0\\.1\\.2["\']',
        'VERSION="0.1.3"',
        provider,
        count=1,
    )
    provider, timeout_count = re.subn(
        r'timeout\s*=\s*22\s*,\s*attempts\s*=\s*3',
        'timeout=28, attempts=1',
        provider,
        count=1,
    )
    provider, limit_count = re.subn(
        r'books\s*=\s*_fetch\(\{key:q,\s*"limit":"8",\s*"offset":"0"\}\)',
        'books=_fetch({key:q,"limit":"1","offset":"0"})',
        provider,
        count=1,
    )
    if (version_count, timeout_count, limit_count) != (1, 1, 1):
        raise RuntimeError(
            "Unexpected LibriVox source shape: "
            f"version={version_count}, timeout={timeout_count}, limit={limit_count}"
        )
    files["provider.py"] = provider.encode("utf-8")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zout:
        for name in ("LICENSE", "README.md", "manifest.json", "provider.py"):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 1, 8, 40, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 << 16)
            zout.writestr(info, files[name])

    with zipfile.ZipFile(destination, "r") as check:
        bad = check.testzip()
        if bad:
            raise RuntimeError(f"CRC validation failed for {bad}")
        rebuilt_manifest = json.loads(check.read("manifest.json"))
        if rebuilt_manifest.get("version") != "0.1.3":
            raise RuntimeError("rebuilt manifest version mismatch")
        compile(check.read("provider.py"), f"{destination}:provider.py", "exec")

    print(f"Rebuilt and validated {destination} ({destination.stat().st_size} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    rebuild(args.source, args.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
