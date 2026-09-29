# Source Policy — ListenBrainz Community Pulse

## Upstream

- Recording popularity: `POST https://api.listenbrainz.org/1/popularity/recording`
- Artist top recordings: `GET https://api.listenbrainz.org/1/popularity/top-recordings-for-artist/{artist_mbid}`
- Health: `GET https://api.listenbrainz.org/1/status/service-status`
- Authentication: none for the endpoints used here.

## Privacy

Only MusicBrainz recording/artist identifiers are sent. No ListenBrainz username, user token, listening history or personal feedback is sent.

## Rights and provenance

The plugin displays aggregate service output with explicit ListenBrainz/MetaBrainz provenance and does not make a blanket licensing claim for every derived statistic. Synthetic fixture data is bundled for tests; live popularity data is fetched on demand.

## Caching

Popularity is intentionally short-lived and requests a six-hour TTL.
