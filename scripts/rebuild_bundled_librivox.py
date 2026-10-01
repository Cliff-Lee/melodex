from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "desktop" / "bundled_provider_sources" / "librivox"
LICENSE = ROOT / "LICENSE"
EXPECTED_VERSION = "0.1.4"


def rebuild(destination: Path) -> None:
    source_files = {
        "LICENSE": LICENSE,
        "README.md": SOURCE / "README.md",
        "manifest.json": SOURCE / "manifest.json",
        "provider.py": SOURCE / "provider.py",
    }
    for name, path in source_files.items():
        if not path.is_file():
            raise RuntimeError(f"Missing LibriVox bundle source {name}: {path}")

    manifest = json.loads(source_files["manifest.json"].read_text("utf-8"))
    if manifest.get("id") != "org.melodex.librivox":
        raise RuntimeError("Unexpected LibriVox provider id")
    if str(manifest.get("version") or "") != EXPECTED_VERSION:
        raise RuntimeError("LibriVox source manifest version mismatch")
    if manifest.get("entrypoints", {}).get("python") != "provider.py":
        raise RuntimeError("LibriVox source manifest entrypoint mismatch")

    provider_source = source_files["provider.py"].read_text("utf-8")
    compile(provider_source, "librivox:provider.py", "exec")
    if f'VERSION = "{EXPECTED_VERSION}"' not in provider_source:
        raise RuntimeError("LibriVox provider source version mismatch")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zout:
        for name in ("LICENSE", "README.md", "manifest.json", "provider.py"):
            path = source_files[name]
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 1, 9, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            zout.writestr(info, path.read_bytes())

    with zipfile.ZipFile(destination, "r") as check:
        bad = check.testzip()
        if bad:
            raise RuntimeError(f"CRC validation failed for {bad}")
        rebuilt_manifest = json.loads(check.read("manifest.json"))
        if rebuilt_manifest.get("version") != EXPECTED_VERSION:
            raise RuntimeError("rebuilt manifest version mismatch")
        compile(check.read("provider.py"), f"{destination}:provider.py", "exec")

    print(f"Rebuilt and validated {destination} ({destination.stat().st_size} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    rebuild(args.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
