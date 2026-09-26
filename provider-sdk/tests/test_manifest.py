import json
from pathlib import Path

from melodex_provider_sdk.validation import load_manifest, validate_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_demo_manifest_is_valid():
    manifest = load_manifest(ROOT / "examples" / "demo_provider")
    errors = validate_manifest(manifest, ROOT / "spec" / "provider_manifest.schema.json")
    assert errors == []


def test_invalid_manifest_reports_error(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    manifest = load_manifest(path)
    errors = validate_manifest(manifest, ROOT / "spec" / "provider_manifest.schema.json")
    assert errors
