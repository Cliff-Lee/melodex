from __future__ import annotations

import argparse
import json
import sys
import zipfile
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


METHODS = {
    "identity": "identity.resolve",
    "metadata": "metadata.enrich",
    "artwork": "artwork.lookup",
    "lyrics": "lyrics.lookup",
    "context": "context.lookup",
}


def _schema() -> dict[str, Any]:
    text = resources.files("melodex_provider_sdk").joinpath(
        "schemas/extension-capabilities-v0.1.json"
    ).read_text(encoding="utf-8")
    return json.loads(text)


def load_descriptor(path: str | Path) -> tuple[Path, dict[str, Any]]:
    target = Path(path).resolve()
    descriptor_path = target / "capabilities.json" if target.is_dir() else target
    if not descriptor_path.is_file():
        raise FileNotFoundError(f"capabilities.json not found: {descriptor_path}")
    data = json.loads(descriptor_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("capabilities.json must contain a JSON object")
    return descriptor_path, data


def validation_errors(descriptor: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(_schema())
    errors = sorted(validator.iter_errors(descriptor), key=lambda err: list(err.path))
    out: list[str] = []
    for error in errors:
        where = ".".join(str(part) for part in error.path)
        out.append(f"{where}: {error.message}" if where else error.message)
    for index, contract in enumerate(descriptor.get("contracts") or []):
        if not isinstance(contract, dict):
            continue
        capability = str(contract.get("capability") or "")
        method = str(contract.get("method") or "")
        expected = METHODS.get(capability)
        if expected and method != expected:
            out.append(f"contracts.{index}.method: {capability!r} requires {expected!r}")
    return out


def _safe_files(root: Path):
    skipped_dirs = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
    skipped_suffixes = {".pyc", ".pyo", ".mdxplugin"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix in skipped_suffixes:
            continue
        relative = path.relative_to(root)
        if any(part in skipped_dirs for part in relative.parts):
            continue
        yield path, relative


def _plugin_template(capability: str) -> str:
    method = METHODS[capability]
    bodies = {
        "identity": '{"schema_version":"0.1","capability":"identity","status":"not_found","subject":params["subject"],"candidates":[]}',
        "metadata": '{"schema_version":"0.1","capability":"metadata","subject":params["subject"],"fields":{}}',
        "artwork": '{"schema_version":"0.1","capability":"artwork","subject":params["subject"],"assets":[]}' ,
        "lyrics": '{"schema_version":"0.1","capability":"lyrics","subject":params["subject"],"entries":[]}' ,
        "context": '{"schema_version":"0.1","capability":"context","subject":params["subject"],"cards":[]}' ,
    }
    body = bodies[capability]
    return f'''from __future__ import annotations

import json
import sys


def respond(request):
    method = request.get("method")
    params = request.get("params") or {{}}
    config = params.get("_melodex_config") or {{}}
    if method != {method!r}:
        raise RuntimeError(f"Unsupported method: {{method}}")
    return {body}


for line in sys.stdin:
    if not line.strip():
        continue
    request = None
    try:
        request = json.loads(line)
        payload = {{"jsonrpc":"2.0","id":request.get("id"),"result":respond(request)}}
    except Exception as exc:
        payload = {{"jsonrpc":"2.0","id":request.get("id") if isinstance(request, dict) else None,
                   "error":{{"code":-32000,"message":str(exc)}}}}
    print(json.dumps(payload, ensure_ascii=False), flush=True)
'''


def command_init(args: argparse.Namespace) -> int:
    root = Path(args.directory).resolve()
    if root.exists() and any(root.iterdir()):
        print(f"error: target is not empty: {root}", file=sys.stderr)
        return 2
    root.mkdir(parents=True, exist_ok=True)
    capability = str(args.capability)
    descriptor = {
        "schema_version": "0.1",
        "extension_id": args.id,
        "name": args.name,
        "version": "0.1.0",
        "publisher": "Your Name or Organisation",
        "description": f"Example Melodex {capability} capability extension.",
        "permissions": {"network_hosts": [], "local_files": False, "browser_auth": False},
        "configuration": [],
        "entrypoints": {"python": "plugin.py"},
        "contracts": [{"capability": capability, "contract_version": "0.1", "method": METHODS[capability]}],
    }
    (root / "capabilities.json").write_text(json.dumps(descriptor, indent=2) + "\n", encoding="utf-8")
    (root / "plugin.py").write_text(_plugin_template(capability), encoding="utf-8")
    (root / "README.md").write_text(f"# {args.name}\n\nRun `melodex-extension validate .` then `melodex-extension pack .`.\n", encoding="utf-8")
    (root / "SOURCE_POLICY.md").write_text("# Source Policy\n\nDocument API access, rights, rate limits, caching and attribution.\n", encoding="utf-8")
    (root / "LICENSE").write_text("Choose an appropriate license before distribution.\n", encoding="utf-8")
    (root / "vendor").mkdir(exist_ok=True)
    print(f"Created extension skeleton: {root}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    try:
        _, descriptor = load_descriptor(args.path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors = validation_errors(descriptor)
    if errors:
        print("Extension descriptor is invalid:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Extension descriptor is valid.")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    try:
        descriptor_path, descriptor = load_descriptor(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"✗ descriptor: {exc}")
        return 1
    errors = validation_errors(descriptor)
    if errors:
        print("✗ descriptor invalid")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("✓ capabilities.json valid")
    base = descriptor_path.parent
    for name in ("README.md", "LICENSE", "SOURCE_POLICY.md"):
        print(f"✓ {name} present" if (base / name).is_file() else f"! {name} missing")
    entry = str((descriptor.get("entrypoints") or {}).get("python") or "plugin.py")
    if entry:
        path = base / entry
        if not path.is_file():
            print(f"✗ Python entrypoint missing: {entry}")
            return 1
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as exc:
            print(f"✗ Python entrypoint does not compile: {exc}")
            return 1
        print(f"✓ Python entrypoint compiles: {entry}")
    caps = ", ".join(str(x.get("capability")) for x in descriptor.get("contracts") or [] if isinstance(x, dict))
    print(f"✓ contracts: {caps}")
    health = descriptor.get("health")
    if isinstance(health, dict):
        print(f"✓ optional health: {health.get('method')} v{health.get('contract_version')}")
    else:
        print("✓ optional health: not declared (process-check fallback)")
    return 0


def command_pack(args: argparse.Namespace) -> int:
    root = Path(args.directory).resolve()
    if not root.is_dir():
        print(f"error: extension directory not found: {root}", file=sys.stderr)
        return 2
    try:
        _, descriptor = load_descriptor(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors = validation_errors(descriptor)
    if errors:
        print("Refusing to package an invalid extension:")
        for error in errors:
            print(f"  - {error}")
        return 1
    output = Path(args.output).resolve() if args.output else root.with_suffix(".mdxplugin")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, relative in _safe_files(root):
            archive.write(source, relative.as_posix())
    print(f"Packed extension: {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="melodex-extension")
    parser.add_argument("--version", action="version", version="%(prog)s 0.7.0")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init", help="create a capability extension skeleton")
    p.add_argument("directory")
    p.add_argument("--id", default="org.example.extension")
    p.add_argument("--name", default="Example Extension")
    p.add_argument("--capability", choices=sorted(METHODS), default="metadata")
    p.set_defaults(func=command_init)
    p = sub.add_parser("validate", help="validate capabilities.json")
    p.add_argument("path")
    p.set_defaults(func=command_validate)
    p = sub.add_parser("doctor", help="run static extension diagnostics")
    p.add_argument("path")
    p.set_defaults(func=command_doctor)
    p = sub.add_parser("pack", help="create a .mdxplugin bundle")
    p.add_argument("directory")
    p.add_argument("-o", "--output", default=None)
    p.set_defaults(func=command_pack)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
