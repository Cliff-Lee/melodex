from __future__ import annotations

import json
from pathlib import Path

from melodex.journey_registry import (
    BUNDLED_REGISTRY,
    JourneyRegistryClient,
    recipe_sha256,
    validate_journey_registry,
)


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _Session:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def get(self, *args, **kwargs):
        if self.error:
            raise self.error
        return _Response(self.payload)


def test_bundled_journey_registry_is_valid():
    assert validate_journey_registry(BUNDLED_REGISTRY) == []
    assert len(BUNDLED_REGISTRY["recipes"]) >= 5


def test_public_registry_file_matches_bundled_fallback():
    root = Path(__file__).resolve().parents[2]
    public = json.loads((root / "journey-recipes" / "registry.json").read_text("utf-8"))
    assert public == BUNDLED_REGISTRY


def test_registry_entry_hash_detects_tampering():
    entry = dict(BUNDLED_REGISTRY["recipes"][0])
    assert recipe_sha256(entry["recipe"]) == entry["sha256"]
    tampered = json.loads(json.dumps(BUNDLED_REGISTRY))
    tampered["recipes"][0]["recipe"]["name"] = "Changed"
    errors = validate_journey_registry(tampered)
    assert any("sha256" in error for error in errors)


def test_registry_fetch_uses_valid_remote_and_cache(tmp_path: Path):
    client = JourneyRegistryClient(
        tmp_path,
        registry_url="https://example.test/registry.json",
        session=_Session(BUNDLED_REGISTRY),
    )
    result = client.fetch(force=True)
    assert result.source == "https://example.test/registry.json"
    assert len(result.recipes) == len(BUNDLED_REGISTRY["recipes"])
    assert client.cache_path.exists()

    cached = JourneyRegistryClient(
        tmp_path,
        registry_url="https://example.test/registry.json",
        session=_Session(error=RuntimeError("offline")),
    ).fetch()
    assert cached.source == "cache"
    assert cached.stale is False


def test_registry_falls_back_to_bundled_when_offline_without_cache(tmp_path: Path):
    result = JourneyRegistryClient(
        tmp_path,
        registry_url="https://example.test/registry.json",
        session=_Session(error=RuntimeError("offline")),
    ).fetch(force=True)
    assert result.source == "bundled"
    assert result.stale is True
    assert result.error
    assert len(result.recipes) == len(BUNDLED_REGISTRY["recipes"])


def test_filter_searches_tags_author_and_description():
    rows = JourneyRegistryClient.filter_recipes(
        BUNDLED_REGISTRY["recipes"],
        query="rediscovery",
    )
    names = {row["name"] for row in rows}
    assert "Late Night Descent" in names
    assert "Rediscovery Sunday" in names

    bright = JourneyRegistryClient.filter_recipes(
        BUNDLED_REGISTRY["recipes"],
        tag="bright",
    )
    assert {row["name"] for row in bright} == {
        "Dark to Bright",
        "Discovery Drift",
        "Rediscovery Sunday",
    }


def test_recipe_for_entry_rejects_hash_mismatch():
    entry = json.loads(json.dumps(BUNDLED_REGISTRY["recipes"][0]))
    entry["recipe"]["description"] = "Tampered"
    try:
        JourneyRegistryClient.recipe_for_entry(entry)
    except RuntimeError as exc:
        assert "SHA-256 mismatch" in str(exc)
    else:
        raise AssertionError("tampered recipe should be rejected")
