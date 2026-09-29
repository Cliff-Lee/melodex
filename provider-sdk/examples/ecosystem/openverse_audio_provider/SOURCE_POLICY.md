# Source Policy — Openverse Audio Example

## Upstream

- API: `https://api.openverse.org/v1/audio/`
- Purpose: search openly licensed/public-domain audio indexed by Openverse.
- Authentication: none required for this example.
- Network permission: `api.openverse.org`.

## Rights and attribution

Openverse indexes Creative Commons and public-domain media, but Openverse explicitly warns that it cannot guarantee the accuracy of every licence record. This provider preserves the upstream landing page, licence code/version, licence URL and attribution returned by the API so users can inspect the original source.

The provider code is MIT licensed. Media found through Openverse remains under the licence shown for that individual work; it is not relicensed by Melodex.

## Playback and offline use

The provider returns the direct media URL supplied by Openverse for streaming. It does not declare the Melodex `offline` capability. A particular Creative Commons licence may permit downloading, but the example avoids translating licence metadata into an automatic offline-use decision.

## Caching and load

Search responses are not persisted by the example. Melodex may apply its normal session/runtime caching. Consumers should respect Openverse throttling and API guidance.
