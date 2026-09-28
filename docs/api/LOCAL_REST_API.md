# Melodex Local REST API

## Status

Bridge protocol version: **0.2**

The desktop app runs an authenticated local control bridge.

## Authentication

Except for `/health` and `/openapi.json`, requests require:

```http
Authorization: Bearer <bridge-token>
```

The media endpoint also accepts a query token because some playback engines cannot attach custom headers. Query-token authentication is restricted to `/v1/media`; other protected endpoints require the Bearer header.

Treat the token like a password.

## GET endpoints

### `GET /health`

Public health check.

### `GET /openapi.json`

Public OpenAPI 3.1 description. It contains API structure, not credentials.

### `GET /v1/providers`

Lists connected playback/catalog sources in resolver-priority order.

Where available, provider rows also include:

```text
version
declared permissions
installation provenance
```

The provenance record can distinguish registry-verified installs from manual local packages.

### `GET /v1/extensions`

Lists installed capability extensions, declared contracts, enabled/preference state, declared permissions and installation provenance where available.

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

Streams local media with Range support or redirects to an ordinary remote resource. Provider-specific upstream request headers/cookies are not yet proxied through this LAN media endpoint.

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


## Public response redaction

Catalog/control responses strip local filesystem paths, raw upstream playback URLs, provider request headers/cookies, refresh tokens and internal allowed-host state.

When `/v1/resolve` or `/v1/play` returns a playable track with provider identity, the public `stream_url` points back to the authenticated Bridge media endpoint rather than exposing the upstream playback URL directly.
