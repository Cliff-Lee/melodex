# Parachord → Melodex Feature Map

This document tracks useful Parachord ideas against the Melodex architecture. The goal is not to clone Parachord; it is to adopt the useful source-neutral capabilities while preserving Melodex's simpler UI, Flow engine, taste memory and AI-first controls.

## Implemented

- **Smart multi-source resolution** — metadata-only requests are matched across connected providers.
- **Source priority** — persistent provider ordering with simple up/down controls.
- **Mixed-source queues** — each queued track can resolve independently to a different source.
- **Resolver blocklist foundation** — a bad candidate can be blocked for one requested track without disabling its provider.
- **AI playlist resolution** — LLM-created track lists are resolved, saved and played.
- **Remote metadata resolve** — Provider Bridge `/v1/resolve` accepts provider/id or artist/title/album.
- **Resolver confidence / version protection** — title, artist and album similarity plus penalties for unintended live/remix/cover/etc. variants.
- **MCP control server** — standard MCP tools expose status, search, resolution, queue, playback, Flow, volume, seeking, taste feedback and saved moments.
- **OpenWebUI-native MCP path** — optional Streamable HTTP server with bearer authentication; stdio remains available for desktop MCP clients.
- **Private GUI control bridge** — the desktop app starts a loopback-only authenticated bridge automatically; MCP never manipulates Qt objects from a second process.
- **Playlist interchange** — XSPF, M3U and M3U8 import/export, including metadata-only entries that re-resolve against connected providers.
- **Resolver Inspector** — candidate confidence, score breakdowns, version flags, duration checks and provider priority are visible from the player.
- **Persistent match memory** — per-song `Prefer`, `Wrong match`, and reset controls; rejecting a preferred match automatically clears the preference.
- **Resolver MCP controls** — external agents can inspect candidates and manage preferred/wrong-match memory through the same resolver.

## Already present in Melodex

- Provider-neutral plug-in architecture (`.mdxprovider` / MPP).
- Local library scanning and playback.
- Search across connected sources.
- Queue and continuous playback.
- Flow transitions / crossfade planning.
- Taste memory, likes/dislikes, keeps, listening history and saved moments.
- Play For Me / journey generation.
- Optional OpenWebUI, Ollama, OpenAI-compatible LLM control inside the app.
- Provider Bridge for other devices/tools.

## High-value next additions

1. **Volume normalization** — ReplayGain / loudness metadata where available, with conservative fallback gain.
2. **Scrobbling** — Last.fm and ListenBrainz as optional meta-service plug-ins rather than hard-coded providers.
3. **Recommendations / spinoff** — use ListenBrainz, Last.fm or AI to branch from a track while still resolving playback independently.
4. **Deep links** — `melodex://search`, `melodex://track`, `melodex://playlist` for browser/tools/automation.
5. **URL playlist import** — import supported public playlist URLs through meta/importer plug-ins, keeping playback resolution separate.
6. **Browser extension bridge** — optional extension that sends detected album/playlist metadata to Melodex rather than scraping inside the player.
7. **Auto-update checks** — GitHub Releases-based update notification; installation remains explicit.

## Deliberately not copied blindly

- Service-specific resolver code that creates licensing, credential or reliability problems.
- Features that duplicate Melodex Flow / Mind without improving the user experience.
- Provider logic embedded in the core player. New services should stay behind the provider/meta-service boundary.
- Anything that makes the public app depend on unofficial copyrighted-content sources.


## Rich Now Playing / music knowledge

- [x] MusicBrainz recording/artist/release identity and cache
- [x] Cover Art Archive artwork
- [x] embedded/provider/CAA artwork priority
- [x] full Now Playing information page
- [x] artist/band relationships, genres/tags and structured credits
- [x] local embedded / .lrc / .txt lyrics with synchronized highlighting
- [x] artwork-derived visual accent/background
- [ ] optional Last.fm / ListenBrainz enrichment
- [ ] Wikimedia/Wikidata artist photographs with attribution
- [ ] waveform / spectrum visualization


## Visual enrichment / artist visuals

- [x] Wikimedia Commons artist photographs via Wikidata links
- [x] MusicBrainz release-group timeline / discography lookup
- [x] album-cover wall / release timeline tab in Now Playing
- [ ] richer attribution / license display for artist photos
- [ ] click-through artist/release browsing pages
- [ ] waveform / spectrum / motion graphics
