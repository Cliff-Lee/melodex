from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

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
        "network_hosts": ["media.example.invalid"],
        "offline_downloads": False,
        "local_files": False,
        "browser_auth": False,
        "lan_discovery": False,
    },
    "configuration": [],
    "entrypoints": {"python": "provider.py"},
}

_TEMPLATE_README = """# Example Melodex Provider

Describe the source, setup, authentication, permissions, and lawful basis for the
integration.

## Development

1. Edit `manifest.json`.
2. Implement MPP using `spec/openapi.yaml` or the local-process mapping.
3. Run `melodex-provider validate .`.
4. Run `melodex-provider doctor .`.
5. Run `melodex-provider pack .`.

Use `vendor/` for bundled pure-Python dependencies when you need a self-contained
provider package.
"""

_TEMPLATE_LICENSE = (
    "Choose and include a license appropriate for your provider before distribution.\n"
)

_TEMPLATE_SOURCE_POLICY = """# Source Policy

Document the upstream source before publishing this provider.

- Source/API:
- Official/documented access method:
- Authentication:
- Rate limits:
- Data/media rights:
- Attribution:
- Caching:
- Offline/download rules:
- Commercial restrictions:
- Per-item rights or licence fields:
"""

_TEMPLATE_PROVIDER = r'''from __future__ import annotations

import json
import sys

TRACK = {
    "type": "track",
    "provider_id": "org.example.provider",
    "provider_track_id": "demo-1",
    "title": "Demo track",
    "artist": "Example artist",
}


def respond(request):
    method = request.get("method")
    params = request.get("params") or {}
    config = params.get("_melodex_config") or {}
    if method == "provider.info":
        return {
            "id": "org.example.provider",
            "name": "Example Provider",
            "version": "0.1.0",
        }
    if method == "provider.health":
        return {"status": "ready"}
    if method == "catalog.search":
        return {"items": [TRACK], "next_cursor": None}
    if method == "catalog.get_track":
        return TRACK
    if method in {"playback.resolve", "playback.refresh"}:
        return {
            "kind": "http",
            "url": "https://media.example.invalid/demo.mp3",
            "headers": {},
            "cookies": {},
            "seekable": True,
            "cache_policy": "none",
        }
    raise RuntimeError(f"Unsupported method: {method}; configured={bool(config)}")


for line in sys.stdin:
    try:
        request = json.loads(line)
        result = respond(request)
        payload = {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
    except Exception as exc:
        payload = {
            "jsonrpc": "2.0",
            "id": request.get("id") if "request" in locals() else None,
            "error": {"code": -32000, "message": str(exc)},
        }
    print(json.dumps(payload), flush=True)
'''


def command_init(args: argparse.Namespace) -> int:
    target = Path(args.directory).resolve()
    if target.exists() and any(target.iterdir()):
        print(f"error: target is not empty: {target}", file=sys.stderr)
        return 2
    target.mkdir(parents=True, exist_ok=True)
    manifest = dict(_TEMPLATE_MANIFEST)
    manifest["id"] = args.id
    manifest["name"] = args.name
    (target / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    provider_text = _TEMPLATE_PROVIDER.replace("org.example.provider", args.id)
    provider_text = provider_text.replace("Example Provider", args.name)
    (target / "provider.py").write_text(provider_text, encoding="utf-8")
    readme_text = _TEMPLATE_README.replace("Example Melodex Provider", args.name)
    (target / "README.md").write_text(readme_text, encoding="utf-8")
    (target / "LICENSE").write_text(_TEMPLATE_LICENSE, encoding="utf-8")
    (target / "SOURCE_POLICY.md").write_text(
        _TEMPLATE_SOURCE_POLICY, encoding="utf-8"
    )
    (target / "vendor").mkdir(exist_ok=True)
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
    skipped_dirs = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
    }
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


def _rpc(
    proc: subprocess.Popen[str], method: str, params: dict[str, Any] | None = None
) -> Any:
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    assert proc.stdin and proc.stdout
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("provider stopped without returning a protocol response")
    response = json.loads(line)
    if response.get("error"):
        raise RuntimeError(str(response["error"].get("message") or response["error"]))
    return response.get("result")


def command_doctor(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    try:
        manifest = load_manifest(root)
        errors = validate_manifest(manifest, args.schema)
    except ManifestValidationError as exc:
        print(f"✗ manifest: {exc}")
        return 1
    if errors:
        print("✗ manifest invalid")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("✓ manifest valid")

    for name in ("README.md", "LICENSE", "SOURCE_POLICY.md"):
        print(f"✓ {name} present" if (root / name).is_file() else f"! {name} missing")

    entries = dict(manifest.get("entrypoints") or {})
    python_entry = str(entries.get("python") or "").strip()
    if args.no_runtime or not python_entry:
        print("✓ static checks complete")
        if not python_entry:
            print("! runtime checks skipped: no Python entrypoint declared")
        return 0

    entry = root / python_entry
    if not entry.is_file():
        print(f"✗ entrypoint missing: {python_entry}")
        return 1
    print(f"✓ entrypoint present: {python_entry}")

    env = os.environ.copy()
    paths = [str(root)]
    if (root / "vendor").is_dir():
        paths.insert(0, str(root / "vendor"))
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)

    proc = subprocess.Popen(
        [sys.executable, "-u", str(entry)],
        cwd=str(root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )
    try:
        info = _rpc(proc, "provider.info") or {}
        print(f"✓ provider.info: {str(info.get('name') or manifest['name'])}")
        health = _rpc(proc, "provider.health") or {}
        print(f"✓ provider.health: {str(health.get('status') or 'unknown')}")
        capabilities = list(manifest.get("capabilities") or [])
        items: list[dict[str, Any]] = []
        if "search" in capabilities:
            search = _rpc(
                proc,
                "catalog.search",
                {"query": args.query, "types": ["track"], "limit": 3, "cursor": None},
            ) or {}
            items = list(search.get("items") or [])
            print(f"✓ catalog.search: {len(items)} item(s)")
        else:
            print("✓ catalog.search skipped: capability not declared")
        if items and "playback" in capabilities:
            item = items[0]
            track_id = str(item.get("provider_track_id") or item.get("track_id") or "")
            resource = _rpc(
                proc,
                "playback.resolve",
                {
                    "provider_track_id": track_id,
                    "track_id": track_id,
                    "purpose": "stream",
                },
            ) or {}
            if not (resource.get("url") or resource.get("stream_url")):
                raise RuntimeError("playback.resolve returned no URL")
            print("✓ playback.resolve returned a playable resource shape")
        if "recommendations" in capabilities:
            print("✓ recommendations capability declared; host-configured runtime call tested separately")
    except Exception as exc:
        print(f"✗ runtime check failed: {exc}")
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="melodex-provider")
    parser.add_argument("--version", action="version", version="%(prog)s 0.6.0")
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

    p_doctor = sub.add_parser("doctor", help="diagnose a provider before packaging")
    p_doctor.add_argument("path", help="provider directory")
    p_doctor.add_argument("--schema", default=None)
    p_doctor.add_argument("--query", default="test")
    p_doctor.add_argument("--no-runtime", action="store_true")
    p_doctor.set_defaults(func=command_doctor)

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
