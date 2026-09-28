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
  <a href="docs/COMMUNITY.md">Community</a> ·
  <a href="docs/ALL_DOCUMENTATION.md">Documentation</a>
</p>

# Melodex

## Don't shuffle. Flow.

Melodex is a source-neutral music player that tries to make listening sessions **go somewhere**.

It combines your library and connected sources with taste memory, optional audio analysis, **Flow** sequencing, **Play for Me**, Moments, and a resolver that can match requested music across multiple providers.

But Melodex is also becoming something broader:

> **An open music platform where independent extensions contribute capabilities and Melodex combines them.**

A playback source does not need to become a metadata database. An artwork plugin does not need to know how the queue works. An AI client does not need to know which provider ultimately plays a track.

## Choose your path

| I want to… | Start here |
| --- | --- |
| Use Melodex as a music player | [5-minute start](docs/START_HERE.md) |
| Build a music source / playback provider | [Provider tutorial](docs/tutorials/BUILD_A_PROVIDER.md) |
| Add metadata, identity, artwork or lyrics | [Enrichment tutorial](docs/tutorials/BUILD_AN_ENRICHMENT_PLUGIN.md) |
| Control Melodex from another app | [REST/OpenAPI tutorial](docs/tutorials/CONTROL_MELODEX_WITH_REST.md) |
| Connect OpenWebUI or another MCP client | [MCP tutorial](docs/tutorials/CONNECT_OPENWEBUI_MCP.md) |
| Use Melodex from an OpenAI application | [OpenAI function tutorial](docs/tutorials/USE_OPENAI_FUNCTIONS.md) |
| Publish a community plugin | [Registry tutorial](docs/tutorials/ADD_PLUGIN_TO_REGISTRY.md) |
| Contribute code, docs, testing or ideas | [Community guide](docs/COMMUNITY.md) |

## The developer platform

Melodex deliberately separates four integration layers:

```text
                           MELODEX
                              │
              ┌───────────────┼────────────────┐
              │               │                │
            MPP          REST / OpenAPI        MCP
      music providers     app control        AI tools
              │               │                │
              └───────────────┼────────────────┘
                              │
                       resolver + player
                              │
                              ▼
                   optional model backends
             OpenAI / OpenWebUI / Ollama / custom
```

### 1. MPP — music-source providers

Use the Melodex Provider Protocol when you want to connect a music source.

Current provider capabilities include:

```text
search  browse  track  album  artist
playback  library  offline  recommendations  auth
```

Start with [Build a provider](docs/tutorials/BUILD_A_PROVIDER.md) or read the [Provider SDK](provider-sdk/README.md).

### 2. Capability extensions

Melodex is extending beyond monolithic source plugins. Experimental contracts let small extensions contribute:

```text
identity.resolve
metadata.enrich
artwork.lookup
lyrics.lookup
```

The aim is composition: playback from one source, canonical identity from another, artwork from another, and lyrics from another — while retaining provenance.

Start with [Build an enrichment plugin](docs/tutorials/BUILD_AN_ENRICHMENT_PLUGIN.md).

### 3. REST + OpenAPI

A running desktop app exposes an authenticated local control API for searching, resolving, queueing and playback control.

Key operations include:

```text
GET  /v1/providers
GET  /v1/search
GET  /v1/resolve
GET  /v1/resolve-candidates
GET  /v1/status

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
melodex_play
melodex_queue
melodex_playback
melodex_flow
melodex_feedback
```

Use [MCP with OpenWebUI](docs/tutorials/CONNECT_OPENWEBUI_MCP.md) or [OpenAI function calling](docs/tutorials/USE_OPENAI_FUNCTIONS.md).

## Reference extensions

The ecosystem is being developed with small examples built around documented, legal/open-access sources:

| Example | What it demonstrates |
| --- | --- |
| Radio Browser | station search + live playback |
| LibriVox | public-domain search + playback + offline |
| MusicBrainz | canonical identity + metadata provenance |
| Wikimedia Commons | artwork + per-file licence/attribution |

The examples are designed to be copied, studied and changed.

## Community philosophy

You do not need to understand the whole Melodex codebase to contribute.

**Build one useful thing.**

- Know a music API? Build a provider.
- Know a metadata or artwork source? Build one capability.
- Build AI software? Use MCP or the function schemas.
- Build another app? Use REST/OpenAPI.
- Don't code? Help with testing, documentation, accessibility, translations, source research or UX.

See [Community](docs/COMMUNITY.md).

## Source-neutral and rights-aware

Melodex is designed for music and media the user is authorised to access.

A public API existing does **not** automatically mean media may be redistributed, downloaded or commercially reused. Public/community extensions should document API terms, rate limits, caching, offline rules, attribution and per-item rights.

See [Source and rights policy](docs/developers/11_SOURCE_AND_RIGHTS_POLICY.md).

## Download

You do **not** need Python or Git to use release builds.

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

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

## Licence

Melodex code is MIT licensed unless a subdirectory states otherwise. External music, artwork, lyrics and metadata retain their original licences and rights.

See [LICENSE](LICENSE), [RESPONSIBLE_USE.md](RESPONSIBLE_USE.md), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
