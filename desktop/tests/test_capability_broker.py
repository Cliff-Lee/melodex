from __future__ import annotations

import json
import zipfile
from pathlib import Path

from melodex.capabilities import (
    CapabilityBroker,
    ExtensionContract,
    ExtensionInfo,
    ExternalExtension,
)
from melodex.metadata import RichMetadataService


class FakeExtension:
    def __init__(self, extension_id, capability, result=None, error=None):
        self.info = ExtensionInfo(
            id=extension_id,
            name=extension_id,
            contracts=[
                ExtensionContract(
                    capability=capability,
                    contract_version="0.1",
                    method={
                        "identity": "identity.resolve",
                        "metadata": "metadata.enrich",
                        "artwork": "artwork.lookup",
                        "lyrics": "lyrics.lookup",
                        "context": "context.lookup",
                        "library_suggestions": "library.suggest",
                    }[capability],
                )
            ],
        )
        self.result = result or {}
        self.error = error

    def contract(self, capability):
        return next(
            (x for x in self.info.contracts if x.capability == capability), None
        )

    def call(self, capability, params, timeout=None):
        if self.error:
            raise RuntimeError(self.error)
        return dict(self.result)

    def close(self):
        pass


def test_broker_metadata_preference_and_alternatives(tmp_path: Path):
    broker = CapabilityBroker(tmp_path)
    subject = {"entity_type": "track", "hints": {"title": "Demo"}}
    broker.extensions = {
        "org.example.a": FakeExtension(
            "org.example.a",
            "metadata",
            {
                "fields": {
                    "title": {
                        "value": "First",
                        "provenance": {"retrieved_at": "2026-09-28T00:00:00Z"},
                    }
                }
            },
        ),
        "org.example.b": FakeExtension(
            "org.example.b",
            "metadata",
            {
                "fields": {
                    "title": {
                        "value": "Second",
                        "provenance": {"retrieved_at": "2026-09-28T00:00:00Z"},
                    }
                }
            },
        ),
    }
    broker.set_preference("metadata", ["org.example.b", "org.example.a"])
    result = broker.enrich_metadata(subject)
    assert result["fields"]["title"]["value"] == "Second"
    assert result["fields"]["title"]["provenance"]["source_extension_id"] == "org.example.b"
    assert result["alternatives"]["title"][0]["value"] == "First"


def test_broker_failure_isolation(tmp_path: Path):
    broker = CapabilityBroker(tmp_path)
    subject = {"entity_type": "track", "hints": {"title": "Demo"}}
    broker.extensions = {
        "org.example.bad": FakeExtension(
            "org.example.bad", "artwork", error="network down"
        ),
        "org.example.good": FakeExtension(
            "org.example.good",
            "artwork",
            {
                "assets": [
                    {
                        "url": "https://example.invalid/cover.jpg",
                        "role": "cover",
                        "score": 0.9,
                        "provenance": {"retrieved_at": "2026-09-28T00:00:00Z"},
                    }
                ]
            },
        ),
    }
    result = broker.lookup_artwork(subject)
    assert len(result["assets"]) == 1
    assert result["assets"][0]["_extension_id"] == "org.example.good"
    assert any("call_error" in error for error in result["errors"])


def test_extension_package_installs_and_runs(tmp_path: Path):
    package = tmp_path / "demo.mdxplugin"
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.demo",
        "name": "Demo",
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
    request = json.loads(line)
    params = request.get("params") or {}
    result = {
        "schema_version": "0.1",
        "capability": "metadata",
        "subject": params["subject"],
        "fields": {
            "genre": {
                "value": "ambient",
                "provenance": {
                    "source_extension_id": "org.example.demo",
                    "retrieved_at": "2026-09-28T00:00:00Z"
                }
            }
        }
    }
    print(json.dumps({"jsonrpc":"2.0","id":request["id"],"result":result}), flush=True)
"""
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("capabilities.json", json.dumps(descriptor))
        archive.writestr("plugin.py", plugin)

    broker = CapabilityBroker(tmp_path / "data")
    info = broker.install_package(package)
    assert info.id == "org.example.demo"
    result = broker.enrich_metadata(
        {"entity_type": "track", "hints": {"title": "Test"}}
    )
    assert result["fields"]["genre"]["value"] == "ambient"
    broker.close()


def test_metadata_service_uses_extension_identity_metadata_and_lyrics(tmp_path: Path):
    class Broker:
        def entity_ref(self, track, identity=None, entity_type="track"):
            return {"entity_type": entity_type, "hints": {"title": track.get("title")}}

        def resolve_identity(self, subject, max_candidates=5):
            return {
                "status": "matched",
                "candidates": [
                    {
                        "canonical_ids": {
                            "musicbrainz_recording_id": "rec-1",
                            "musicbrainz_artist_id": "artist-1",
                        },
                        "display": {"title": "Canonical", "artist": "Artist"},
                        "score": 0.98,
                        "provenance": {
                            "source_extension_id": "org.example.identity",
                            "retrieved_at": "2026-09-28T00:00:00Z",
                        },
                        "_extension_id": "org.example.identity",
                    }
                ],
                "errors": [],
            }

        def legacy_identity(self, track, candidate):
            return CapabilityBroker.legacy_identity(track, candidate)

        def enrich_metadata(self, subject, requested_fields=None):
            return {
                "fields": {
                    "album": {
                        "value": "Extension Album",
                        "provenance": {
                            "source_extension_id": "org.example.metadata",
                            "retrieved_at": "2026-09-28T00:00:00Z",
                        },
                    }
                },
                "errors": [],
            }

        def lookup_lyrics(self, subject, kinds=None, languages=None):
            return {
                "entries": [
                    {
                        "kind": "plain",
                        "language": "en",
                        "text": "extension lyrics",
                        "provenance": {
                            "source_extension_id": "org.example.lyrics",
                            "retrieved_at": "2026-09-28T00:00:00Z",
                        },
                    }
                ],
                "errors": [],
            }

    svc = RichMetadataService(tmp_path / "data", capability_broker=Broker())
    svc.local_lyrics = lambda track: {"text": "", "synced": [], "source": ""}
    svc.identify = lambda track: (_ for _ in ()).throw(
        AssertionError("built-in identify should not run after a matched extension")
    )
    result = svc.enrich_identity({"title": "Raw", "artist": "Artist"})
    assert result["identity"]["recording_mbid"] == "rec-1"
    assert result["identity"]["album"] == "Extension Album"
    assert result["lyrics"]["text"] == "extension lyrics"
    assert result["lyrics"]["source"] == "org.example.lyrics"


def test_metadata_service_uses_extension_artwork_before_caa(tmp_path: Path):
    class Broker:
        def entity_ref(self, track, identity=None, entity_type="track"):
            return {"entity_type": entity_type, "hints": {"title": track.get("title")}}

        def lookup_artwork(self, subject, roles=None, max_results=8):
            return {
                "assets": [
                    {
                        "url": "https://example.invalid/art.jpg",
                        "role": "cover",
                        "score": 0.9,
                        "provenance": {
                            "source_extension_id": "org.example.art",
                            "source_url": "https://example.invalid/file-page",
                            "attribution": "Example Artist",
                            "license": "CC BY 4.0",
                            "retrieved_at": "2026-09-28T00:00:00Z",
                        },
                    }
                ],
                "errors": [],
            }

    svc = RichMetadataService(tmp_path / "data", capability_broker=Broker())
    image_path = tmp_path / "cover.jpg"
    image_path.write_bytes(b"image")
    svc._download_artwork = lambda url: image_path
    svc._caa_json = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("CAA should not run when an extension supplies artwork")
    )
    result = svc.artwork(
        {"title": "Demo"},
        svc.identity_from_dict({"release_mbid": "release-1"}),
    )
    assert result["path"] == str(image_path)
    assert result["source"] == "org.example.art"
    assert result["attribution"] == "Example Artist"
    assert result["license"] == "CC BY 4.0"


def test_extension_does_not_inherit_arbitrary_parent_secrets(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MELODEX_TEST_SECRET", "do-not-forward")
    package = tmp_path / "env.mdxplugin"
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.env",
        "name": "Env",
        "entrypoints": {"python": "plugin.py"},
        "contracts": [
            {
                "capability": "metadata",
                "contract_version": "0.1",
                "method": "metadata.enrich",
            }
        ],
    }
    plugin = """import json, os, sys
for line in sys.stdin:
    req = json.loads(line)
    result = {
        "schema_version": "0.1",
        "capability": "metadata",
        "subject": (req.get("params") or {})["subject"],
        "fields": {
            "secret": {"value": os.getenv("MELODEX_TEST_SECRET", "missing")},
            "extension_id": {"value": os.getenv("MELODEX_EXTENSION_ID", "")},
        },
    }
    print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}), flush=True)
"""
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("capabilities.json", json.dumps(descriptor))
        archive.writestr("plugin.py", plugin)

    broker = CapabilityBroker(tmp_path / "data")
    try:
        broker.install_package(package)
        result = broker.enrich_metadata(
            {"entity_type": "track", "hints": {"title": "Test"}}
        )
        assert result["fields"]["secret"]["value"] == "missing"
        assert result["fields"]["extension_id"]["value"] == "org.example.env"
    finally:
        broker.close()


def test_extension_health_tracks_success_and_redacted_failure(tmp_path: Path):
    package = tmp_path / "health.mdxplugin"
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.health",
        "name": "Health",
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
    title = ((req.get("params") or {}).get("subject") or {}).get("hints", {}).get("title")
    if title == "Fail":
        print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "error": {"code": -32000, "message": "API_KEY=super-secret"}}), flush=True)
    else:
        result = {"schema_version": "0.1", "capability": "metadata", "subject": (req.get("params") or {})["subject"], "fields": {}}
        print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}), flush=True)
"""
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("capabilities.json", json.dumps(descriptor))
        archive.writestr("plugin.py", plugin)

    broker = CapabilityBroker(tmp_path / "data")
    try:
        broker.install_package(package)
        broker.enrich_metadata({"entity_type": "track", "hints": {"title": "OK"}})
        health = broker.list_extensions()[0]["health"]
        assert health["status"] == "ok"
        assert health["calls"] == 1
        assert health["successes"] == 1
        assert health["failures"] == 0

        result = broker.enrich_metadata(
            {"entity_type": "track", "hints": {"title": "Fail"}}
        )
        assert result["errors"]
        health = broker.list_extensions()[0]["health"]
        assert health["status"] == "error"
        assert health["calls"] == 2
        assert health["successes"] == 1
        assert health["failures"] == 1
        assert health["last_error"] == "call_error"
        assert "super-secret" not in json.dumps(health)
    finally:
        broker.close()


def test_extension_receives_brokered_configuration(tmp_path: Path):
    folder = tmp_path / "extension"
    folder.mkdir()
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.config",
        "name": "Config",
        "configuration": [
            {"key": "api_token", "label": "API token", "type": "secret"}
        ],
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
    result = {
        "schema_version": "0.1",
        "capability": "metadata",
        "subject": params["subject"],
        "fields": {"token": {"value": config.get("api_token", "missing")}},
    }
    print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result}), flush=True)
"""
    (folder / "capabilities.json").write_text(json.dumps(descriptor), "utf-8")
    (folder / "plugin.py").write_text(plugin, "utf-8")
    extension = ExternalExtension(folder, descriptor)
    extension.configure({"api_token": "brokered-secret"})
    try:
        result = extension.call(
            "metadata",
            {
                "schema_version": "0.1",
                "capability": "metadata",
                "subject": {"entity_type": "track"},
            },
        )
        assert result["fields"]["token"]["value"] == "brokered-secret"
    finally:
        extension.close()


def test_broker_context_aggregates_cards_with_provenance_and_priority(tmp_path: Path):
    broker = CapabilityBroker(tmp_path)
    subject = {
        "entity_type": "track",
        "canonical_ids": {"musicbrainz_recording_id": "rec-1"},
    }
    broker.extensions = {
        "org.example.low": FakeExtension(
            "org.example.low",
            "context",
            {
                "cards": [
                    {
                        "id": "low",
                        "title": "Low card",
                        "kind": "text",
                        "priority": 10,
                        "text": "Later",
                        "provenance": {"retrieved_at": "2026-09-29T00:00:00Z"},
                    }
                ]
            },
        ),
        "org.example.high": FakeExtension(
            "org.example.high",
            "context",
            {
                "cards": [
                    {
                        "id": "high",
                        "title": "High card",
                        "kind": "facts",
                        "priority": 80,
                        "facts": [{"label": "Listeners", "value": 42}],
                        "provenance": {"retrieved_at": "2026-09-29T00:00:00Z"},
                    }
                ]
            },
        ),
    }
    result = broker.lookup_context(subject)
    assert [card["id"] for card in result["cards"]] == ["high", "low"]
    assert (
        result["cards"][0]["provenance"]["source_extension_id"]
        == "org.example.high"
    )
    assert result["errors"] == []


def test_metadata_service_exposes_context_cards(tmp_path: Path):
    class Broker:
        def entity_ref(self, track, identity=None, entity_type="track"):
            return {
                "entity_type": entity_type,
                "canonical_ids": {
                    "musicbrainz_recording_id": (identity or {}).get(
                        "recording_mbid", "rec-1"
                    )
                },
            }

        def lookup_context(self, subject, requested_cards=None, max_cards=20):
            return {
                "cards": [
                    {
                        "id": "story",
                        "title": "Story",
                        "kind": "text",
                        "text": "Context works",
                        "provenance": {
                            "source_extension_id": "org.example.context",
                            "retrieved_at": "2026-09-29T00:00:00Z",
                        },
                    }
                ],
                "errors": [],
            }

    svc = RichMetadataService(tmp_path / "data", capability_broker=Broker())
    result = svc.enrich_context(
        {"title": "Demo"},
        {"recording_mbid": "rec-1", "artist": "Example"},
    )
    assert result["cards"][0]["title"] == "Story"
    assert result["cards"][0]["text"] == "Context works"


def test_broker_library_suggestions_merges_and_ranks(tmp_path: Path):
    broker = CapabilityBroker(tmp_path)
    profiles = [
        {
            "ref": "t0",
            "title": "Seed",
            "artist": "A",
            "album": "",
            "duration_ms": 1000,
            "analysis": None,
            "taste": {},
        },
        {
            "ref": "t1",
            "title": "One",
            "artist": "B",
            "album": "",
            "duration_ms": 1000,
            "analysis": None,
            "taste": {},
        },
        {
            "ref": "t2",
            "title": "Two",
            "artist": "C",
            "album": "",
            "duration_ms": 1000,
            "analysis": None,
            "taste": {},
        },
    ]
    broker.extensions = {
        "org.example.low": FakeExtension(
            "org.example.low",
            "library_suggestions",
            {
                "intent": "similar",
                "suggestions": [
                    {"ref": "t1", "score": 0.61, "reason": "low"}
                ],
            },
        ),
        "org.example.high": FakeExtension(
            "org.example.high",
            "library_suggestions",
            {
                "intent": "similar",
                "suggestions": [
                    {"ref": "t2", "score": 0.91, "reason": "high"}
                ],
            },
        ),
    }
    result = broker.suggest_library(
        profiles, "similar", seed_refs=["t0"], limit=10, adventure=0.4
    )
    assert [row["ref"] for row in result["suggestions"]] == ["t2", "t1"]
    assert result["suggestions"][0]["_extension_id"] == "org.example.high"
    assert result["errors"] == []
