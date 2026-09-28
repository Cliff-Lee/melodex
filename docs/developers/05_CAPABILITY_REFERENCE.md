# Capability Reference

Melodex has two extension layers.

## Current MPP provider capabilities

MPP providers supply catalogs and authorized playback access.

| Capability | Status | Purpose |
| --- | --- | --- |
| `search` | implemented | Search a source catalog |
| `browse` | implemented | Browse source-defined collections |
| `track` | implemented | Retrieve track data |
| `album` | implemented | Retrieve album data |
| `artist` | implemented | Retrieve artist data |
| `playback` | implemented | Resolve playable media |
| `library` | implemented | Interact with a provider library |
| `offline` | implemented/evolving | Provider-authorized offline access |
| `recommendations` | implemented | Provider-side recommendations |
| `auth` | implemented | Provider authentication |

Packages use `.mdxprovider`.

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
