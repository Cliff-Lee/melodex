from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from melodex_provider_sdk.extension_cli import (
    command_doctor,
    command_init,
    command_pack,
    command_validate,
    validation_errors,
)


def test_extension_descriptor_validation():
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.meta",
        "contracts": [
            {
                "capability": "metadata",
                "contract_version": "0.1",
                "method": "metadata.enrich",
            }
        ],
    }
    assert validation_errors(descriptor) == []


def test_extension_descriptor_rejects_mismatched_method():
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.bad",
        "contracts": [
            {
                "capability": "metadata",
                "contract_version": "0.1",
                "method": "artwork.lookup",
            }
        ],
    }
    errors = validation_errors(descriptor)
    assert any("metadata.enrich" in error for error in errors)


def test_extension_cli_init_validate_doctor_pack(tmp_path: Path):
    root = tmp_path / "my-extension"
    args = argparse.Namespace(
        directory=str(root),
        id="org.example.art",
        name="Example Art",
        capability="artwork",
    )
    assert command_init(args) == 0
    descriptor = json.loads((root / "capabilities.json").read_text("utf-8"))
    assert descriptor["contracts"][0]["method"] == "artwork.lookup"

    assert command_validate(argparse.Namespace(path=str(root))) == 0
    assert command_doctor(argparse.Namespace(path=str(root))) == 0

    package = tmp_path / "example.mdxplugin"
    assert command_pack(
        argparse.Namespace(directory=str(root), output=str(package))
    ) == 0
    assert package.is_file()
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
    assert "capabilities.json" in names
    assert "plugin.py" in names
    assert "SOURCE_POLICY.md" in names


def test_extension_descriptor_accepts_declared_configuration():
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.configured",
        "configuration": [
            {
                "key": "api_token",
                "label": "API token",
                "type": "secret",
                "required": True,
            }
        ],
        "contracts": [
            {
                "capability": "metadata",
                "contract_version": "0.1",
                "method": "metadata.enrich",
            }
        ],
    }
    assert validation_errors(descriptor) == []


def test_extension_descriptor_rejects_invalid_configuration_key():
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.badconfig",
        "configuration": [
            {"key": "../token", "label": "Token", "type": "secret"}
        ],
        "contracts": [
            {
                "capability": "metadata",
                "contract_version": "0.1",
                "method": "metadata.enrich",
            }
        ],
    }
    assert validation_errors(descriptor)


def test_extension_descriptor_accepts_optional_health_contract():
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.healthy",
        "health": {
            "contract_version": "0.1",
            "method": "extension.health",
        },
        "contracts": [
            {
                "capability": "metadata",
                "contract_version": "0.1",
                "method": "metadata.enrich",
            }
        ],
    }
    assert validation_errors(descriptor) == []


def test_extension_descriptor_rejects_invalid_health_method():
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.badhealth",
        "health": {
            "contract_version": "0.1",
            "method": "health.check",
        },
        "contracts": [
            {
                "capability": "metadata",
                "contract_version": "0.1",
                "method": "metadata.enrich",
            }
        ],
    }
    errors = validation_errors(descriptor)
    assert any("extension.health" in error for error in errors)


def test_extension_cli_can_scaffold_context_extension(tmp_path: Path):
    root = tmp_path / "context-extension"
    args = argparse.Namespace(
        directory=str(root),
        id="org.example.context",
        name="Example Context",
        capability="context",
    )
    assert command_init(args) == 0
    descriptor = json.loads((root / "capabilities.json").read_text("utf-8"))
    assert descriptor["contracts"][0]["method"] == "context.lookup"
    plugin = (root / "plugin.py").read_text("utf-8")
    assert '"capability":"context"' in plugin


def test_extension_cli_can_scaffold_library_suggestions_extension(tmp_path: Path):
    root = tmp_path / "local-intelligence-extension"
    args = argparse.Namespace(
        directory=str(root),
        id="org.example.local-intelligence",
        name="Example Local Intelligence",
        capability="library_suggestions",
    )
    assert command_init(args) == 0
    descriptor = json.loads((root / "capabilities.json").read_text("utf-8"))
    assert descriptor["contracts"][0]["method"] == "library.suggest"
    plugin = (root / "plugin.py").read_text("utf-8")
    assert '"capability":"library_suggestions"' in plugin
