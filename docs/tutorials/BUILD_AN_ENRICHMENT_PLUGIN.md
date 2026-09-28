# Tutorial — Build an Enrichment Plugin

Use this path if your service provides **knowledge about music** rather than playback.

Experimental capability contracts currently include:

```text
identity.resolve
metadata.enrich
artwork.lookup
lyrics.lookup
```

## 1. Choose one capability

Do not build a complete music provider unless you actually need one.

Example:

```text
Wikimedia Commons
        ↓
artwork.lookup
```

## 2. Declare the experimental capability

```json
{
  "schema_version": "0.1",
  "extension_id": "org.example.artwork",
  "contracts": [
    {
      "capability": "artwork",
      "contract_version": "0.1",
      "method": "artwork.lookup"
    }
  ]
}
```

## 3. Receive an EntityRef

```json
{
  "entity_type": "artist",
  "canonical_ids": {
    "musicbrainz_artist_id": "..."
  },
  "hints": {
    "name": "Example Artist"
  }
}
```

Canonical IDs are stronger evidence than display-text hints.

## 4. Return provenance

```json
{
  "url": "https://example.org/image.jpg",
  "role": "portrait",
  "provenance": {
    "source_extension_id": "org.example.artwork",
    "retrieved_at": "2026-09-28T00:00:00Z",
    "license": "CC BY-SA 4.0",
    "attribution": "Example Photographer"
  }
}
```

The source of externally supplied data should survive normalization.

## 5. Fail independently

If artwork fails, playback should still work. If lyrics time out, metadata should still appear.

## 6. Test with fixtures

Store representative upstream responses and test normalization offline. Keep live-network tests optional.

## 7. Read the design reference

- [Capability reference](../developers/05_CAPABILITY_REFERENCE.md)
- [Composition and provenance](../developers/06_COMPOSITION_AND_PROVENANCE.md)
