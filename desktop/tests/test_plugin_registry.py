from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from melodex.plugin_registry import PluginRegistryClient, validate_registry


def _entry(payload: bytes = b"plugin-bytes") -> dict:
    return {
        "id": "org.example.demo",
        "name": "Demo",
        "publisher": "Example",
        "version": "1.0.0",
        "kind": "enrichment",
        "status": "community",
        "description": "Demo extension",
        "capabilities": ["metadata"],
        "license": "MIT",
        "source": {"repository": "https://example.org/source"},
        "distribution": {
            "package_url": "https://example.org/demo.mdxplugin",
            "format": "mdxplugin",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        },
        "compatibility": {"melodex_min": "0.1.0", "mpp": None, "contracts": {"metadata": "0.1"}},
        "permissions": ["network:example.org"],
        "source_policy": "https://example.org/policy",
    }


def _registry(entry=None):
    return {"schema_version": "0.1", "plugins": [entry or _entry()]}


class FakeResponse:
    def __init__(self, *, data=None, payload=b"", url="https://example.org/resource", error=None):
        self._data = data
        self._payload = payload
        self.url = url
        self.error = error
        self.headers = {"Content-Length": str(len(payload))} if payload else {}

    def raise_for_status(self):
        if self.error:
            raise RuntimeError(self.error)

    def json(self):
        if self.error:
            raise RuntimeError(self.error)
        return self._data

    def iter_content(self, chunk_size=65536):
        for start in range(0, len(self._payload), chunk_size):
            yield self._payload[start : start + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeSession:
    def __init__(self, registry=None, payload=b"plugin-bytes", fail_registry=False):
        self.registry = registry or _registry(payload and _entry(payload))
        self.payload = payload
        self.fail_registry = fail_registry

    def get(self, url, **kwargs):
        if url.endswith("registry.json"):
            return FakeResponse(
                data=self.registry,
                url=url,
                error="offline" if self.fail_registry else None,
            )
        return FakeResponse(payload=self.payload, url=url)


def test_registry_validation_requires_hash_for_installable_package():
    data = _registry()
    data["plugins"][0]["distribution"]["sha256"] = None
    errors = validate_registry(data)
    assert any("sha256" in error for error in errors)


def test_registry_fetch_and_cache_fallback(tmp_path: Path):
    url = "https://example.org/registry.json"
    client = PluginRegistryClient(
        tmp_path,
        registry_url=url,
        session=FakeSession(),
    )
    result = client.fetch(force=True)
    assert result.source == url
    assert result.plugins[0]["id"] == "org.example.demo"

    offline = PluginRegistryClient(
        tmp_path,
        registry_url=url,
        session=FakeSession(fail_registry=True),
    )
    result = offline.fetch(force=True)
    assert result.source == "cache"
    assert result.stale is True
    assert "offline" in result.error


def test_registry_filtering():
    plugins = [
        _entry(),
        {
            **_entry(),
            "id": "org.example.provider",
            "name": "Radio Thing",
            "kind": "provider",
            "capabilities": ["search", "playback"],
        },
    ]
    found = PluginRegistryClient.filter_plugins(
        plugins, query="radio", kind="provider", capability="playback"
    )
    assert [item["id"] for item in found] == ["org.example.provider"]


def test_package_download_verifies_sha_and_size(tmp_path: Path):
    payload = b"verified-package"
    entry = _entry(payload)
    client = PluginRegistryClient(tmp_path, session=FakeSession(payload=payload))
    path = client.download_package(entry)
    assert path.read_bytes() == payload
    assert path.suffix == ".mdxplugin"


def test_package_download_rejects_hash_mismatch(tmp_path: Path):
    payload = b"changed-package!"
    entry = _entry(b"expected-package")
    client = PluginRegistryClient(tmp_path, session=FakeSession(payload=payload))
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        client.download_package(entry)


def test_registry_marks_newer_plugin_incompatible():
    entry = _entry()
    entry["compatibility"]["melodex_min"] = "99.0.0"
    compatible, reason = PluginRegistryClient.compatibility(entry)
    assert compatible is False
    assert "Requires Melodex 99.0.0" in reason
