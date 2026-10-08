from __future__ import annotations

from typing import Any


def openapi_document() -> dict[str, Any]:
    """OpenAPI 3.1 description of Melodex's local control API."""
    error = {
        "description": "Error",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["error"],
                    "properties": {"error": {"type": "string"}},
                    "additionalProperties": True,
                }
            }
        },
    }
    track_request = {
        "type": "object",
        "properties": {
            "provider_id": {"type": "string"},
            "track_id": {"type": "string"},
            "rel": {"type": "string"},
            "artist": {"type": "string"},
            "title": {"type": "string"},
            "album": {"type": "string"},
        },
        "additionalProperties": True,
    }

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Melodex Local Control API",
            "version": "0.2",
            "description": (
                "Authenticated local/LAN API for searching Melodex sources, resolving music, "
                "controlling playback, editing resolver memory and streaming resolved media."
            ),
        },
        "servers": [{"url": "/", "description": "The running Melodex bridge"}],
        "security": [{"BearerAuth": []}],
        "tags": [
            {"name": "system"},
            {"name": "catalog"},
            {"name": "resolver"},
            {"name": "playback"},
            {"name": "ai"},
        ],
        "paths": {
            "/health": {
                "get": {
                    "operationId": "melodexHealth",
                    "tags": ["system"],
                    "security": [],
                    "responses": {"200": {"description": "Bridge health"}},
                }
            },
            "/openapi.json": {
                "get": {
                    "operationId": "melodexOpenApi",
                    "tags": ["system"],
                    "security": [],
                    "responses": {"200": {"description": "OpenAPI 3.1 document"}},
                }
            },
            "/v1/pair": {
                "post": {
                    "operationId": "melodexPairDevice",
                    "tags": ["system"],
                    "security": [],
                    "description": "Redeem a single-use local QR pairing code. The code expires after two minutes.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["code"],
                                    "properties": {
                                        "code": {"type": "string"},
                                        "device_name": {"type": "string", "maxLength": 80},
                                    },
                                    "additionalProperties": False,
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Device token issued"}, "400": error, "401": error},
                }
            },
            "/v1/unpair": {
                "post": {
                    "operationId": "melodexUnpairDevice",
                    "tags": ["system"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["device_id"],
                                    "properties": {"device_id": {"type": "string"}},
                                    "additionalProperties": False,
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Device token revoked"}, "401": error},
                }
            },
            "/v1/extensions": {
                "get": {
                    "operationId": "melodexExtensions",
                    "tags": ["catalog"],
                    "description": "List installed capability extensions, enabled/preference state, declared permissions, installation provenance and redacted runtime health.",
                    "responses": {"200": {"description": "Capability extension list"}, "401": error},
                }
            },
            "/v1/providers": {
                "get": {
                    "operationId": "melodexProviders",
                    "tags": ["catalog"],
                    "description": "List music providers in resolver-priority order, including version, declared permissions and installation provenance where available.",
                    "responses": {"200": {"description": "Provider list"}, "401": error},
                }
            },
            "/v1/search": {
                "get": {
                    "operationId": "melodexSearch",
                    "tags": ["catalog"],
                    "parameters": [
                        {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "provider", "in": "query", "schema": {"type": "string", "default": "all"}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 100}},
                    ],
                    "responses": {"200": {"description": "Search results"}, "401": error},
                }
            },
            "/v1/recommendations": {
                "get": {
                    "operationId": "melodexRecommendations",
                    "tags": ["catalog"],
                    "description": "Get provider-side track recommendations for a seed artist/title without assuming the recommendation provider can play the result.",
                    "parameters": [
                        {"name": "artist", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "title", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "album", "in": "query", "schema": {"type": "string"}},
                        {"name": "provider", "in": "query", "schema": {"type": "string", "default": "all"}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 25}},
                    ],
                    "responses": {"200": {"description": "Recommendation results"}, "401": error, "500": error},
                }
            },
            "/v1/browse": {
                "get": {
                    "operationId": "melodexBrowse",
                    "tags": ["catalog"],
                    "parameters": [
                        {"name": "provider", "in": "query", "schema": {"type": "string", "default": "local"}},
                        {"name": "kind", "in": "query", "schema": {"type": "string", "default": "featured"}},
                    ],
                    "responses": {"200": {"description": "Browse results"}, "401": error},
                }
            },
            "/v1/resolve": {
                "get": {
                    "operationId": "melodexResolve",
                    "tags": ["resolver"],
                    "description": "Resolve by provider/id or by artist/title/album without starting playback.",
                    "parameters": [
                        {"name": "provider", "in": "query", "schema": {"type": "string"}},
                        {"name": "id", "in": "query", "schema": {"type": "string"}},
                        {"name": "artist", "in": "query", "schema": {"type": "string"}},
                        {"name": "title", "in": "query", "schema": {"type": "string"}},
                        {"name": "album", "in": "query", "schema": {"type": "string"}},
                    ],
                    "responses": {"200": {"description": "Resolved track"}, "401": error, "500": error},
                }
            },
            "/v1/resolve-candidates": {
                "get": {
                    "operationId": "melodexResolveCandidates",
                    "tags": ["resolver"],
                    "parameters": [
                        {"name": "artist", "in": "query", "schema": {"type": "string"}},
                        {"name": "title", "in": "query", "schema": {"type": "string"}},
                        {"name": "album", "in": "query", "schema": {"type": "string"}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20}},
                    ],
                    "responses": {"200": {"description": "Resolver diagnostics"}, "401": error},
                }
            },
            "/v1/status": {
                "get": {
                    "operationId": "melodexStatus",
                    "tags": ["playback"],
                    "responses": {"200": {"description": "Current player state"}, "401": error},
                }
            },
            "/v1/play": {
                "post": {
                    "operationId": "melodexPlay",
                    "tags": ["playback"],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": track_request}},
                    },
                    "responses": {"200": {"description": "Playback started"}, "400": error, "401": error, "500": error},
                }
            },
            "/v1/queue": {
                "post": {
                    "operationId": "melodexQueue",
                    "tags": ["playback"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["tracks"],
                                    "properties": {
                                        "tracks": {"type": "array", "minItems": 1, "items": track_request},
                                        "mode": {"type": "string", "enum": ["replace", "append"], "default": "replace"},
                                        "autoplay": {"type": "boolean", "default": True},
                                    },
                                    "additionalProperties": False,
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Queue result"}, "400": error, "401": error, "500": error},
                }
            },
            "/v1/control": {
                "post": {
                    "operationId": "melodexControl",
                    "tags": ["playback"],
                    "description": "Run a high-level playback/UI control action.",
                    "responses": {"200": {"description": "Control result"}, "400": error, "401": error, "500": error},
                }
            },
            "/v1/resolver/prefer": {
                "post": {
                    "operationId": "melodexResolverPrefer",
                    "tags": ["resolver"],
                    "responses": {"200": {"description": "Preferred match stored"}, "401": error},
                }
            },
            "/v1/resolver/block": {
                "post": {
                    "operationId": "melodexResolverBlock",
                    "tags": ["resolver"],
                    "responses": {"200": {"description": "Wrong match blocked"}, "401": error},
                }
            },
            "/v1/resolver/reset": {
                "post": {
                    "operationId": "melodexResolverReset",
                    "tags": ["resolver"],
                    "responses": {"200": {"description": "Resolver memory reset"}, "401": error},
                }
            },
            "/v1/media": {
                "get": {
                    "operationId": "melodexMedia",
                    "tags": ["playback"],
                    "security": [{"BearerAuth": []}, {"MediaToken": []}],
                    "parameters": [
                        {"name": "provider", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "id", "in": "query", "required": True, "schema": {"type": "string"}},
                    ],
                    "responses": {
                        "200": {"description": "Media"},
                        "206": {"description": "Partial media"},
                        "302": {"description": "Redirect to remote stream"},
                        "401": error,
                        "404": error,
                    },
                }
            },
            "/v1/openai/tools": {
                "get": {
                    "operationId": "melodexOpenAiTools",
                    "tags": ["ai"],
                    "description": (
                        "Return equivalent Melodex function definitions for OpenAI "
                        "Responses and Chat Completions tool calling."
                    ),
                    "responses": {"200": {"description": "Function tool definitions"}, "401": error},
                }
            },
        },
        "components": {
            "securitySchemes": {
                "BearerAuth": {"type": "http", "scheme": "bearer"},
                "MediaToken": {"type": "apiKey", "in": "query", "name": "token"},
            }
        },
    }
