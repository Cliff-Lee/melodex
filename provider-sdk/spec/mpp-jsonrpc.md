# MPP local-process mapping (JSON-RPC over stdio)

Desktop `.mdxprovider` bundles may run as child processes. Semantic operations
match the HTTP/OpenAPI mapping, using newline-delimited JSON-RPC 2.0.

## Transport rules

- stdin carries requests from Melodex;
- stdout contains protocol responses only;
- stderr is for human-readable logs;
- UTF-8, one complete JSON object per line;
- providers must not write banners or debug text to stdout.

## Method mapping

| Semantic method | JSON-RPC method | HTTP equivalent |
|---|---|---|
| provider.info | `provider.info` | `GET /v1/provider` |
| provider.health | `provider.health` | `GET /v1/health` |
| catalog.search | `catalog.search` | `POST /v1/search` |
| catalog.get_track | `catalog.get_track` | `GET /v1/tracks/{id}` |
| catalog.get_album | `catalog.get_album` | `GET /v1/albums/{id}` |
| catalog.get_artist | `catalog.get_artist` | `GET /v1/artists/{id}` |
| playback.resolve | `playback.resolve` | `POST /v1/playback/resolve` |
| playback.refresh | `playback.refresh` | `POST /v1/playback/refresh` |
| recommendations.get | `recommendations.get` | `POST /v1/recommendations` |

`playback.refresh` is optional in SDK v0.2. `recommendations.get` is optional and only called for providers that declare the `recommendations` capability. If `playback.refresh` is absent, Melodex falls back
to a fresh `playback.resolve` call. This keeps v0.1 providers compatible.

A playback resource may include `headers`, `cookies`, `expires_at`,
`refresh_token`, `seekable`, `mime_type`, `cache_policy`, and
`request_timeout_seconds`.
