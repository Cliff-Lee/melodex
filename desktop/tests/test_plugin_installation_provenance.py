from __future__ import annotations

import hashlib
import json
import zipfile

import pytest
from pathlib import Path

from melodex.provider_manager import ProviderManager


def _provider_package(path: Path, version: str = "1.0.0") -> Path:
    manifest = {
        "schema_version": 1,
        "id": "org.example.provenance",
        "name": "Provenance Test",
        "version": version,
        "protocol_version": "1.0",
        "description": "Test provider",
        "capabilities": ["search", "track", "playback"],
        "permissions": {
            "network_hosts": [],
            "offline_downloads": False,
            "local_files": False,
            "browser_auth": False,
            "lan_discovery": False,
        },
        "entrypoints": {"python": "provider.py"},
    }
    provider = """import json, sys
for line in sys.stdin:
    request = json.loads(line)
    print(json.dumps({"jsonrpc":"2.0","id":request.get("id"),"result":{}}), flush=True)
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("provider.py", provider)
    return path


def test_manual_install_records_local_hash(tmp_path: Path):
    package = _provider_package(tmp_path / "manual.mdxprovider")
    manager = ProviderManager(tmp_path / "data")
    try:
        provider = manager.install_package(package)
        record = manager.installation_record(provider.info.id)
        assert record["method"] == "manual"
        assert record["registry_verified"] is False
        assert record["version"] == "1.0.0"
        assert record["package_sha256"] == hashlib.sha256(package.read_bytes()).hexdigest()
        assert record["package_size"] == package.stat().st_size
    finally:
        manager.close()


def test_registry_install_records_verification_provenance(tmp_path: Path):
    package = _provider_package(tmp_path / "registry.mdxprovider", "1.2.0")
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    entry = {
        "id": "org.example.provenance",
        "name": "Provenance Test",
        "publisher": "Example Publisher",
        "version": "1.2.0",
        "kind": "provider",
        "status": "community",
        "capabilities": ["search", "track", "playback"],
        "source": {"repository": "https://example.org/source"},
        "distribution": {
            "format": "mdxprovider",
            "package_url": "https://example.org/provider.mdxprovider",
            "sha256": digest,
            "size_bytes": package.stat().st_size,
        },
    }
    manager = ProviderManager(tmp_path / "data")
    try:
        result = manager.install_downloaded_registry_entry(entry, package)
        record = manager.installation_record(result["id"])
        assert record["method"] == "registry"
        assert record["registry_verified"] is True
        assert record["registry_sha256"] == digest
        assert record["package_sha256"] == digest
        assert record["publisher"] == "Example Publisher"
        assert record["source_repository"] == "https://example.org/source"
        assert record["version"] == "1.2.0"
    finally:
        manager.close()


def test_installation_records_persist(tmp_path: Path):
    package = _provider_package(tmp_path / "manual.mdxprovider")
    data_dir = tmp_path / "data"
    first = ProviderManager(data_dir)
    try:
        first.install_package(package)
    finally:
        first.close()

    second = ProviderManager(data_dir)
    try:
        record = second.installation_record("org.example.provenance")
        assert record["method"] == "manual"
        assert record["package_name"] == "manual.mdxprovider"
    finally:
        second.close()


def test_registry_install_rejects_package_identity_mismatch(tmp_path: Path):
    package = _provider_package(tmp_path / "registry.mdxprovider", "1.0.0")
    entry = {
        "id": "org.example.different",
        "name": "Different",
        "publisher": "Example",
        "version": "1.0.0",
        "kind": "provider",
        "status": "community",
        "capabilities": ["search", "track", "playback"],
        "source": {"repository": "https://example.org/source"},
        "distribution": {
            "format": "mdxprovider",
            "package_url": "https://example.org/provider.mdxprovider",
            "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
            "size_bytes": package.stat().st_size,
        },
    }
    manager = ProviderManager(tmp_path / "data")
    try:
        with pytest.raises(RuntimeError, match="id mismatch"):
            manager.install_downloaded_registry_entry(entry, package)
        assert manager.installation_record("org.example.different") == {}
    finally:
        manager.close()


def test_registry_install_rejects_package_version_mismatch(tmp_path: Path):
    package = _provider_package(tmp_path / "registry.mdxprovider", "1.0.0")
    entry = {
        "id": "org.example.provenance",
        "name": "Provenance Test",
        "publisher": "Example",
        "version": "2.0.0",
        "kind": "provider",
        "status": "community",
        "capabilities": ["search", "track", "playback"],
        "source": {"repository": "https://example.org/source"},
        "distribution": {
            "format": "mdxprovider",
            "package_url": "https://example.org/provider.mdxprovider",
            "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
            "size_bytes": package.stat().st_size,
        },
    }
    manager = ProviderManager(tmp_path / "data")
    try:
        with pytest.raises(RuntimeError, match="version mismatch"):
            manager.install_downloaded_registry_entry(entry, package)
        assert manager.installation_record("org.example.provenance") == {}
    finally:
        manager.close()
