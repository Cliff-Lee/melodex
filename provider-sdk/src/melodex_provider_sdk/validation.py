from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class ManifestValidationError(ValueError):
    """Raised when a provider manifest cannot be read or parsed."""


def load_manifest(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if path.is_dir():
        path = path / "manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestValidationError(f"Manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestValidationError("Manifest root must be a JSON object")
    return data


def _load_default_schema() -> dict[str, Any]:
    schema_file = resources.files("melodex_provider_sdk").joinpath(
        "schemas/provider_manifest.schema.json"
    )
    return json.loads(schema_file.read_text(encoding="utf-8"))


def validate_manifest(
    manifest: dict[str, Any], schema_path: str | Path | None = None
) -> list[str]:
    if schema_path is None:
        schema = _load_default_schema()
    else:
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(manifest), key=lambda e: list(e.absolute_path))
    messages: list[str] = []
    for error in errors:
        where = ".".join(str(p) for p in error.absolute_path) or "<root>"
        messages.append(f"{where}: {error.message}")
    return messages
