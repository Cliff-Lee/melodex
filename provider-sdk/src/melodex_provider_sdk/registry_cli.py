from __future__ import annotations

import argparse
import hashlib
import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator


def _schema() -> dict[str, Any]:
    text = resources.files("melodex_provider_sdk").joinpath(
        "schemas/plugin-registry-v0.1.json"
    ).read_text(encoding="utf-8")
    return json.loads(text)


def load_registry(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("registry must contain a JSON object")
    return data


def validation_errors(data: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(_schema())
    errors = sorted(validator.iter_errors(data), key=lambda err: list(err.path))
    out: list[str] = []
    for error in errors:
        where = ".".join(str(part) for part in error.path)
        out.append(f"{where}: {error.message}" if where else error.message)

    seen: set[str] = set()
    for index, raw in enumerate(data.get("plugins") or []):
        if not isinstance(raw, dict):
            continue
        plugin_id = str(raw.get("id") or "")
        if plugin_id in seen:
            out.append(f"plugins.{index}.id: duplicate id {plugin_id!r}")
        seen.add(plugin_id)

        kind = str(raw.get("kind") or "")
        distribution = dict(raw.get("distribution") or {})
        fmt = str(distribution.get("format") or "")
        if kind == "provider" and fmt != "mdxprovider":
            out.append(
                f"plugins.{index}.distribution.format: providers must use mdxprovider"
            )
        if kind == "enrichment" and fmt != "mdxplugin":
            out.append(
                f"plugins.{index}.distribution.format: enrichment must use mdxplugin"
            )

        package_url = distribution.get("package_url")
        if package_url:
            if urlparse(str(package_url)).scheme != "https":
                out.append(
                    f"plugins.{index}.distribution.package_url: installable packages must use HTTPS"
                )
            if not distribution.get("sha256"):
                out.append(
                    f"plugins.{index}.distribution.sha256: required for installable packages"
                )
            if not distribution.get("size_bytes"):
                out.append(
                    f"plugins.{index}.distribution.size_bytes: required for installable packages"
                )
    return out


def command_validate(args: argparse.Namespace) -> int:
    try:
        data = load_registry(args.registry)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors = validation_errors(data)
    if errors:
        print("Registry is invalid:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"Registry is valid: {len(data.get('plugins') or [])} entries")
    return 0


def command_verify_packages(args: argparse.Namespace) -> int:
    try:
        data = load_registry(args.registry)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors = validation_errors(data)
    if errors:
        print("Registry is invalid:")
        for error in errors:
            print(f"  - {error}")
        return 1

    package_dir = Path(args.packages).resolve()
    failures: list[str] = []
    verified = 0
    for raw in data.get("plugins") or []:
        if not isinstance(raw, dict):
            continue
        distribution = dict(raw.get("distribution") or {})
        package_url = str(distribution.get("package_url") or "")
        if not package_url:
            continue
        filename = Path(urlparse(package_url).path).name
        path = package_dir / filename
        if not path.is_file():
            failures.append(f"{raw.get('id')}: package missing: {filename}")
            continue
        payload = path.read_bytes()
        expected_size = int(distribution.get("size_bytes") or 0)
        actual_hash = hashlib.sha256(payload).hexdigest()
        expected_hash = str(distribution.get("sha256") or "").lower()
        if len(payload) != expected_size:
            failures.append(
                f"{raw.get('id')}: size {len(payload)} != registry {expected_size}"
            )
        elif actual_hash != expected_hash:
            failures.append(
                f"{raw.get('id')}: SHA-256 {actual_hash} != registry {expected_hash}"
            )
        else:
            verified += 1
            print(f"✓ {raw.get('id')}  {filename}")

    if failures:
        print("Package verification failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"Verified {verified} registry package(s).")
    return 0


def command_summary(args: argparse.Namespace) -> int:
    try:
        data = load_registry(args.registry)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for raw in data.get("plugins") or []:
        if not isinstance(raw, dict):
            continue
        caps = ", ".join(str(x) for x in raw.get("capabilities") or [])
        installable = "installable" if (raw.get("distribution") or {}).get("package_url") else "source-only"
        print(
            f"{raw.get('id')}\t{raw.get('status')}\t{raw.get('kind')}\t"
            f"{installable}\t{caps}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="melodex-registry")
    parser.add_argument("--version", action="version", version="%(prog)s 0.4.0")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="validate a registry JSON file")
    p.add_argument("registry")
    p.set_defaults(func=command_validate)

    p = sub.add_parser(
        "verify-packages",
        help="verify local package files against registry SHA-256 and sizes",
    )
    p.add_argument("registry")
    p.add_argument("--packages", required=True)
    p.set_defaults(func=command_verify_packages)

    p = sub.add_parser("summary", help="print compact registry contents")
    p.add_argument("registry")
    p.set_defaults(func=command_summary)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
