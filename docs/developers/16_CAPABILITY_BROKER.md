# Capability Broker

The Capability Broker is the Melodex Core service that composes small enrichment extensions.

## Status

Implemented in the desktop app for the experimental v0.1 contracts:

```text
identity.resolve
metadata.enrich
artwork.lookup
lyrics.lookup
```

These contracts are **experimental**. MPP playback-provider contracts remain separate.

## Runtime model

```text
playback provider
      ↓
raw track
      ↓
Capability Broker
      ├── identity extension(s)
      ├── metadata extension(s)
      ├── artwork extension(s)
      └── lyrics extension(s)
      ↓
progressively enriched Melodex entity
```

Playback does not wait for every enrichment service.

## Package format

Capability extensions are distributed as:

```text
.mdxplugin
```

A package contains at minimum:

```text
capabilities.json
plugin.py
```

Recommended:

```text
README.md
SOURCE_POLICY.md
LICENSE
fixtures/
tests/
vendor/
```

## Process boundary

Python extensions currently run out-of-process and communicate using newline-delimited JSON-RPC over stdin/stdout.

Keep stdout protocol-clean. Send diagnostics to stderr.

## Discovery

Installed extensions live in Melodex's application-data `extensions/` directory.

The broker discovers `capabilities.json`, validates the declared v0.1 contracts and starts the process only when a capability is needed.

## Preferences

Users can enable/disable extensions independently. Core also stores per-capability preference order.

Preference is a merge signal, not permission to return invalid data.

## Failure isolation

An extension failure becomes an enrichment error, not a playback failure.

```text
playback      ✓
identity      ✓
metadata      timeout
artwork       ✓
lyrics        unavailable
```

The song should continue playing.

## Provenance

Extensions must preserve provenance for externally supplied information.

Melodex keeps fields such as:

```text
source_extension_id
source_item_id
source_url
retrieved_at
license
attribution
confidence
evidence
```

## Security note

The v0.1 extension process boundary provides failure isolation, **not a complete OS sandbox**.

Declared permissions are review/UI metadata today. Only install extensions you trust. Stronger sandboxing/signing remains roadmap work.
