<p align="center">
  <img src="docs/images/melodex.jpg" width="100%" alt="Melodex — Don't shuffle. Flow.">
</p>

<p align="center">
  <strong>A local-first music player — and an open platform for music sources, metadata, automation and AI tools.</strong>
</p>

<p align="center">
  <a href="https://github.com/Cliff-Lee/melodex/releases/latest"><strong>Download</strong></a> ·
  <a href="docs/START_HERE.md">Start here</a> ·
  <a href="docs/DEVELOPERS.md">Developers</a> ·
  <a href="docs/FIRST_CONTRIBUTION.md">Contribute</a> ·
  <a href="docs/README.md">Documentation</a>
</p>

# Melodex

> **Development documentation:** this README follows the current `main` branch. Downloadable GitHub Releases are tagged snapshots and may lag behind `main`. See [Releases, `main`, and version numbers](docs/RELEASES_AND_MAIN.md).

## Don't shuffle. Flow.

Melodex is a source-neutral music player that tries to make listening sessions **go somewhere**.

It combines your library and connected sources with taste memory, optional audio analysis, **Flow** sequencing, **Play for me**, a local **Music Map**, Moments, and a resolver that can match requested music across multiple providers.

But Melodex is also becoming something broader:

> **An open music platform where independent extensions contribute capabilities and Melodex combines them.**

A playback source does not need to become a metadata database. An artwork plugin does not need to know how the queue works. An AI client does not need to know which provider ultimately plays a track.

## Build something in 5 minutes

If you want to develop rather than study the architecture first:

**[→ 5-minute developer quickstart](docs/DEVELOPER_QUICKSTART.md)**

For the precise current state—including what is implemented, preview, experimental, planned, or not sandboxed—see **[Status, stability and trust](docs/developers/00_STATUS_AND_STABILITY.md)**.

## Choose your path

| I want to… | Start here |
| --- | --- |
| Use Melodex as a music player | [5-minute start](docs/START_HERE.md) |
| Build something quickly | [5-minute developer quickstart](docs/DEVELOPER_QUICKSTART.md) |
| Build a music source / playback provider | [Provider tutorial](docs/tutorials/BUILD_A_PROVIDER.md) |
| Add metadata, identity, artwork or lyrics | [Enrichment tutorial](docs/tutorials/BUILD_AN_ENRICHMENT_PLUGIN.md) |
| Control Melodex from another app | [REST/OpenAPI tutorial](docs/tutorials/CONTROL_MELODEX_WITH_REST.md) |
| Connect OpenWebUI or another MCP client | [MCP tutorial](docs/tutorials/CONNECT_OPENWEBUI_MCP.md) |
| Use Melodex from an OpenAI application | [OpenAI function tutorial](docs/tutorials/USE_OPENAI_FUNCTIONS.md) |
| Browse/install community extensions | [Plugin Directory](docs/PLUGIN_DIRECTORY.md) |
| Publish a community plugin | [Registry tutorial](docs/tutorials/ADD_PLUGIN_TO_REGISTRY.md) |
| Make a first contribution to this repository | [First contribution](docs/FIRST_CONTRIBUTION.md) |
| Explore other community contribution paths | [Community guide](docs/COMMUNITY.md) |

## The developer platform

Melodex separates discovery/distribution from runtime capabilities and external control:

```text
                         Plugin Directory
                               │
                  Registry + registry-verified packages
                               │
             ┌─────────────────┴─────────────────┐
             │                                   │
       .mdxprovider                         .mdxplugin
             │                                   │
      Provider Manager                    Capability Broker
             │                                   │
        catalog/playback        identity/metadata/artwork/lyrics/context
                                      local intelligence
             └─────────────────┬─────────────────┘
                               ▼
                    resolver + player + Flow
                               ▲
                               │
                REST / OpenAPI / MCP / OpenAI
```

The [ecosystem architecture](docs/developers/01_ECOSYSTEM_ARCHITECTURE.md) gives the detailed map.

### 1. MPP — music-source providers

Use the Melodex Provider Protocol when you want to connect a music source.

Current provider capabilities include:

```text
search  browse  track  album  artist
playback  library  offline  recommendations  auth
```

Start with [Build a provider](docs/tutorials/BUILD_A_PROVIDER.md) or read the [Provider SDK](provider-sdk/README.md).

### 2. Capability extensions

Melodex now has a runnable **Capability Broker** for small enrichment extensions. The v0.1 contracts are still experimental, but `.mdxplugin` packages can be installed and composed today:

```text
identity.resolve
metadata.enrich
artwork.lookup
lyrics.lookup
context.lookup
library.suggest
```

The aim is composition: playback from one source, canonical identity from another, artwork/context from others, and privacy-preserving local intelligence over the user's own library.

Install extensions through **Sources → Explore plugins…**, or start with [Build an enrichment plugin](docs/tutorials/BUILD_AN_ENRICHMENT_PLUGIN.md).

### 3. REST + OpenAPI

A running desktop app exposes an authenticated local control API for searching, resolving, queueing and playback control.

Key operations include:

```text
GET  /openapi.json
GET  /v1/providers
GET  /v1/extensions
GET  /v1/search
GET  /v1/resolve
GET  /v1/resolve-candidates
GET  /v1/status
GET  /v1/openai/tools

POST /v1/play
POST /v1/queue
POST /v1/control
```

The platform work also defines an OpenAPI contract so external tools can discover this surface instead of reverse-engineering Melodex.

Start with [Control Melodex with REST](docs/tutorials/CONTROL_MELODEX_WITH_REST.md).

### 4. MCP + OpenAI tools

Melodex exposes high-level music actions to AI systems rather than giving models raw provider internals.

Examples:

```text
melodex_search
melodex_resolve
melodex_extensions
melodex_play
melodex_queue
melodex_playback
melodex_flow
melodex_feedback
```

Use [MCP with OpenWebUI](docs/tutorials/CONNECT_OPENWEBUI_MCP.md) or [OpenAI function calling](docs/tutorials/USE_OPENAI_FUNCTIONS.md).

## Explore your library spatially

The desktop **Music Map** turns cached Flow analysis into a zoomable local sonic landscape. Nearby tracks share similar combinations of tempo, energy, key, timbre, rhythmic density and mixability; colour modes can expose energy, taste strength or rediscovery potential.

The same fixed dots can switch from **Sounds similar · Flow** to **Actually connected** overlays built from cached artists/albums, production and performer credits, compositions/works, samples/remixes/versions, artist relationships and recording places. Normal listening grows that local knowledge index; explicit map enrichment can fill gaps.

A selected node can be played, queued, or used as the anchor for a new Mind + Flow journey. **Pathfinder** can connect two mapped tracks using Balanced, Sonic or Knowledge-first routing, drawing a numbered route and explaining every hop before it is played or queued.

**Journey Designer** layers transparent semantic waypoints on top: Calm, Darker, Forgotten, Energetic, Bright, Rhythmic, Familiar, Surprising, or an exact chosen track. Its first preset builds a **Calm → Darker → Forgotten → Energetic** arc and records the fit/reason for every selected stage.

**Journey Live** can then adapt only the unfinished tail while playback continues: steer calmer/more energetic/darker/brighter, ask for more rhythm/familiarity/surprise/rediscovery, avoid the current artist, or manually skip and replan. The current track and fixed destination stay anchored, and failed replans keep the existing queue.

The **Journey Library** separates reusable intent from personal history. Recipes save/share routing mode + ordered stages as `.mdxjourney` without local paths or taste data; private Runs keep the designed route, final adapted route and explicit steering/skip/avoid decisions so either route can be inspected and replayed later.

The first implementation is deterministic, local and dependency-light rather than using a remote embedding service or opaque ML model.

## Reference extensions

The ecosystem is being developed with small examples built around documented, legal/open-access sources:

| Example | What it demonstrates |
| --- | --- |
| Radio Browser | station search + live playback |
| LibriVox | public-domain search + playback + offline |
| MusicBrainz | canonical identity + metadata provenance |
| Wikimedia Commons | artwork + per-file licence/attribution |
| MusicBrainz Song Connections | samples/remixes/works/recording-place context |
| Wikimedia Liner Notes | sourced encyclopedic context cards |
| ListenBrainz Community Pulse | aggregate community listening context |
| Sonic Neighbours | local Flow-feature “more like this” |
| Forgotten Favourites | private local rediscovery |
| Bridge Builder | local transition bridge suggestions |

The examples are designed to be copied, studied and changed. Canonical examples are packaged with exact SHA-256/size metadata and surfaced through the desktop [Plugin Directory](docs/PLUGIN_DIRECTORY.md).

## Community philosophy

You do not need to understand the whole Melodex codebase to contribute.

**Build one useful thing.**

- Know a music API? Build a provider.
- Know a metadata or artwork source? Build one capability.
- Build AI software? Use MCP or the function schemas.
- Build another app? Use REST/OpenAPI.
- Don't code? Help with testing, documentation, accessibility, translations, source research or UX.

New to the repository? Start with **[Your First Melodex Contribution](docs/FIRST_CONTRIBUTION.md)**.

See [Community](docs/COMMUNITY.md) for the wider set of contribution paths.

## Source-neutral and rights-aware

Melodex is designed for music and media the user is authorised to access.

A public API existing does **not** automatically mean media may be redistributed, downloaded or commercially reused. Public/community extensions should document API terms, rate limits, caching, offline rules, attribution and per-item rights.

See [Source and rights policy](docs/developers/11_SOURCE_AND_RIGHTS_POLICY.md).

## Download

You do **not** need Python or Git to use release builds.

If a feature described elsewhere in this repository is missing from your installed build, check [Releases, `main`, and version numbers](docs/RELEASES_AND_MAIN.md): current documentation can describe work added after the latest tagged binary.

- [Latest release](https://github.com/Cliff-Lee/melodex/releases/latest)
- [macOS installation](docs/INSTALL_MACOS.md)
- [Windows installation](docs/INSTALL_WINDOWS.md)
- [Android installation](docs/INSTALL_ANDROID.md)

## Build Melodex itself

```bash
git clone https://github.com/Cliff-Lee/melodex.git
cd melodex
```

Useful starting points:

```text
desktop/       desktop player, resolver and local API
android/       Android client
provider-sdk/  provider SDK, schemas and examples
docs/          user and developer documentation
```

For the shortest repository-onboarding path, read [Your First Melodex Contribution](docs/FIRST_CONTRIBUTION.md), then [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Melodex code is MIT licensed unless a subdirectory states otherwise. External music, artwork, lyrics and metadata retain their original licences and rights.

See [LICENSE](LICENSE), [RESPONSIBLE_USE.md](RESPONSIBLE_USE.md), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
