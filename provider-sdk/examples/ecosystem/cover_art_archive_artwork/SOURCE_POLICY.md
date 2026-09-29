# Source Policy — Cover Art Archive Artwork Example

## Upstream

- API: `https://coverartarchive.org`
- Identifiers: MusicBrainz release or release-group MBIDs.
- Authentication: none.
- Declared extension network permission: `coverartarchive.org`.

The Cover Art Archive API may return image URLs hosted by Internet Archive. The extension returns those asset URLs to Melodex but does not itself fetch them.

## Rights

Cover Art Archive is a repository/index of cover images connected to MusicBrainz releases. Copyright and reuse rights can vary per image. The extension therefore does **not** claim that returned artwork is freely licensed. Provenance explicitly tells the user to inspect the linked source.

The plugin source code is MIT licensed; returned artwork is not relicensed by Melodex.

## Caching

Successful results request a seven-day TTL. Missing artwork can be retried later because community-curated cover art changes over time.
