# Source Policy — Openverse Audio Example

## Upstream

- API: `https://api.openverse.org/v1/audio/`
- Purpose: search openly licensed/public-domain audio indexed by Openverse.
- Authentication: none required for this example.
- Network permissions: `api.openverse.org` plus dynamic media hosts returned by Openverse. The provider follows the selected public media URL only to resolve its final HTTP(S) playback origin; Melodex then restricts the playback gateway to that concrete resolved host.

## Rights and attribution

Openverse indexes Creative Commons and public-domain media, but Openverse explicitly warns that it cannot guarantee the accuracy of every licence record. This provider preserves the upstream landing page, licence code/version, licence URL and attribution returned by the API so users can inspect the original source.

The provider code is MIT licensed. Media found through Openverse remains under the licence shown for that individual work; it is not relicensed by Melodex.

## Playback and offline use

The provider resolves the selected media URL to its final HTTP(S) origin before returning it for streaming. This prevents ordinary CDN redirects from being rejected by Melodex's exact-host playback gateway. It does not declare the Melodex `offline` capability. A particular Creative Commons licence may permit downloading, but the example avoids translating licence metadata into an automatic offline-use decision.

## Caching and load

Search responses are not persisted by the example. Melodex may apply its normal session/runtime caching. Consumers should respect Openverse throttling and API guidance.
