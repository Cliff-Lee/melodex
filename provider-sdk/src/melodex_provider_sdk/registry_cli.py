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


def _review_schema() -> dict[str, Any]:
    text = resources.files("melodex_provider_sdk").joinpath(
        "schemas/review-record-v0.1.json"
    ).read_text(encoding="utf-8")
    return json.loads(text)


def load_registry(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("registry must contain a JSON object")
    return data


def load_review_records(path: str | Path) -> list[dict[str, Any]]:
    root = Path(path)
    if not root.is_dir():
        raise ValueError(f"review directory not found: {root}")
    records: list[dict[str, Any]] = []
    for file in sorted(root.glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"review record must be a JSON object: {file}")
        record = dict(data)
        record["_path"] = str(file)
        records.append(record)
    return records


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

        review = dict(raw.get("review") or {})
        record_url = str(review.get("record") or "")
        if record_url and urlparse(record_url).scheme != "https":
            out.append(
                f"plugins.{index}.review.record: review records must use HTTPS"
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


def review_validation_errors(
    registry: dict[str, Any],
    records: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    validator = Draft202012Validator(_review_schema())
    by_id: dict[str, dict[str, Any]] = {}

    for record_index, raw in enumerate(records):
        clean = {key: value for key, value in raw.items() if key != "_path"}
        for error in sorted(
            validator.iter_errors(clean), key=lambda err: list(err.path)
        ):
            where = ".".join(str(part) for part in error.path)
            prefix = f"records.{record_index}"
            errors.append(
                f"{prefix}.{where}: {error.message}"
                if where
                else f"{prefix}: {error.message}"
            )

        plugin_id = str(raw.get("plugin_id") or "")
        if not plugin_id:
            continue
        if plugin_id in by_id:
            errors.append(f"duplicate review record for {plugin_id!r}")
            continue
        by_id[plugin_id] = raw

        events = [event for event in raw.get("events") or [] if isinstance(event, dict)]
        previous = ""
        for event_index, event in enumerate(events):
            timestamp = str(event.get("reviewed_at") or "")
            if previous and timestamp and timestamp < previous:
                errors.append(
                    f"{plugin_id}: events are not chronological at index {event_index}"
                )
            previous = timestamp or previous

    plugins = {
        str(raw.get("id") or ""): raw
        for raw in registry.get("plugins") or []
        if isinstance(raw, dict)
    }
    unknown = sorted(set(by_id) - set(plugins))
    for plugin_id in unknown:
        errors.append(f"review record references unknown plugin {plugin_id!r}")

    expected_decision = {
        "example": "example-baseline",
        "community": "community-intake",
        "reviewed": "reviewed",
        "deprecated": "deprecated",
        "blocked": "blocked",
    }
    for plugin_id, plugin in plugins.items():
        record = by_id.get(plugin_id)
        if record is None:
            errors.append(f"{plugin_id}: review record is required")
            continue
        events = [event for event in record.get("events") or [] if isinstance(event, dict)]
        if not events:
            errors.append(f"{plugin_id}: review record has no events")
            continue
        latest = events[-1]
        version = str(plugin.get("version") or "")
        if str(latest.get("version") or "") != version:
            errors.append(
                f"{plugin_id}: latest review version {latest.get('version')!r} "
                f"!= registry version {version!r}"
            )

        distribution = dict(plugin.get("distribution") or {})
        registry_hash = str(distribution.get("sha256") or "").lower()
        review_hash = str(latest.get("package_sha256") or "").lower()
        if registry_hash and review_hash != registry_hash:
            errors.append(
                f"{plugin_id}: latest review SHA-256 does not match registry package"
            )
        if not registry_hash and latest.get("package_sha256") not in (None, ""):
            errors.append(
                f"{plugin_id}: review has a package SHA-256 but registry has no package hash"
            )

        status = str(plugin.get("status") or "")
        expected = expected_decision.get(status)
        if expected and str(latest.get("decision") or "") != expected:
            errors.append(
                f"{plugin_id}: latest review decision must be {expected!r} "
                f"for registry status {status!r}"
            )

        review_meta = dict(plugin.get("review") or {})
        latest_at = str(latest.get("reviewed_at") or "")
        if str(review_meta.get("last_reviewed_at") or "") != latest_at:
            errors.append(
                f"{plugin_id}: review.last_reviewed_at does not match latest review event"
            )
        record_url = str(review_meta.get("record") or "")
        expected_name = f"{plugin_id}.json"
        if record_url and not urlparse(record_url).path.endswith("/" + expected_name):
            errors.append(
                f"{plugin_id}: review.record should point to {expected_name}"
            )

    return errors


def command_validate_reviews(args: argparse.Namespace) -> int:
    try:
        registry = load_registry(args.registry)
        records = load_review_records(args.reviews)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    registry_errors = validation_errors(registry)
    review_errors = review_validation_errors(registry, records)
    errors = registry_errors + review_errors
    if errors:
        print("Registry review history is invalid:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(
        f"Registry review history is valid: "
        f"{len(registry.get('plugins') or [])} entries, {len(records)} records"
    )
    return 0


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
    parser.add_argument("--version", action="version", version="%(prog)s 0.9.0")
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

    p = sub.add_parser(
        "validate-reviews",
        help="validate registry review records against current entries",
    )
    p.add_argument("registry")
    p.add_argument("--reviews", required=True)
    p.set_defaults(func=command_validate_reviews)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
