import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def test_json_schemas_are_valid_schemas():
    for name in [
        "provider_manifest.schema.json",
        "track.schema.json",
        "catalog_item.schema.json",
        "registry/plugin-registry.schema.json",
        "registry/review-record.schema.json",
    ]:
        path = ROOT / name if name.startswith("registry/") else ROOT / "spec" / name
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)


def test_registry_schema_copies_match():
    pairs = [
        (
            ROOT / "spec" / "extensions" / "v0.1" / "capabilities.schema.json",
            ROOT / "src" / "melodex_provider_sdk" / "schemas" / "extension-capabilities-v0.1.json",
        ),
        (
            ROOT / "registry" / "plugin-registry.schema.json",
            ROOT / "src" / "melodex_provider_sdk" / "schemas" / "plugin-registry-v0.1.json",
        ),
        (
            ROOT / "registry" / "review-record.schema.json",
            ROOT / "src" / "melodex_provider_sdk" / "schemas" / "review-record-v0.1.json",
        ),
    ]
    for public, bundled in pairs:
        assert json.loads(public.read_text("utf-8")) == json.loads(
            bundled.read_text("utf-8")
        )
