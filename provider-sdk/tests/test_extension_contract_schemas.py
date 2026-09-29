from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "extensions" / "v0.1"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_extension_contract_schemas_are_valid():
    schemas = []
    for path in SPEC.glob("*.schema.json"):
        schema = _load(path)
        Draft202012Validator.check_schema(schema)
        schemas.append(schema)

    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )

    # Smoke-resolve the shared references from each method schema.
    for path in SPEC.glob("*-request.schema.json"):
        Draft202012Validator(_load(path), registry=registry)
    for path in SPEC.glob("*-response.schema.json"):
        Draft202012Validator(_load(path), registry=registry)


def test_example_capability_descriptors_validate():
    schema = _load(SPEC / "capabilities.schema.json")
    validator = Draft202012Validator(schema)
    examples = [
        ROOT / "examples" / "ecosystem" / "musicbrainz_enrichment" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "wikimedia_artwork" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "cover_art_archive_artwork" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "listenbrainz_tags" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "public_domain_lyrics" / "capabilities.json",
    ]
    for path in examples:
        errors = list(validator.iter_errors(_load(path)))
        assert errors == [], f"{path}: {[error.message for error in errors]}"
