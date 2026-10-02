from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


EXPECTED = {
    "Internet-Archive-Audio-0.1.1.mdxprovider": (
        "org.melodex.internetarchive.audio",
        "0.1.1",
    ),
    "LibriVox-0.1.5.mdxprovider": ("org.melodex.librivox", "0.1.5"),
    "NicheDB-Radio-0.1.2.mdxprovider": ("org.melodex.nichedb.radio", "0.1.2"),
    "Radio-Browser-0.1.2.mdxprovider": ("org.melodex.radiobrowser", "0.1.2"),
    "SomaFM-0.1.1.mdxprovider": ("org.melodex.somafm", "0.1.1"),
    "Wikimedia-Commons-Audio-0.1.1.mdxprovider": (
        "org.melodex.wikimedia.commons.audio",
        "0.1.1",
    ),
    "ccMixter-0.1.3.mdxprovider": ("org.melodex.ccmixter", "0.1.3"),
}


def check_payload(root: Path) -> None:
    roots = [path for path in root.rglob("bundled_providers") if path.is_dir()]
    packages: dict[str, Path] = {}
    for bundle_root in roots:
        packages.update(
            (path.name, path)
            for path in bundle_root.glob("*.mdxprovider")
            if path.is_file()
        )

    missing = sorted(set(EXPECTED) - set(packages))
    if missing:
        raise SystemExit(
            f"Bundled provider payload is missing {', '.join(missing)} under {root}"
        )
    unexpected = sorted(set(packages) - set(EXPECTED))
    if unexpected:
        raise SystemExit(
            f"Bundled provider payload has unexpected packages: "
            f"{', '.join(unexpected)} under {root}"
        )

    for filename, (expected_id, expected_version) in EXPECTED.items():
        try:
            with zipfile.ZipFile(packages[filename]) as archive:
                manifest_names = [
                    name
                    for name in archive.namelist()
                    if not name.endswith("/") and Path(name).name == "manifest.json"
                ]
                if len(manifest_names) != 1:
                    raise ValueError("expected one manifest.json")
                manifest = json.loads(archive.read(manifest_names[0]))
                entrypoint = str(
                    ((manifest.get("entrypoints") or {}).get("python") or "")
                )
                if (
                    not entrypoint
                    or Path(entrypoint).is_absolute()
                    or ".." in Path(entrypoint).parts
                ):
                    raise ValueError("invalid Python entrypoint")
                if entrypoint not in archive.namelist():
                    raise ValueError("Python entrypoint is absent")
                compile(archive.read(entrypoint), f"{filename}:{entrypoint}", "exec")
        except Exception as exc:
            raise SystemExit(f"Invalid bundled provider {filename}: {exc}") from exc
        if (
            manifest.get("id") != expected_id
            or str(manifest.get("version")) != expected_version
        ):
            raise SystemExit(
                f"{filename} must declare {expected_id} {expected_version}; "
                f"found {manifest.get('id')} {manifest.get('version')}"
            )

    print(f"Bundled provider payload check passed: {len(EXPECTED)} providers")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify bundled provider archives in a source or frozen app tree."
    )
    parser.add_argument("root", type=Path, help="source package or PyInstaller output root")
    args = parser.parse_args()
    if not args.root.exists():
        raise SystemExit(f"Payload root does not exist: {args.root}")
    check_payload(args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
