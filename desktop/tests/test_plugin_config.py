from __future__ import annotations

import json
from pathlib import Path

import pytest

from melodex.plugin_config import PluginConfigBroker, normalise_configuration


class FakeSecretStore:
    mode = "test-secret-store"

    def __init__(self):
        self.values: dict[tuple[str, str], str] = {}

    def get(self, plugin_id: str, key: str) -> str | None:
        return self.values.get((plugin_id, key))

    def set(self, plugin_id: str, key: str, value: str) -> None:
        self.values[(plugin_id, key)] = value

    def delete(self, plugin_id: str, key: str) -> None:
        self.values.pop((plugin_id, key), None)


FIELDS = [
    {"key": "endpoint", "label": "Endpoint", "type": "string", "required": True},
    {"key": "api_token", "label": "API token", "type": "secret", "required": True},
    {"key": "enabled", "label": "Enabled", "type": "boolean"},
]


def test_configuration_normalisation_rejects_duplicate_and_unsafe_keys():
    assert [field["key"] for field in normalise_configuration(FIELDS)] == [
        "endpoint",
        "api_token",
        "enabled",
    ]
    with pytest.raises(ValueError, match="duplicate"):
        normalise_configuration(
            [
                {"key": "token", "label": "One", "type": "secret"},
                {"key": "token", "label": "Two", "type": "secret"},
            ]
        )
    with pytest.raises(ValueError, match="key"):
        normalise_configuration(
            [{"key": "../secret", "label": "Bad", "type": "secret"}]
        )


def test_broker_persists_only_non_secret_values(tmp_path: Path):
    secrets = FakeSecretStore()
    broker = PluginConfigBroker(tmp_path, secret_store=secrets)
    status = broker.update(
        "org.example.provider",
        FIELDS,
        {
            "endpoint": "https://api.example.invalid",
            "api_token": "super-secret-token",
            "enabled": True,
        },
    )
    assert status["ready"] is True
    assert status["secret_storage"] == "test-secret-store"

    values = broker.values("org.example.provider", FIELDS)
    assert values == {
        "endpoint": "https://api.example.invalid",
        "api_token": "super-secret-token",
        "enabled": True,
    }

    raw = (tmp_path / "plugin-config.json").read_text("utf-8")
    assert "https://api.example.invalid" in raw
    assert "super-secret-token" not in raw
    assert "api_token" not in raw

    stored = json.loads(raw)
    assert stored["org.example.provider"]["enabled"] is True


def test_broker_reports_missing_required_and_rejects_undeclared_values(tmp_path: Path):
    broker = PluginConfigBroker(tmp_path, secret_store=FakeSecretStore())
    status = broker.status("org.example.provider", FIELDS)
    assert status["ready"] is False
    assert set(status["missing_required"]) == {"endpoint", "api_token"}

    with pytest.raises(ValueError, match="undeclared"):
        broker.update(
            "org.example.provider",
            FIELDS,
            {"not_declared": "nope"},
        )


def test_secret_blank_clears_and_none_preserves(tmp_path: Path):
    secrets = FakeSecretStore()
    broker = PluginConfigBroker(tmp_path, secret_store=secrets)
    broker.update(
        "org.example.provider",
        FIELDS,
        {"api_token": "first"},
    )
    broker.update(
        "org.example.provider",
        FIELDS,
        {"api_token": None},
    )
    assert broker.values("org.example.provider", FIELDS)["api_token"] == "first"
    broker.update(
        "org.example.provider",
        FIELDS,
        {"api_token": ""},
    )
    assert "api_token" not in broker.values("org.example.provider", FIELDS)


def test_remove_clears_plain_and_secret_config(tmp_path: Path):
    secrets = FakeSecretStore()
    broker = PluginConfigBroker(tmp_path, secret_store=secrets)
    broker.update(
        "org.example.provider",
        FIELDS,
        {"endpoint": "example", "api_token": "secret"},
    )
    broker.remove("org.example.provider", FIELDS)
    assert broker.values("org.example.provider", FIELDS) == {}
    stored = json.loads((tmp_path / "plugin-config.json").read_text("utf-8"))
    assert "org.example.provider" not in stored


def test_cached_status_never_reads_secret_store_and_reports_pending(tmp_path: Path):
    class CountingSecretStore(FakeSecretStore):
        def __init__(self):
            super().__init__()
            self.get_calls = 0

        def get(self, plugin_id: str, key: str) -> str | None:
            self.get_calls += 1
            return super().get(plugin_id, key)

    fields = [
        {
            "key": "api_token",
            "label": "API token",
            "type": "secret",
            "required": True,
        }
    ]
    secrets = CountingSecretStore()
    secrets.values[("org.example.provider", "api_token")] = "secret"
    broker = PluginConfigBroker(tmp_path, secret_store=secrets)

    cached = broker.cached_status("org.example.provider", fields)
    assert secrets.get_calls == 0
    assert cached["ready"] is None
    assert cached["pending"] is True
    assert cached["pending_required"] == ["api_token"]

    resolved = broker.status("org.example.provider", fields)
    assert secrets.get_calls == 1
    assert resolved["ready"] is True

    cached_again = broker.cached_status("org.example.provider", fields)
    assert secrets.get_calls == 1
    assert cached_again["ready"] is True
    assert cached_again["pending"] is False


def test_default_secret_store_is_deferred_until_secret_access(
    monkeypatch,
    tmp_path: Path,
):
    import melodex.plugin_config as plugin_config

    calls = {"created": 0}

    def make_store():
        calls["created"] += 1
        return FakeSecretStore()

    monkeypatch.setattr(plugin_config, "_default_secret_store", make_store)
    broker = PluginConfigBroker(tmp_path)

    assert calls["created"] == 0
    assert broker.secret_storage == "deferred"

    cached = broker.cached_status("org.example.provider", FIELDS)
    assert cached["pending"] is True
    assert calls["created"] == 0

    broker.values("org.example.provider", FIELDS)
    assert calls["created"] == 1
