import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def test_json_schemas_are_valid_schemas():
    for name in ["provider_manifest.schema.json", "track.schema.json", "catalog_item.schema.json"]:
        schema = json.loads((ROOT / "spec" / name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
