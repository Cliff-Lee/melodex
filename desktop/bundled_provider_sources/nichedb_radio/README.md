# NicheDB Radio provider

A bundled Melodex source for the NicheDB radio collection.

NicheDB maintains a daily-refreshed index of internet-radio stations sourced from Radio Browser and exposes a normalized, keyless read API. The provider uses NicheDB for discovery and metadata, then sends playback directly to the station stream supplied in the NicheDB item.

## Capabilities

- normal text search, such as `jazz`, `BBC`, `ambient` or a station name;
- `popular` for currently popular working stations;
- `genre:ambient`, `country:gb`, `lang:english`, and `codec:mp3` power searches;
- live playback of stations NicheDB currently marks online;
- station artwork when supplied;
- country, language, genre, codec, bitrate, votes/listens and coordinates preserved as metadata.

The anonymous API does not require an account or key. `NICHEDB_API_KEY` can optionally be supplied in the environment for deployments that have a higher API allowance.

Offline downloads are deliberately disabled because these are live radio streams.

NicheDB API documentation: <https://nichedb.dev/docs/api>
