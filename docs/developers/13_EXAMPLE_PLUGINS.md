# Reference Extensions

The reference ecosystem uses small examples that teach one architectural idea at a time.

## Radio Browser Provider

**Layer:** current MPP provider

Capabilities:

```text
search
track
playback
```

Teaches internet-radio normalization, stable station identity, stream resolution, mirror fallback and non-downloadable continuous playback.

## LibriVox Provider

**Layer:** current MPP provider

Capabilities:

```text
search
track
playback
offline
```

Teaches public-domain media, projects/books as albums, sections as tracks and provider-authorized offline access.

## MusicBrainz Enrichment

**Layer:** experimental v0.1 capability extension, runnable through the Capability Broker

```text
identity.resolve
metadata.enrich
```

Teaches weak metadata → canonical identity, MusicBrainz IDs, match evidence and field-level provenance.

## Wikimedia Commons Artwork

**Layer:** experimental v0.1 capability extension, runnable through the Capability Broker

```text
artwork.lookup
```

Teaches artwork as an independent capability and preservation of per-file licence/attribution.

## Running an example as an installed extension

Copy an example to a working folder, validate it, then package it:

```bash
cd provider-sdk
python -m pip install -e '.[dev]'

melodex-extension validate examples/ecosystem/wikimedia_artwork
melodex-extension doctor examples/ecosystem/wikimedia_artwork
melodex-extension pack examples/ecosystem/wikimedia_artwork
```

Install the generated `.mdxplugin` from Melodex → Sources → Power tools.

## Why not an official lyrics example yet?

A public lyrics endpoint does not automatically imply redistribution rights. The first public reference lyrics extension should use a source whose API access and content rights are sufficiently clear for a reusable example.
