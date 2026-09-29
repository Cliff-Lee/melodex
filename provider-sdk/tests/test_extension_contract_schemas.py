from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "extensions" / "v0.1"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_extension_contract_schemas_are_valid():
    schemas = []
    for path in SPEC.glob("*.schema.json"):
        schema = _load(path)
        Draft202012Validator.check_schema(schema)
        schemas.append(schema)

    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )

    # Smoke-resolve the shared references from each method schema.
    for path in SPEC.glob("*-request.schema.json"):
        Draft202012Validator(_load(path), registry=registry)
    for path in SPEC.glob("*-response.schema.json"):
        Draft202012Validator(_load(path), registry=registry)


def test_example_capability_descriptors_validate():
    schema = _load(SPEC / "capabilities.schema.json")
    validator = Draft202012Validator(schema)
    examples = [
        ROOT / "examples" / "ecosystem" / "musicbrainz_enrichment" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "wikimedia_artwork" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "cover_art_archive_artwork" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "listenbrainz_tags" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "public_domain_lyrics" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "musicbrainz_connections" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "wikimedia_liner_notes" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "listenbrainz_community_pulse" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "sonic_neighbours" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "forgotten_favourites" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "bridge_builder" / "capabilities.json",
        ROOT / "examples" / "ecosystem" / "musical_detours" / "capabilities.json",
    ]
    for path in examples:
        errors = list(validator.iter_errors(_load(path)))
        assert errors == [], f"{path}: {[error.message for error in errors]}"


def test_extension_health_request_and_response_examples_validate():
    request_schema = _load(SPEC / "health-request.schema.json")
    response_schema = _load(SPEC / "health-response.schema.json")

    request_errors = list(
        Draft202012Validator(request_schema).iter_errors(
            {"schema_version": "0.1", "check": "live"}
        )
    )
    assert request_errors == []

    response_errors = list(
        Draft202012Validator(response_schema).iter_errors(
            {
                "schema_version": "0.1",
                "status": "ready",
                "upstream_checked": True,
                "message": "Service reachable",
                "latency_ms": 42,
            }
        )
    )
    assert response_errors == []

    invalid = list(
        Draft202012Validator(response_schema).iter_errors(
            {
                "schema_version": "0.1",
                "status": "ready",
            }
        )
    )
    assert invalid


def test_context_request_and_response_examples_validate():
    request_schema = _load(SPEC / "context-request.schema.json")
    response_schema = _load(SPEC / "context-response.schema.json")
    common_schema = _load(SPEC / "common.schema.json")
    registry = Registry().with_resources(
        [
            (common_schema["$id"], Resource.from_contents(common_schema)),
            (response_schema["$id"], Resource.from_contents(response_schema)),
            (request_schema["$id"], Resource.from_contents(request_schema)),
        ]
    )
    subject = {
        "entity_type": "track",
        "canonical_ids": {"musicbrainz_recording_id": "rec-1"},
    }
    assert list(
        Draft202012Validator(request_schema, registry=registry).iter_errors(
            {
                "schema_version": "0.1",
                "capability": "context",
                "subject": subject,
                "max_cards": 10,
            }
        )
    ) == []
    assert list(
        Draft202012Validator(response_schema, registry=registry).iter_errors(
            {
                "schema_version": "0.1",
                "capability": "context",
                "subject": subject,
                "cards": [
                    {
                        "id": "story",
                        "title": "Story",
                        "kind": "text",
                        "text": "A sourced note",
                        "provenance": {
                            "source_extension_id": "org.example.context",
                            "retrieved_at": "2026-09-29T00:00:00Z",
                        },
                    },
                    {
                        "id": "pulse",
                        "title": "Pulse",
                        "kind": "facts",
                        "facts": [{"label": "Listeners", "value": 42}],
                        "provenance": {
                            "source_extension_id": "org.example.context",
                            "retrieved_at": "2026-09-29T00:00:00Z",
                        },
                    },
                ],
            }
        )
    ) == []


def test_library_suggest_request_and_response_examples_validate():
    request_schema = _load(SPEC / "library-suggest-request.schema.json")
    response_schema = _load(SPEC / "library-suggest-response.schema.json")
    track = {
        "ref": "t0",
        "title": "Demo",
        "artist": "Artist",
        "album": "Album",
        "duration_ms": 240000,
        "analysis": {
            "bpm": 120.0,
            "rhythm_confidence": 0.8,
            "key_pc": 0,
            "key_mode": "minor",
            "key_confidence": 0.7,
            "loudness_db": -10.0,
            "energy": 0.6,
            "energy_start": 0.4,
            "energy_end": 0.7,
            "spectral_centroid": 1800.0,
            "onset_density": 0.14,
            "intro_mixability": 0.6,
            "outro_mixability": 0.7,
            "ending_type": "natural",
        },
        "taste": {
            "plays": 3,
            "completes": 2,
            "skips": 0,
            "loves": 1,
            "dislikes": 0,
            "keeps": 1,
            "completion_rate": 2 / 3,
            "skip_rate": 0.0,
            "days_since_last_played": 30.0,
        },
    }
    assert list(
        Draft202012Validator(request_schema).iter_errors(
            {
                "schema_version": "0.1",
                "capability": "library_suggestions",
                "intent": "similar",
                "tracks": [track],
                "seed_refs": ["t0"],
                "limit": 10,
                "adventure": 0.4,
            }
        )
    ) == []
    assert list(
        Draft202012Validator(response_schema).iter_errors(
            {
                "schema_version": "0.1",
                "capability": "library_suggestions",
                "intent": "similar",
                "suggestions": [
                    {
                        "ref": "t1",
                        "score": 0.87,
                        "reason": "similar energy · compatible tempo",
                        "badges": ["energy", "tempo"],
                    }
                ],
            }
        )
    ) == []



def test_detour_intent_is_valid_library_suggestion_request_and_response():
    request_schema = _load(SPEC / "library-suggest-request.schema.json")
    response_schema = _load(SPEC / "library-suggest-response.schema.json")
    request = {
        "schema_version": "0.1",
        "capability": "library_suggestions",
        "intent": "detour",
        "tracks": [],
        "limit": 8,
        "adventure": 0.35,
    }
    response = {
        "schema_version": "0.1",
        "capability": "library_suggestions",
        "intent": "detour",
        "suggestions": [],
    }
    assert list(Draft202012Validator(request_schema).iter_errors(request)) == []
    assert list(Draft202012Validator(response_schema).iter_errors(response)) == []
