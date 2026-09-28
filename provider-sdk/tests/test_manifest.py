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


def test_provider_manifest_accepts_declared_configuration():
    manifest = load_manifest(ROOT / "examples" / "demo_provider")
    manifest["configuration"] = [
        {
            "key": "api_token",
            "label": "API token",
            "type": "secret",
            "required": True,
            "help": "Token issued by the upstream service.",
        },
        {
            "key": "region",
            "label": "Region",
            "type": "string",
            "required": False,
        },
    ]
    errors = validate_manifest(
        manifest, ROOT / "spec" / "provider_manifest.schema.json"
    )
    assert errors == []


def test_provider_manifest_rejects_invalid_configuration_type():
    manifest = load_manifest(ROOT / "examples" / "demo_provider")
    manifest["configuration"] = [
        {"key": "token", "label": "Token", "type": "password"}
    ]
    errors = validate_manifest(
        manifest, ROOT / "spec" / "provider_manifest.schema.json"
    )
    assert any("configuration" in error for error in errors)
