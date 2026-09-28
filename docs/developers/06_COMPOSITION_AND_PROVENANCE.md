# Composition and Provenance

## Provider identity is not canonical identity

A provider-local reference:

```json
{
  "provider_id": "org.example.source",
  "provider_track_id": "8472"
}
```

means only that one provider knows the object as `8472`.

Canonical identifiers may include:

```text
ISRC
MusicBrainz recording ID
MusicBrainz release ID
MusicBrainz artist ID
Wikidata ID
```

## Progressive enrichment

```text
raw provider result
      ↓
playable immediately
      ↓
canonical identity
      ↓
metadata
      ↓
artwork
      ↓
lyrics
```

Enrichment should improve the object without unnecessarily blocking playback.

## Provenance

External contributions should be traceable.

Useful provenance fields include:

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

Confidence is source-local unless explicitly calibrated. Do not assume a `0.9` from two unrelated extensions means exactly the same thing.

## Merge ownership

Extensions contribute candidates.

**Melodex Core owns merge policy.**

Useful precedence signals include:

1. explicit user override;
2. exact canonical-ID agreement;
3. user-selected preferred capability source;
4. configured source trust/priority;
5. match evidence;
6. completeness;
7. freshness;
8. deterministic tie-break.

Installation order should not become an undocumented permanent merge rule.

## Failure isolation

```text
playback  ✓
identity  ✓
metadata  ✓
artwork   timeout
lyrics    unavailable
```

The track should still play.
