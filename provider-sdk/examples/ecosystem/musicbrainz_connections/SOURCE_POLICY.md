# Source Policy — MusicBrainz Song Connections

## Upstream

- API: `https://musicbrainz.org/ws/2/recording/{MBID}`
- Data requested: recording relationships to recordings, releases, artists, works and places.
- Authentication: none.
- User-Agent: identifies Melodex and this example extension.
- Cache intent: persistent/long-lived; relationship data changes relatively slowly.

## Rights

MusicBrainz documents relationships and URLs as core database data. MusicBrainz core data is CC0. The plugin returns relationship facts/identifiers and links back to MusicBrainz rather than copying MusicBrainz documentation text.

## Privacy

Only the recording MBID being inspected is sent to MusicBrainz. No listening history, account identifier or credential is sent.
