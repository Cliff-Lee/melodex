from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from melodex_provider_sdk.registry_cli import (
    command_validate,
    command_verify_packages,
    validation_errors,
)


def _registry(filename: str, payload: bytes) -> dict:
    return {
        "schema_version": "0.1",
        "plugins": [
            {
                "id": "org.example.demo",
                "name": "Demo",
                "publisher": "Example",
                "version": "1.0.0",
                "kind": "enrichment",
                "status": "community",
                "description": "Demo",
                "capabilities": ["metadata"],
                "license": "MIT",
                "source": {"repository": "https://example.org/source"},
                "distribution": {
                    "package_url": f"https://example.org/{filename}",
                    "format": "mdxplugin",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                },
                "compatibility": {
                    "melodex_min": "0.1.0",
                    "mpp": None,
                    "contracts": {"metadata": "0.1"},
                },
                "permissions": [],
                "source_policy": "https://example.org/policy",
            }
        ],
    }


def test_registry_schema_and_semantics():
    data = _registry("demo.mdxplugin", b"abc")
    assert validation_errors(data) == []


def test_registry_rejects_wrong_package_format():
    data = _registry("demo.mdxplugin", b"abc")
    data["plugins"][0]["distribution"]["format"] = "mdxprovider"
    errors = validation_errors(data)
    assert any("enrichment must use mdxplugin" in error for error in errors)


def test_registry_cli_validate_and_verify(tmp_path: Path):
    payload = b"package-data"
    packages = tmp_path / "packages"
    packages.mkdir()
    package = packages / "demo.mdxplugin"
    package.write_bytes(payload)
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(_registry(package.name, payload), indent=2),
        encoding="utf-8",
    )

    assert command_validate(argparse.Namespace(registry=str(registry))) == 0
    assert (
        command_verify_packages(
            argparse.Namespace(
                registry=str(registry),
                packages=str(packages),
            )
        )
        == 0
    )


def test_repository_registry_packages_match():
    root = Path(__file__).resolve().parents[1]
    registry = root / "registry" / "registry.json"
    packages = root / "registry" / "packages"
    assert command_validate(argparse.Namespace(registry=str(registry))) == 0
    assert (
        command_verify_packages(
            argparse.Namespace(registry=str(registry), packages=str(packages))
        )
        == 0
    )
