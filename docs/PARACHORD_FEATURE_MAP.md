# Parachord → Melodex Feature Map

This document tracks useful Parachord ideas against the Melodex architecture. The goal is not to clone Parachord; it is to adopt the useful source-neutral capabilities while preserving Melodex's simpler UI, Flow engine, taste memory and AI-first controls.

## Implemented / foundation in this update

- **Smart multi-source resolution** — metadata-only requests are matched across connected providers.
- **Source priority** — persistent provider ordering with simple up/down controls.
- **Mixed-source queues** — each queued track can resolve independently to a different source.
- **Resolver blocklist foundation** — a bad candidate can be blocked for one requested track without disabling its provider.
- **AI playlist resolution** — LLM-created track lists are resolved, saved and played.
- **Remote metadata resolve** — Provider Bridge `/v1/resolve` accepts provider/id or artist/title/album.
- **Resolver confidence / version protection** — title, artist and album similarity plus penalties for unintended live/remix/cover/etc. variants.

## Already present in Melodex

- Provider-neutral plug-in architecture (`.mdxprovider` / MPP).
- Local library scanning and playback.
- Search across connected sources.
- Queue and continuous playback.
- Flow transitions / crossfade planning.
- Taste memory, likes/dislikes, keeps, listening history and saved moments.
- Play For Me / journey generation.
- Optional OpenWebUI, Ollama, OpenAI-compatible LLM control.
- Provider Bridge for other devices/tools.

## High-value next additions

1. **MCP server** — expose search, resolve, queue, playback, current track, playlists, taste and Flow controls to ChatGPT/OpenWebUI/Claude-compatible agents.
2. **Playlist interchange** — XSPF, M3U and M3U8 import/export while retaining Melodex JSON for AI-generated playlists.
3. **Resolver inspector** — optional power-user panel showing candidate confidence and a `Wrong match` action wired to the blocklist.
4. **Volume normalization** — ReplayGain / loudness metadata where available, with conservative fallback gain.
5. **Scrobbling** — Last.fm and ListenBrainz as optional meta-service plug-ins rather than hard-coded providers.
6. **Recommendations / spinoff** — use ListenBrainz, Last.fm or AI to branch from a track while still resolving playback independently.
7. **Deep links** — `melodex://search`, `melodex://track`, `melodex://playlist` for browser/tools/automation.
8. **URL playlist import** — import supported public playlist URLs through meta/importer plug-ins, keeping playback resolution separate.
9. **Browser extension bridge** — optional extension that sends detected album/playlist metadata to Melodex rather than scraping inside the player.
10. **Auto-update checks** — GitHub Releases-based update notification; installation remains explicit.

## Deliberately not copied blindly

- Service-specific resolver code that creates licensing, credential or reliability problems.
- Features that duplicate Melodex Flow / Mind without improving the user experience.
- Provider logic embedded in the core player. New services should stay behind the provider/meta-service boundary.
- Anything that makes the public app depend on unofficial copyrighted-content sources.
