# Source Policy — Openverse Audio Example

## Upstream

- API: `https://api.openverse.org/v1/audio/`
- Purpose: search openly licensed/public-domain audio indexed by Openverse.
- Authentication: none required for this example.
- Network permission: `api.openverse.org` for catalogue/item lookup. Playback is resolved to the exact media origin selected by the Openverse result.

## Rights and attribution

Openverse indexes Creative Commons and public-domain media, but Openverse explicitly warns that it cannot guarantee the accuracy of every licence record. This provider preserves the upstream landing page, licence code/version, licence URL and attribution returned by the API so users can inspect the original source.

The provider code is MIT licensed. Media found through Openverse remains under the licence shown for that individual work; it is not relicensed by Melodex.

## Playback and offline use

The provider follows the selected media URL's normal HTTP redirects before returning the final stream URL to Melodex. This prevents legitimate CDN redirects from being blocked by Melodex's guarded playback gateway. It does not declare the Melodex `offline` capability.

## Caching and load

Search responses are not persisted by the example. Melodex may apply its normal session/runtime caching. Consumers should respect Openverse throttling and API guidance.
