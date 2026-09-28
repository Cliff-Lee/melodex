from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from melodex.diagnostics import build_diagnostics, write_diagnostics


class FakePluginConfig:
    def status(self, plugin_id, declarations):
        return {
            "declared": True,
            "configured": {"api_token": True},
            "ready": True,
            "missing_required": [],
            "secret_storage": "system-keyring",
        }


class FakeManager:
    def __init__(self):
        self.settings = {
            "jamendo_client_id": "jamendo-secret-value",
            "local_roots": ["/Users/example/Music"],
            "user_streams": [
                {"name": "Private radio", "url": "https://secret.example/stream"}
            ],
        }
        self.plugin_config = FakePluginConfig()
        self.providers = {
            "local": SimpleNamespace(
                info=SimpleNamespace(
                    id="local",
                    name="Local Files",
                    version="1",
                    capabilities=["search", "playback"],
                    permissions={},
                    configuration=[],
                )
            ),
            "jamendo": SimpleNamespace(
                info=SimpleNamespace(
                    id="jamendo",
                    name="Jamendo",
                    version="1",
                    capabilities=["search", "playback"],
                    permissions={},
                    configuration=[],
                )
            ),
            "streams": SimpleNamespace(
                info=SimpleNamespace(
                    id="streams",
                    name="User Streams",
                    version="1",
                    capabilities=["playback"],
                    permissions={},
                    configuration=[],
                )
            ),
            "org.example.provider": SimpleNamespace(
                info=SimpleNamespace(
                    id="org.example.provider",
                    name="Example",
                    version="1.2.3",
                    capabilities=["search", "playback"],
                    permissions={"network_hosts": ["api.example.org"]},
                    configuration=[
                        {"key": "api_token", "label": "API token", "type": "secret"}
                    ],
                )
            ),
        }

    def provider_order(self):
        return ["local", "jamendo", "streams", "org.example.provider"]

    def local_catalog(self):
        return [{"title": "private local track"}]

    def user_streams(self):
        return [{"name": "Private radio", "url": "https://secret.example/stream"}]

    def installation_record(self, plugin_id):
        return {
            "id": plugin_id,
            "name": "Example",
            "version": "1.2.3",
            "kind": "provider",
            "installed_at": "2026-09-29T00:00:00+00:00",
            "method": "registry",
            "package_name": "example.mdxprovider",
            "package_size": 123,
            "package_sha256": "a" * 64,
            "registry_verified": True,
            "registry_status": "community",
            "publisher": "Example Publisher",
            "package_url": "https://should-not-appear.example/package",
            "registry_sha256": "a" * 64,
            "source_repository": "https://example.org/source",
        }

    def extensions(self):
        return [
            {
                "id": "org.example.extension",
                "name": "Example Extension",
                "version": "0.1.0",
                "capabilities": ["metadata"],
                "permissions": {"network_hosts": ["meta.example.org"]},
                "enabled": True,
                "preferred_for": ["metadata"],
                "health": {
                    "status": "error",
                    "calls": 2,
                    "successes": 1,
                    "failures": 1,
                    "consecutive_failures": 1,
                    "last_error": "call_error",
                    "process_running": False,
                },
                "configuration_status": {
                    "declared": True,
                    "configured": {"token": True},
                    "ready": True,
                    "missing_required": [],
                    "secret_storage": "system-keyring",
                },
            }
        ]


def test_diagnostics_excludes_secret_values_and_private_paths():
    payload = build_diagnostics(FakeManager())
    text = json.dumps(payload)
    assert "jamendo-secret-value" not in text
    assert "/Users/example/Music" not in text
    assert "https://secret.example/stream" not in text
    assert "private local track" not in text
    assert "https://should-not-appear.example/package" not in text
    assert payload["sources"][1]["configured"] is True
    assert payload["sources"][2]["stream_count"] == 1
    assert payload["sources"][3]["configuration_status"]["ready"] is True
    assert payload["extensions"][0]["health"]["last_error"] == "call_error"


def test_write_diagnostics_creates_json_file(tmp_path: Path):
    target = write_diagnostics(tmp_path / "diagnostics.json", FakeManager())
    assert target.is_file()
    payload = json.loads(target.read_text("utf-8"))
    assert payload["schema_version"] == "0.1"
    assert payload["sources"]
    assert payload["extensions"]
