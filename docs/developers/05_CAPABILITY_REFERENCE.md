# Capability Reference

Melodex has two extension layers.

## Current MPP provider capabilities

MPP providers supply catalogs and authorized playback access.

| Capability | Current desktop/MPP status | Purpose |
| --- | --- | --- |
| `search` | **implemented** | Search a source catalog through `catalog.search` |
| `browse` | **partial** | Built-in providers can browse; a generic external-provider JSON-RPC browse operation is not yet mapped |
| `track` | **partial** | MPP defines `catalog.get_track`; desktop search/playback paths do not yet expose a general direct track lookup API |
| `album` | **partial** | MPP defines `catalog.get_album`; the desktop adapter does not yet expose it as a general external-provider operation |
| `artist` | **partial** | MPP defines `catalog.get_artist`; the desktop adapter does not yet expose it as a general external-provider operation |
| `playback` | **implemented** | Resolve playable media through `playback.resolve` / optional `playback.refresh` |
| `library` | **built-in / reserved externally** | Built-in providers may expose library behavior; no generic external-provider library RPC is stable yet |
| `offline` | **partial** | Playback resources can declare offline-allowed caching, but a complete generic external-provider offline workflow is not yet surfaced |
| `recommendations` | **implemented / preview** | Optional `recommendations.get` returns discovery tracks from a normalized seed |
| `auth` | **configuration implemented; generic auth flow not yet stable** | Secret/string/boolean config is brokered; no general browser/OAuth MPP method family is currently exposed |

Packages use `.mdxprovider`.

The manifest capability vocabulary is intentionally a little broader than the operations currently wired through the desktop adapter. Treat this table—not the mere presence of a capability string in the schema—as the support truth table.

## Experimental enrichment capabilities

These contracts now have a runnable desktop Capability Broker but remain **v0.1 experimental**.

| Capability | Method | Purpose |
| --- | --- | --- |
| identity | `identity.resolve` | Resolve incomplete objects to canonical identifiers |
| metadata | `metadata.enrich` | Add sourced structured fields |
| artwork | `artwork.lookup` | Return sourced visual assets |
| lyrics | `lyrics.lookup` | Return sourced lyrics |

Packages use `.mdxplugin`.

## Capability independence

Bad:

```text
To provide lyrics you must implement search + albums + playback.
```

Better:

```text
lyrics(track_identity) -> LyricsResult
```

A service may expose multiple capabilities, but the interfaces should remain independently replaceable where practical.

## Extension process

Current Python extensions:

```text
Melodex
  ↕ JSON-RPC over stdin/stdout
extension process
```

This isolates crashes/timeouts from the player. It is not yet a full security sandbox.

## Future directions

Possible future capabilities include:

```text
scrobble
audio_analysis
playlist.import
playlist.export
presence
automation
llm.tool
```

These names are design directions, not stable API commitments.
