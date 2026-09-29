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
        if key == "fixture-timeout-key":
            time.sleep(2)
            result = {"status":"ready"}
        elif key == "fixture-good-key":
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


def _active_extension_package(path: Path, *, malformed: bool = False) -> Path:
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.active-health-extension",
        "name": "Active Health Extension",
        "version": "0.1.0",
        "publisher": "Tests",
        "description": "Active extension health test",
        "permissions": {
            "network_hosts": ["status.example.invalid"],
            "local_files": False,
            "browser_auth": False,
        },
        "configuration": [
            {
                "key": "credential",
                "label": "Credential",
                "type": "secret",
                "required": False,
            }
        ],
        "health": {
            "contract_version": "0.1",
            "method": "extension.health",
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
    config = params.get("_melodex_config") or {}
    method = req.get("method")
    if method == "extension.health":
        if """ + ("True" if malformed else "False") + """:
            result = {"status":"ready","upstream_checked":True}
        else:
            result = {
                "schema_version":"0.1",
                "status":"ready",
                "upstream_checked":True,
                "message":"Connected with " + str(config.get("credential") or "none"),
                "latency_ms":12,
            }
    elif method == "metadata.enrich":
        subject = params.get("subject") or {}
        title = (subject.get("hints") or {}).get("title")
        if title == "Fail":
            raise RuntimeError("metadata failure")
        result = {
            "schema_version":"0.1",
            "capability":"metadata",
            "subject":subject,
            "fields":{},
        }
    else:
        raise RuntimeError("unsupported")
    print(json.dumps({"jsonrpc":"2.0","id":req["id"],"result":result}), flush=True)
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("capabilities.json", json.dumps(descriptor))
        archive.writestr("plugin.py", plugin)
        archive.writestr("README.md", "# Active Health Extension\n")
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
    assert normalise_health_status("degraded") == "degraded"
    assert health_badge({"status": "authentication_required"}) == "AUTH REQUIRED"
    assert health_badge({"status": "degraded"}) == "DEGRADED"
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

        manager.set_plugin_configuration(plugin_id, {"api_key": "fixture-bad-key"})
        result = manager.test_plugin_health(plugin_id, timeout=1)
        assert result["status"] == "authentication_required"
        assert result["provider_status"] == "auth_required"
        assert "fixture-bad-key" not in json.dumps(result)
        assert "fixture-bad-key" not in result["message"]

        manager.set_plugin_configuration(plugin_id, {"api_key": "fixture-good-key"})
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
        manager.set_plugin_configuration(plugin_id, {"api_key": "fixture-timeout-key"})

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


def test_extension_active_health_checks_upstream_and_redacts_secret(tmp_path: Path):
    manager = ProviderManager(tmp_path / "data")
    try:
        package = _active_extension_package(tmp_path / "active.mdxplugin")
        info = manager.install_extension(package)
        manager.set_plugin_configuration(
            info.id, {"credential": "fixture-extension-key"}
        )

        result = manager.test_plugin_health(info.id, timeout=1)
        assert result["status"] == "ready"
        assert result["check_scope"] == "upstream"
        assert result["upstream_checked"] is True
        assert result["latency_ms"] == 12
        assert "fixture-extension-key" not in json.dumps(result)
        assert "[redacted]" in result["message"]
        assert manager.plugin_health(info.id)["status"] == "ready"
    finally:
        manager.close()


def test_extension_without_health_contract_keeps_process_fallback(tmp_path: Path):
    manager = ProviderManager(tmp_path / "data")
    try:
        package = _extension_package(tmp_path / "legacy-health.mdxplugin")
        info = manager.install_extension(package)
        result = manager.test_plugin_health(info.id, timeout=1)
        assert result["status"] == "ready"
        assert result["check_scope"] == "process"
        assert "Upstream service access" in result["message"]
    finally:
        manager.close()


def test_extension_invalid_active_health_response_is_protocol_error(tmp_path: Path):
    manager = ProviderManager(tmp_path / "data")
    try:
        package = _active_extension_package(
            tmp_path / "malformed-health.mdxplugin", malformed=True
        )
        info = manager.install_extension(package)
        result = manager.test_plugin_health(info.id, timeout=1)
        assert result["status"] == "error"
        assert result["reason"] == "protocol_error"
        assert result["upstream_checked"] is False
    finally:
        manager.close()


def test_active_health_ready_plus_recent_runtime_failure_is_degraded(tmp_path: Path):
    manager = ProviderManager(tmp_path / "data")
    try:
        package = _active_extension_package(tmp_path / "combined.mdxplugin")
        info = manager.install_extension(package)
        manager.set_plugin_configuration(
            info.id, {"credential": "fixture-extension-key"}
        )

        failed = manager.capabilities.enrich_metadata(
            {"entity_type": "track", "hints": {"title": "Fail"}}
        )
        assert failed["errors"]

        result = manager.test_plugin_health(info.id, timeout=1)
        assert result["status"] == "degraded"
        assert result["check_scope"] == "combined"
        assert "Upstream health check passed" in result["message"]
        assert result["reason"] == "call_error"
    finally:
        manager.close()
