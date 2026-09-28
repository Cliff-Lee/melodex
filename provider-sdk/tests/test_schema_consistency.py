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
