# 4. Provider developer guide

## 4.1 Smallest possible provider

A provider needs:

```text
my-provider/
  manifest.json
  provider executable
  README.md
  LICENSE
```

The manifest describes identity, capabilities and permissions. The executable implements MPP.

## 4.2 Required manifest fields

```json
{
  "schema_version": 1,
  "id": "org.example.music",
  "name": "Example Music",
  "version": "1.0.0",
  "publisher": "Example Org",
  "protocol_version": "1.0",
  "capabilities": ["search", "track", "album", "artist", "playback"],
  "permissions": {
    "network_hosts": ["api.example.org", "cdn.example.org"],
    "offline_downloads": false,
    "local_files": false
  }
}
```

See `spec/provider_manifest.schema.json`.

## 4.3 Search

Request:

```json
{
  "query": "artist title",
  "types": ["track", "album", "artist"],
  "limit": 25,
  "cursor": null
}
```

Response:

```json
{
  "items": [
    {
      "type": "track",
      "provider_id": "org.example.music",
      "provider_track_id": "t-123",
      "artist": "Example Artist",
      "title": "Example Track",
      "album": "Example Album",
      "duration_ms": 245000,
      "artwork_url": "https://cdn.example.org/art/123.jpg"
    }
  ],
  "next_cursor": null
}
```

## 4.4 Playback resolution

Providers should return the least-privileged resource necessary for playback. Short-lived signed URLs are preferred when the service supports them.

Request:

```json
{
  "provider_track_id": "t-123",
  "purpose": "stream"
}
```

Response:

```json
{
  "kind": "http",
  "url": "https://cdn.example.org/play/t-123?...",
  "headers": {},
  "mime_type": "audio/mpeg",
  "expires_at": "2026-09-26T14:30:00Z",
  "seekable": true,
  "cache_policy": "session"
}
```

A provider must not claim `offline_allowed` unless the source terms/technical interface actually permit persistent offline storage.

## 4.5 Authentication

MPP v1 supports these patterns:

- API token supplied by user;
- Basic credentials where appropriate;
- OAuth 2 browser flow;
- device-code flow;
- bridge-managed credentials.

Melodex owns credential storage. A provider receives credentials only for its own source.

## 4.6 Pagination

Use opaque cursors. Never force Melodex to know provider page numbers.

## 4.7 Errors

Normalized error envelope:

```json
{
  "error": {
    "code": "AUTH_REQUIRED",
    "message": "Sign-in required",
    "retryable": false
  }
}
```

Standard codes:

- `AUTH_REQUIRED`
- `NOT_FOUND`
- `RATE_LIMITED`
- `TEMPORARY_FAILURE`
- `UNSUPPORTED`
- `PERMISSION_DENIED`
- `PLAYBACK_EXPIRED`
- `INVALID_REQUEST`

## 4.8 Packaging

Desktop providers use `.mdxprovider`, a ZIP with a fixed root layout:

```text
manifest.json
bin/
  macos-arm64/provider
  macos-x86_64/provider
  windows-x86_64/provider.exe
  linux-x86_64/provider
  linux-aarch64/provider
README.md
LICENSE
icon.png
```

A pure-Python provider may instead declare a Python entry point and minimum runtime version. Melodex should still launch it out-of-process.

## 4.9 Development workflow

Proposed SDK commands:

```bash
melodex-provider init my-provider
melodex-provider validate ./my-provider
melodex-provider serve ./my-provider
melodex-provider test ./my-provider
melodex-provider pack ./my-provider
```

The design package includes a small Python reference SDK and demo server.
