from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

from .validation import ManifestValidationError, load_manifest, validate_manifest

_TEMPLATE_MANIFEST = {
    "schema_version": 1,
    "id": "org.example.provider",
    "name": "Example Provider",
    "version": "0.1.0",
    "publisher": "Your Name or Organisation",
    "protocol_version": "1.0",
    "description": "Describe the user-authorized music source this provider connects to.",
    "capabilities": ["search", "track", "playback"],
    "permissions": {
        "network_hosts": ["api.example.org"],
        "offline_downloads": False,
        "local_files": False,
        "browser_auth": False,
        "lan_discovery": False,
    },
    "entrypoints": {},
}

_TEMPLATE_README = """# Example Melodex Provider\n\nDescribe the source, setup, authentication, permissions, and lawful basis for the integration.\n\n## Development\n\n1. Edit `manifest.json`.\n2. Implement MPP using `spec/openapi.yaml` or the local-process mapping.\n3. Run `melodex-provider validate .`.\n4. Run `melodex-provider pack .`.\n"""

_TEMPLATE_LICENSE = """Choose and include a license appropriate for your provider before distribution.\n"""


def command_init(args: argparse.Namespace) -> int:
    target = Path(args.directory).resolve()
    if target.exists() and any(target.iterdir()):
        print(f"error: target is not empty: {target}", file=sys.stderr)
        return 2
    target.mkdir(parents=True, exist_ok=True)
    manifest = dict(_TEMPLATE_MANIFEST)
    manifest["id"] = args.id
    manifest["name"] = args.name
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (target / "README.md").write_text(_TEMPLATE_README, encoding="utf-8")
    (target / "LICENSE").write_text(_TEMPLATE_LICENSE, encoding="utf-8")
    (target / "bin").mkdir(exist_ok=True)
    print(f"Created provider skeleton: {target}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.path)
        errors = validate_manifest(manifest, args.schema)
    except (ManifestValidationError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if errors:
        print("Manifest is invalid:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Manifest is valid.")
    return 0


def _safe_files(root: Path):
    skipped_dirs = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
    skipped_suffixes = {".pyc", ".pyo", ".mdxprovider"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix in skipped_suffixes:
            continue
        rel = path.relative_to(root)
        if any(part in skipped_dirs for part in rel.parts):
            continue
        yield path, rel


def command_pack(args: argparse.Namespace) -> int:
    root = Path(args.directory).resolve()
    if not root.is_dir():
        print(f"error: provider directory not found: {root}", file=sys.stderr)
        return 2
    manifest = load_manifest(root)
    errors = validate_manifest(manifest, args.schema)
    if errors:
        print("Refusing to package an invalid manifest:")
        for error in errors:
            print(f"  - {error}")
        return 1
    output = Path(args.output).resolve() if args.output else root.with_suffix(".mdxprovider")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, rel in _safe_files(root):
            archive.write(source, rel.as_posix())
    print(f"Packed provider: {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="melodex-provider")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create a provider skeleton")
    p_init.add_argument("directory")
    p_init.add_argument("--id", default="org.example.provider")
    p_init.add_argument("--name", default="Example Provider")
    p_init.set_defaults(func=command_init)

    p_validate = sub.add_parser("validate", help="validate manifest.json")
    p_validate.add_argument("path", help="provider directory or manifest.json")
    p_validate.add_argument("--schema", default=None)
    p_validate.set_defaults(func=command_validate)

    p_pack = sub.add_parser("pack", help="create a .mdxprovider bundle")
    p_pack.add_argument("directory")
    p_pack.add_argument("-o", "--output", default=None)
    p_pack.add_argument("--schema", default=None)
    p_pack.set_defaults(func=command_pack)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
