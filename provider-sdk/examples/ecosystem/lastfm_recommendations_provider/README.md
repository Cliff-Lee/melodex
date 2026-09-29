# Last.fm Recommendations Example

A recommendation-only MPP provider. It deliberately does **not** claim search or playback capability.

It demonstrates:

- `recommendations.get`;
- a provider that contributes discovery without becoming a playback source;
- required `secret` configuration;
- a user-owned API credential brokered as `_melodex_config.api_key`;
- normalized recommendation tracks that can subsequently be resolved against other Melodex playback providers.

## Setup

Create/use your own Last.fm API key and enter it in the plugin settings. Melodex does not ship a shared project credential.

A recommendation result is metadata, not a claim that Last.fm hosts playable audio. The intended composition is:

```text
current/seed track
    -> Last.fm Recommendations
    -> artist/title suggestions
    -> Melodex resolver
    -> an installed playback provider
```
