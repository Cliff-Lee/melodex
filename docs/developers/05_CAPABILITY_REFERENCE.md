# Capability Reference

## Current MPP provider capabilities

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

## Experimental enrichment contracts

| Capability | Method | Purpose |
| --- | --- | --- |
| identity | `identity.resolve` | Resolve incomplete objects to canonical identifiers |
| metadata | `metadata.enrich` | Add sourced structured fields |
| artwork | `artwork.lookup` | Return sourced visual assets |
| lyrics | `lyrics.lookup` | Return sourced lyrics |

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
