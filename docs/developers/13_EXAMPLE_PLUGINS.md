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

## Openverse Audio Provider

**Layer:** current MPP provider

Capabilities:

```text
search
track
playback
```

Teaches legal/open catalog discovery, preservation of per-item licence and attribution metadata, direct-media playback resolution and an important boundary: an index result does not automatically imply that Melodex should advertise provider-authorized offline downloads.

## Cover Art Archive Artwork

**Layer:** experimental v0.1 capability extension

```text
artwork.lookup
```

Teaches capability composition through canonical MusicBrainz release/release-group IDs, front-cover preference, independent failure and conservative rights provenance for artwork whose reuse terms can vary by image.

## ListenBrainz Tags

**Layer:** experimental v0.1 capability extension

```text
metadata.enrich
```

Teaches chained enrichment: a provider or identity resolver supplies a MusicBrainz recording ID, then ListenBrainz contributes community tags without repeating fuzzy identity matching. It also demonstrates privacy-minimal API use because only the recording identifier is sent.

Version 0.1.1 additionally demonstrates the optional extension-level `extension.health` contract using ListenBrainz's service-status endpoint. Health remains separate from the `metadata` capability, and the response explicitly reports whether an upstream service was checked.

## MusicBrainz Song Connections

**Layer:** experimental v0.1 capability extension

```text
context.lookup
```

Turns MusicBrainz's relationship graph into useful listening context: samples, remixes, alternate versions, linked compositions and recording places. It deliberately complements rather than duplicates the built-in Credits tab.

## Wikimedia Liner Notes

**Layer:** experimental v0.1 capability extension

```text
context.lookup
```

Uses a Wikidata-linked English Wikipedia page summary to add a short sourced liner-note card with explicit attribution/licence provenance.

## ListenBrainz Community Pulse

**Layer:** experimental v0.1 capability extension

```text
context.lookup
extension.health
```

Shows aggregate listener/listen counts and popular recordings for the current artist using public ListenBrainz popularity endpoints. It demonstrates useful community context without requiring a ListenBrainz account or token.

## Sonic Neighbours

**Layer:** experimental v0.1 local-intelligence capability extension

```text
library.suggest
intent: similar
```

Finds “more like this” candidates from the user's own library using host-supplied Flow features. The extension receives no audio files or filesystem paths.

## Forgotten Favourites

**Layer:** experimental v0.1 local-intelligence capability extension

```text
library.suggest
intent: rediscover
```

Uses loves, keeps, completion rate, skips and relative recency to resurface strong-but-stale tracks. It is deliberately not equivalent to “most played”.

## Bridge Builder

**Layer:** experimental v0.1 local-intelligence capability extension

```text
library.suggest
intent: bridge
```

Ranks local tracks that could form a plausible musical bridge between the current and next queued tracks using tempo, key, energy, timbre and mixability. It returns an explainable shortlist rather than claiming to be an automatic DJ.

## Public Domain Lyrics

**Layer:** experimental v0.1 capability extension

```text
lyrics.lookup
```

Teaches the lyrics response contract, language/kind filtering, provenance and the important distinction between API accessibility and lyric-text redistribution rights. The bundled corpus is deliberately tiny and historical/public-domain rather than a modern commercial lyrics catalogue.

## Last.fm Recommendations

**Layer:** MPP provider, recommendation-only preview

```text
recommendations.get
```

Teaches discovery/playback separation, a provider that does not pretend to host playable media, and a required user-supplied API key using Melodex's brokered `secret` configuration. A chosen suggestion is expected to go back through the Melodex resolver to find an installed playback source.

## Running an example as an installed extension

Copy an example to a working folder, validate it, then package it:

```bash
cd provider-sdk
python -m pip install -e '.[dev]'

melodex-extension validate examples/ecosystem/wikimedia_artwork
melodex-extension doctor examples/ecosystem/wikimedia_artwork
melodex-extension pack examples/ecosystem/wikimedia_artwork
```

Install the generated `.mdxplugin` locally from **Melodex → Sources → Show power tools**. The same reference integrations are also available as registry-verified packages through **Sources → Explore plugins…**.

Each canonical example also has a baseline record under `provider-sdk/registry/reviews/`, tied to the exact published package SHA-256. In the Plugin Directory, **View review** opens that record.

## Why the lyrics reference is intentionally tiny

A public lyrics endpoint does not automatically imply redistribution rights. The project-maintained lyrics example therefore uses a tiny bundled historical/public-domain corpus to exercise the contract without presenting access to a modern lyrics API as permission to redistribute its text.

A future network-backed lyrics reference should only be added when API terms, content rights, attribution and caching rules are clear enough for a reusable public example.
