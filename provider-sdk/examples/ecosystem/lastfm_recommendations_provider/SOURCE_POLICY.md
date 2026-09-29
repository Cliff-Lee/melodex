# Source Policy — Last.fm Recommendations Example

## Upstream

- API: Last.fm Web Services, `https://ws.audioscrobbler.com/2.0/`
- Method: `track.getSimilar`
- Authentication: user/developer-supplied API key.
- Melodex ships no shared Last.fm credential.
- Declared network host: `ws.audioscrobbler.com`.

Developers/users should review the current Last.fm API terms applicable to their use of an API key. This example is intentionally metadata/discovery-only and does not scrape pages or attempt to derive playback URLs.

## Credentials

The API key is declared as Melodex configuration type `secret`. The host brokers it to the provider in `_melodex_config`; it should not appear in track metadata, logs, diagnostics or registry data.

## Playback / media

None. Recommendation results are normalized track identities/hints with `metadata.playable=false`. Melodex should resolve a chosen suggestion through another playback-capable provider.

## Caching

The example does not persist Last.fm responses itself. Recommendation similarity can change over time, so host-side long-term persistence should be conservative.
