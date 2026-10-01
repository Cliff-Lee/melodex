from __future__ import annotations

import argparse
import json
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
    replacements = {
        'VERSION="0.1.2"': 'VERSION="0.1.3"',
        "def _bytes(url,headers=None,timeout=22,attempts=3):":
            "def _bytes(url,headers=None,timeout=28,attempts=1):",
        'books=_fetch({key:q,"limit":"8","offset":"0"})':
            'books=_fetch({key:q,"limit":"1","offset":"0"})',
    }
    for old, new in replacements.items():
        if old not in provider:
            raise RuntimeError(f"Expected LibriVox source fragment is missing: {old}")
        provider = provider.replace(old, new, 1)
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
