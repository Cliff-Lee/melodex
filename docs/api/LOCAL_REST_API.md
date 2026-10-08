# Melodex Local REST API

## Status

Bridge protocol version: **0.2**

The desktop app runs an authenticated local control bridge.

## Authentication

Requests require bearer authentication except for public `/health`, `/openapi.json`, and the one-time `POST /v1/pair` enrollment endpoint:

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

Streams local media with Range support or redirects to a remote resource.

### `GET /v1/openai/tools`

Returns Melodex function schemas in Responses and Chat Completions tool formats.

## POST endpoints

### `POST /v1/pair`

The desktop pairing QR contains a random code that expires after two minutes and can be redeemed once. Pairing is local to the Bridge host; it does not use an account or external rendezvous service.

Request:

```json
{"code": "one-time-code", "device_name": "Android phone"}
```

Success returns a device-specific bearer token and device ID. Android stores the token encrypted with Android Keystore. The desktop stores only its SHA-256 digest in `bridge.paired-devices.json`, with user-only permissions where the operating system supports them. The raw token is returned only during pairing.

### `POST /v1/unpair`

Requires the paired device's bearer token and accepts:

```json
{"device_id": "paired-device-id"}
```

This revokes that device token. Devices can also be revoked in the desktop Provider Bridge pairing dialog.

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
