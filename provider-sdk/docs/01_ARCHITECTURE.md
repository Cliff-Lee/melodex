# 1. Architecture

## 1.1 Product boundary

Melodex Core is responsible for:

- queueing and playback;
- caching and offline policy;
- Flow analysis and transitions;
- taste memory and recommendation;
- playlist resolution;
- Moments, Vibes and Stay Here;
- LLM actions;
- source selection and fallback;
- user-facing permissions and errors.

A provider is responsible only for:

- catalog discovery/search;
- metadata;
- authentication to its own service;
- converting a provider track identifier into a playable resource when permitted;
- optional download/offline capability when the service permits it.

Providers never control the GUI, Flow engine, user-state database, or LLM action executor.

## 1.2 Core modules

Proposed package layout:

```text
melodex/
  providers/
    manager.py          # source registry and lifecycle
    protocol.py         # normalized request/response types
    models.py           # Track, Album, Artist, PlaybackResource
    permissions.py      # permissions and trust decisions
    credentials.py      # OS credential-vault abstraction
    transports/
      builtin.py
      process.py        # desktop .mdxprovider subprocess
      remote.py         # HTTPS Provider Bridge
    resolver.py         # search across sources + dedupe/ranking
  playback/
    engine.py
    cache.py
    source_bridge.py    # generic range-aware local playback bridge
```

This replaces the current coupling where the player and streaming bridge depend directly on one service client.

## 1.3 Melodex Provider Protocol (MPP)

MPP is transport-neutral. The same semantic methods can be carried over a local process or HTTPS.

Minimum v1 methods:

- `provider.info`
- `provider.health`
- `catalog.search`
- `catalog.get_track`
- `catalog.get_album`
- `catalog.get_artist`
- `playback.resolve`

Optional capability methods:

- `catalog.browse`
- `catalog.recommendations`
- `library.list`
- `library.add`
- `library.remove`
- `offline.resolve_download`
- `auth.begin`
- `auth.complete`
- `auth.logout`

The HTTP mapping is specified in `spec/openapi.yaml`.

## 1.4 Normalized identity

Every provider item has two identities:

```json
{
  "provider_id": "example",
  "provider_track_id": "track-123"
}
```

Optional canonical identifiers improve deduplication:

```json
{
  "isrc": "GBAAA0100001",
  "musicbrainz_recording_id": "..."
}
```

Melodex never assumes that two providers use compatible IDs.

## 1.5 Playback resource

A provider does not hand Melodex arbitrary executable logic. It resolves a track to a constrained playback object:

```json
{
  "kind": "http",
  "url": "https://cdn.example.test/audio/123",
  "headers": {
    "Authorization": "Bearer ..."
  },
  "mime_type": "audio/mpeg",
  "expires_at": "2026-09-26T14:30:00Z",
  "seekable": true,
  "cache_policy": "session"
}
```

Allowed `kind` values in v1:

- `http`
- `file`
- `hls`

Future: `dash` if Melodex gains a compatible playback backend.

`cache_policy` is one of:

- `none`
- `session`
- `temporary`
- `offline_allowed`

Melodex, not the provider, enforces the policy.

## 1.6 Two execution modes

### Desktop local provider

```text
Melodex GUI
   │
ProviderManager
   │ JSON-RPC over stdio
Sandboxed provider process
   │
Remote/local service
```

Benefits:

- provider crash cannot crash Melodex;
- language-neutral implementation;
- permissions can be enforced centrally;
- easy developer debugging;
- no imported third-party code inside the GUI process.

### Provider Bridge

```text
Android / iOS / Desktop Melodex
              │ HTTPS + bearer token
              ▼
       Melodex Provider Bridge
              │
       one or more providers
```

This avoids downloaded-code execution on mobile and gives a single household/provider configuration to every device.

## 1.7 Why not a Python-only plugin API?

A Python class such as `search()` / `get_stream_url()` is attractive for the current desktop codebase, but it creates three long-term problems:

1. arbitrary code runs inside the player process;
2. mobile platforms do not support the same dynamic-code model cleanly;
3. providers become tied to Melodex's Python version and internal package layout.

MPP preserves the simple conceptual API while decoupling implementation language and platform.
