# Melodex Universal Resolver

The universal resolver turns a source-neutral track request such as:

```json
{"artist":"Massive Attack","title":"Teardrop","album":"Mezzanine"}
```

into the best playable match available from the user's connected Melodex providers.

## Resolution order

1. If a track already contains a valid `provider_id` plus a provider track identity, Melodex tries that exact source first.
2. Otherwise Melodex searches each connected provider in user-configured priority order.
3. Candidates are scored using title, artist and album similarity.
4. Version mismatches such as live, remix, instrumental, karaoke, cover and acoustic variants are penalized.
5. Provider priority is used as a small tie-breaker rather than overriding a clearly better metadata match.
6. Candidates below the confidence threshold are rejected.
7. If one candidate cannot produce a playable stream, the resolver tries the next acceptable candidate.

## Provider priority

Priority is stored in `sources.json` as `provider_priority` and is exposed by `ProviderManager.provider_order()` / `set_provider_order()`.

## Bad-match blocklist

A bad candidate can be blocked only for the requested track. This avoids disabling an entire provider because of one incorrect version.

The blocklist is stored in `sources.json` as `resolver_blocklist`.

## AI playlists

Metadata-only playlists produced by ChatGPT, OpenWebUI, Ollama or another LLM can be resolved track by track. In the desktop app, **Playlists → Paste from AI…** accepts copied playlist text without connecting Melodex to that AI. Successfully matched tracks are saved and placed in the queue; unresolved requests remain with the saved playlist for later matching. Melodex does not send pasted text to an AI service, though connected music providers may receive artist/title searches during resolution. See [Playlist interchange](PLAYLIST_INTERCHANGE.md) for supported formats.

## API use

`ProviderManager.resolve()` is now the universal entry point. Existing source-specific tracks still resolve directly, while source-neutral metadata is matched across all connected providers. This is also the intended foundation for the Melodex MCP server and future remote-control APIs.
