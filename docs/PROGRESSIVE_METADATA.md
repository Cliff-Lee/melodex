# Melodex Progressive Metadata Loading

This update fixes Rich Now Playing appearing stuck on raw local metadata while network enrichment is still running.

## Previous behavior

The original Rich Now Playing worker performed the entire chain before updating the UI:

1. identify recording
2. artist information
3. artist photo
4. full discography
5. download release covers
6. credits
7. artwork
8. finally update the page

A slow Cover Art Archive/Wikimedia request could therefore make a correctly identifiable track look unidentified.

## New behavior

The page updates progressively:

1. raw local/provider metadata appears immediately
2. MusicBrainz identity + local lyrics
3. cover artwork
4. artist details
5. recording/work credits
6. release timeline metadata
7. plugin context cards after identity/credit prerequisites are available
8. artist photograph
9. only then a small subset of release-cover thumbnails

Each stage is stale-result protected using the current track key. Changing tracks while a request is in flight cannot overwrite the new track.

## Visible status

The page now shows progress such as:

- `Identifying with MusicBrainz…`
- `✓ MusicBrainz match 98% · loading artwork, credits, context…`
- `✓ MusicBrainz match 98% · enrichment complete`
- `No confident MusicBrainz match — showing local metadata`

## Release covers

`discography()` no longer downloads any images. It returns release metadata immediately.

`hydrate_discography_covers()` is a separate background stage and currently hydrates at most eight covers for the visible release wall. Missing images never block track identification.
