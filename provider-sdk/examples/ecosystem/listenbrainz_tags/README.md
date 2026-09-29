# ListenBrainz Tags Example

A Melodex v0.1 `metadata.enrich` plugin that adds community tags for a track once another extension/provider has supplied a `musicbrainz_recording_id`.

This intentionally tests **composition** rather than doing its own fuzzy identity search:

```text
provider track
  -> MusicBrainz identity
  -> ListenBrainz tag enrichment
```

Returned fields:

- `community_tags`
- `community_tag_counts`
- `genres` (top tag labels, lower confidence)

The public recording-metadata endpoint does not require a user token when a recording MBID is already known.
