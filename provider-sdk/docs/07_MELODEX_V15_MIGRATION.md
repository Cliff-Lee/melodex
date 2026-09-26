# 7. Concrete migration from Melodex v15

This plan describes how to move the current desktop application from a source-specific backend to the public provider-neutral architecture.

## 7.1 Current coupling to remove

The private development branch currently has direct dependencies between:

- a source-specific catalog client;
- the player and stream bridge;
- source-specific URL/transfer handling;
- AI playlist resolution and one online catalog implementation;
- vendored source-specific helper code.

The clean public branch should remove all source-specific dependencies from Melodex Core. Private adapters, if used during development, should live outside the public repository and communicate only through the provider boundary.

## 7.2 Phase 1 — normalize models

Add:

```text
melodex/providers/models.py
melodex/providers/protocol.py
```

Create normalized dictionaries/dataclasses for:

- Track
- Album
- Artist
- PlaybackResource
- SearchResult
- ProviderError

Keep adapters at module boundaries so the rest of the current UI does not need a simultaneous rewrite.

## 7.3 Phase 2 — ProviderManager

Add `ProviderManager` with:

```python
search(query, types=None, limit=25, source=None)
get_track(ref)
resolve_playback(ref, purpose="stream")
health()
```

Initially register only:

- LocalFilesProvider
- one safe demo provider

Any private development adapter should remain outside the public repository.

## 7.4 Phase 3 — generic playback bridge

Refactor the source-specific stream bridge into `PlaybackBridge`.

Instead of a provider-specific call such as:

```python
client.resolve_source_url(track_id)
```

use:

```python
resource = provider_manager.resolve_playback(track_ref)
```

`PlaybackBridge` then consumes `resource.url`, `resource.headers`, expiry, seekability and cache policy.

The range-aware localhost caching architecture is worth retaining; only the upstream resolver should change.

## 7.5 Phase 4 — player decoupling

Change:

```python
MelodexPlayer(source_client, cache_dir)
```

to:

```python
MelodexPlayer(provider_manager, cache_dir)
```

Tracks in the queue should carry:

```json
{
  "provider_id": "local",
  "provider_track_id": "..."
}
```

Local permanent files remain a first-class provider, not a special exception scattered through the UI.

## 7.6 Phase 5 — global resolver

Replace any resolver that takes a specific catalog client with a provider-neutral `CatalogResolver`.

Resolution order:

1. canonical-ID exact match;
2. local/permanent exact metadata match;
3. provider search candidates;
4. normalized fuzzy ranking;
5. source preference / availability tie-break.

Existing metadata scoring code can largely survive if its inputs are normalized first.

## 7.7 Phase 6 — desktop process transport

Implement:

```text
providers/transports/process.py
providers/package.py
providers/permissions.py
```

Load `.mdxprovider` bundles only after manifest validation and user approval.

## 7.8 Phase 7 — Provider Bridge

Implement the HTTP MPP server as a standalone package/process that uses the same ProviderManager.

This can later ship as:

- `melodex-bridge` desktop helper;
- Docker image;
- optional service mode in the desktop application.

## 7.9 Phase 8 — clean release audit

Before publishing the clean branch:

- remove all vendored source-specific helper code;
- remove hard-coded private source URLs and names;
- remove source-specific parsing and transfer logic;
- ensure tests use demo/local providers;
- review licences and vendored code;
- scan repository history if publishing an existing Git history;
- ensure docs describe only source-neutral provider integration.

## 7.10 Compatibility shim

To avoid rewriting the whole GUI in one release, create a temporary adapter:

```python
class LegacyClientFacade:
    def __init__(self, provider_manager):
        self.providers = provider_manager

    def search(self, query, category="songs", limit=25):
        ...
```

Delete this facade once UI callers use `ProviderManager` directly.
