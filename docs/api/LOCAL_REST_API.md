# Melodex Local REST API

## Status

Bridge protocol version: **0.2**

The desktop app runs an authenticated local control bridge.

## Authentication

Except for `/health` and `/openapi.json`, requests require:

```http
Authorization: Bearer <bridge-token>
```

The media endpoint also accepts a query token because some playback engines cannot attach custom headers.

Treat the token like a password.

## GET endpoints

### `GET /health`

Public health check.

### `GET /openapi.json`

Public OpenAPI 3.1 description. It contains API structure, not credentials.

### `GET /v1/providers`

Lists connected playback/catalog sources in resolver-priority order.

### `GET /v1/extensions`

Lists installed capability extensions, declared contracts and current enabled/preference state.

### `GET /v1/search`

Query parameters:

```text
q
provider
limit
```

### `GET /v1/browse`

Browse one source.

### `GET /v1/resolve`

Resolve by provider/id or by artist/title/album without starting playback.

### `GET /v1/resolve-candidates`

Inspect candidate providers and resolver scores.

### `GET /v1/status`

Current player state.

### `GET /v1/media`

Streams local media with Range support or redirects to a remote resource.

### `GET /v1/openai/tools`

Returns Melodex function schemas in Responses and Chat Completions tool formats.

## POST endpoints

### `POST /v1/play`

Resolve and play one requested track.

### `POST /v1/queue`

Resolve and queue an ordered list.

### `POST /v1/control`

Runs a high-level playback/UI action.

### Resolver memory

```text
POST /v1/resolver/prefer
POST /v1/resolver/block
POST /v1/resolver/reset
```

These change per-song matching memory rather than disabling a whole source.

## Errors

Current error envelope:

```json
{"error": "message"}
```

Typical HTTP codes: 400, 401, 404 and 500.

## Versioning

Breaking API-contract changes should move to a new major API route rather than silently changing `/v1`.
