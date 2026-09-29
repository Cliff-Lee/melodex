from __future__ import annotations

import json
import zipfile
from pathlib import Path

from melodex.plugin_health import (
    health_badge,
    health_summary,
    normalise_health_status,
    safe_health_text,
)
from melodex.provider_manager import ProviderManager


def _provider_package(path: Path) -> Path:
    manifest = {
        "schema_version": 1,
        "id": "org.example.health-provider",
        "name": "Health Provider",
        "version": "0.1.0",
        "publisher": "Tests",
        "protocol_version": "1.0",
        "description": "Health test provider",
        "capabilities": ["search"],
        "permissions": {
            "network_hosts": [],
            "offline_downloads": False,
            "local_files": False,
            "browser_auth": False,
            "lan_discovery": False,
        },
        "configuration": [
            {
                "key": "api_key",
                "label": "API key",
                "type": "secret",
                "required": True,
            }
        ],
        "entrypoints": {"python": "provider.py"},
    }
    provider = """import json, sys, time
for line in sys.stdin:
    req = json.loads(line)
    params = req.get("params") or {}
    cfg = params.get("_melodex_config") or {}
    method = req.get("method")
    if method == "provider.health":
        key = cfg.get("api_key", "")
        if key == "timeout":
            time.sleep(2)
            result = {"status":"ready"}
        elif key == "good":
            result = {"status":"ready","message":"Connected"}
        else:
            result = {"status":"auth_required","message":"Invalid credential " + str(key)}
    elif method == "catalog.search":
        result = {"items":[]}
    else:
        result = {}
    print(json.dumps({"jsonrpc":"2.0","id":req["id"],"result":result}), flush=True)
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("provider.py", provider)
        archive.writestr("README.md", "# Health Provider\n")
        archive.writestr("SOURCE_POLICY.md", "# Source Policy\n")
        archive.writestr("LICENSE", "test\n")
    return path


def _extension_package(path: Path) -> Path:
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.health-extension",
        "name": "Health Extension",
        "version": "0.1.0",
        "publisher": "Tests",
        "description": "Health test extension",
        "permissions": {
            "network_hosts": [],
            "local_files": False,
            "browser_auth": False,
        },
        "entrypoints": {"python": "plugin.py"},
        "contracts": [
            {
                "capability": "metadata",
                "contract_version": "0.1",
                "method": "metadata.enrich",
            }
        ],
    }
    plugin = """import json, sys
for line in sys.stdin:
    req = json.loads(line)
    params = req.get("params") or {}
    subject = params.get("subject") or {}
    title = (subject.get("hints") or {}).get("title")
    if title == "Fail":
        payload = {"jsonrpc":"2.0","id":req["id"],"error":{"code":-32000,"message":"token=super-secret"}}
    else:
        payload = {"jsonrpc":"2.0","id":req["id"],"result":{
            "schema_version":"0.1",
            "capability":"metadata",
            "subject":subject,
            "fields":{}
        }}
    print(json.dumps(payload), flush=True)
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("capabilities.json", json.dumps(descriptor))
        archive.writestr("plugin.py", plugin)
        archive.writestr("README.md", "# Health Extension\n")
        archive.writestr("SOURCE_POLICY.md", "# Source Policy\n")
        archive.writestr("LICENSE", "test\n")
    return path


def test_health_text_redacts_common_secret_shapes():
    text = safe_health_text(
        "Invalid api_key=abc123 Authorization:BearerXYZ Bearer secret.token.value"
    )
    assert "abc123" not in text
    assert "secret.token.value" not in text
    assert "[redacted]" in text


def test_health_status_and_summary_vocabulary():
    assert normalise_health_status("ok") == "ready"
    assert normalise_health_status("auth_required") == "authentication_required"
    assert normalise_health_status("offline") == "unavailable"
    assert health_badge({"status": "authentication_required"}) == "AUTH REQUIRED"
    assert health_summary(
        {"status": "ready", "message": "Connected", "check_scope": "provider"}
    ) == "READY — Connected"


def test_provider_health_requires_setup_then_redacts_auth_failure(tmp_path: Path):
    manager = ProviderManager(tmp_path / "data")
    try:
        package = _provider_package(tmp_path / "health.mdxprovider")
        provider = manager.install_package(package)
        plugin_id = provider.info.id

        initial = manager.plugin_health(plugin_id)
        assert initial["status"] == "setup_required"

        manager.set_plugin_configuration(plugin_id, {"api_key": "bad-secret"})
        result = manager.test_plugin_health(plugin_id, timeout=1)
        assert result["status"] == "authentication_required"
        assert result["provider_status"] == "auth_required"
        assert "bad-secret" not in json.dumps(result)
        assert "bad-secret" not in result["message"]

        manager.set_plugin_configuration(plugin_id, {"api_key": "good"})
        ready = manager.test_plugin_health(plugin_id, timeout=1)
        assert ready["status"] == "ready"
        assert ready["message"] == "Connected"
        assert manager.plugin_health(plugin_id)["status"] == "ready"
    finally:
        manager.close()


def test_provider_health_timeout_is_bounded_and_cached(tmp_path: Path):
    manager = ProviderManager(tmp_path / "data")
    try:
        package = _provider_package(tmp_path / "health-timeout.mdxprovider")
        provider = manager.install_package(package)
        plugin_id = provider.info.id
        manager.set_plugin_configuration(plugin_id, {"api_key": "timeout"})

        result = manager.test_plugin_health(plugin_id, timeout=0.05)
        assert result["status"] == "unavailable"
        assert result["reason"] == "timeout"
        assert manager.plugin_health(plugin_id)["status"] == "unavailable"
    finally:
        manager.close()


def test_extension_process_check_then_runtime_failure_overrides_cache(tmp_path: Path):
    manager = ProviderManager(tmp_path / "data")
    try:
        package = _extension_package(tmp_path / "health.mdxplugin")
        info = manager.install_extension(package)

        initial = manager.plugin_health(info.id)
        assert initial["status"] == "untested"

        checked = manager.test_plugin_health(info.id)
        assert checked["status"] == "ready"
        assert checked["check_scope"] == "process"
        assert "Upstream service access" in checked["message"]

        result = manager.capabilities.enrich_metadata(
            {"entity_type": "track", "hints": {"title": "Fail"}}
        )
        assert result["errors"]
        runtime = manager.plugin_health(info.id)
        assert runtime["status"] == "error"
        assert runtime["check_scope"] == "runtime"
        assert "super-secret" not in json.dumps(runtime)
    finally:
        manager.close()


def test_extension_disabled_health_state(tmp_path: Path):
    manager = ProviderManager(tmp_path / "data")
    try:
        package = _extension_package(tmp_path / "disabled.mdxplugin")
        info = manager.install_extension(package)
        manager.set_extension_enabled(info.id, False)
        result = manager.plugin_health(info.id)
        assert result["status"] == "disabled"
        tested = manager.test_plugin_health(info.id)
        assert tested["status"] == "disabled"
    finally:
        manager.close()
