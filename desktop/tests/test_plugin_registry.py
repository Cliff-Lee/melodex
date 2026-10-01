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
        "review": {
            "record": "https://example.org/reviews/org.example.demo.json",
            "last_reviewed_at": "2026-09-29T00:00:00Z",
        },
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


def test_registry_update_detection():
    entry = _entry()
    entry["version"] = "1.2.0"
    assert PluginRegistryClient.update_available(entry, "1.1.9") is True
    assert PluginRegistryClient.update_available(entry, "1.2.0") is False
    assert PluginRegistryClient.update_available(entry, "2.0.0") is False


def test_registry_validation_rejects_kind_format_mismatch():
    data = _registry()
    data["plugins"][0]["kind"] = "provider"
    errors = validate_registry(data)
    assert any("mdxprovider" in error for error in errors)


def test_registry_validation_requires_review_metadata():
    data = _registry()
    data["plugins"][0].pop("review")
    errors = validate_registry(data)
    assert any(".review is required" in error for error in errors)


def test_registry_validation_requires_https_review_record():
    data = _registry()
    data["plugins"][0]["review"]["record"] = "http://example.org/review.json"
    errors = validate_registry(data)
    assert any("review.record must use HTTPS" in error for error in errors)


def test_registry_validation_requires_mdxplugin_for_tools():
    data = _registry()
    data["plugins"][0]["kind"] = "tool"
    data["plugins"][0]["distribution"]["format"] = "mdxprovider"
    errors = validate_registry(data)
    assert any("mdxplugin for tools" in error for error in errors)


def test_registry_cache_isolated_by_registry_url(tmp_path: Path):
    first = PluginRegistryClient(
        tmp_path,
        registry_url="https://example.org/a/registry.json",
        session=FakeSession(),
    )
    second = PluginRegistryClient(
        tmp_path,
        registry_url="https://example.org/b/registry.json",
        session=FakeSession(),
    )
    assert first.cache_path != second.cache_path

    first.fetch(force=True)
    assert first.cache_path.exists()
    assert not second.cache_path.exists()



def test_public_registry_is_reference_only_and_not_a_preinstall_manifest():
    registry_path = Path(__file__).resolve().parents[2] / "provider-sdk" / "registry" / "registry.json"
    data = json.loads(registry_path.read_text("utf-8"))
    plugins = list(data.get("plugins") or [])
    assert len(plugins) == 16
    assert {str(row.get("status") or "") for row in plugins} == {"example"}
    assert sum(1 for row in plugins if row.get("kind") == "provider") == 4
    assert sum(1 for row in plugins if row.get("kind") == "enrichment") == 8
    assert sum(1 for row in plugins if row.get("kind") == "tool") == 4
