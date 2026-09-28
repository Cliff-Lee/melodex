# Radio Browser Example Provider

Current MPP example provider.

Capabilities:

```text
search
track
playback
```

Example searches:

```text
jazz
ambient
BBC
classical
```

The provider normalizes a radio station into a track-like catalog object because
the current MPP catalog schema has track/album/artist entities. A future radio
entity can improve this model without changing the upstream integration lesson.

The implementation:

- uses station UUID as stable provider identity;
- prefers `url_resolved` for playback;
- reports clicks through Radio Browser when playback is resolved;
- attempts mirror discovery and falls back between servers;
- uses a descriptive User-Agent.

Offline downloads are deliberately disabled.
