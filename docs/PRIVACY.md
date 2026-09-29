# Privacy

Melodex is designed to be local-first, but **local-first does not mean no network activity**, and it does not mean every local secret is currently stored in an operating-system credential vault.

This page describes the current implementation rather than an intended future state.

## Stored locally

Melodex stores local application state including:

- music folder locations;
- Flow analysis and fingerprints;
- listening history;
- completion and skip events;
- Love / Keep feedback;
- Moments;
- saved playlists and Vibes;
- provider configuration;
- installed-plugin provenance;
- Plugin Directory cache/download state;
- LLM endpoint and model configuration.

## LLM API key storage

**Current implementation:** if you enter an LLM API key in **Ask Melodex → Connect LLM**, the key is stored in Melodex's local SQLite preferences database.

It is not committed to Git and Melodex does not intentionally send it anywhere except the configured model endpoint.

However, it is **not currently protected by the operating system's credential vault**.

A user or process that can read your Melodex application-data directory may therefore be able to read that key.

Moving third-party credentials to an OS-backed credential/configuration broker is a trust-roadmap item.

## What Ask Melodex sends

Nothing is sent to a configured LLM until you submit an Ask Melodex prompt.

For the current desktop GUI, the model request can include:

```text
current track
up to 12 upcoming queue items
current Melodex page
taste summary
up to 15 recent tracks
up to 10 saved Vibes
your current prompt
```

The current GUI does **not** send prior Ask Melodex chat history between requests.

Track data is reduced through a positive allowlist before it enters model context. Melodex keeps only allowlisted descriptive fields such as title, artist, album, duration, provider label and limited recent-history timing/completion metadata.

Provider-local track IDs, absolute filesystem paths, playback URLs, request headers, cookies, refresh tokens, Bridge tokens, MCP tokens and API keys are excluded from track context.

If you use a remote model service, that service receives the prompt/context over the network and its own privacy and retention policies apply.

A local Ollama endpoint can keep model inference on your own machine.

## Other network activity

Melodex can use the network when you deliberately use features that require it, for example:

- searching or browsing an online music provider;
- opening **Explore plugins…** and refreshing/downloading from the Plugin Directory;
- metadata or artwork enrichment that uses a network source;
- connecting to OpenWebUI, OpenAI or another remote model endpoint;
- using Provider Bridge or MCP across a LAN.

Local-file playback itself does not require those services.

## Music Map

The desktop Music Map is a Core-owned local view. It reads cached Flow analysis and local taste signals from Melodex's own application state and does not require a remote embedding service.

Opening the map uses cached analysis and cached local knowledge only. Full-library audio analysis happens only when the user chooses **Analyse my library**.

The map's projection and knowledge graph are computed locally and are not sent to the Plugin Directory, an LLM or a remote recommendation service.

Normal Now Playing enrichment can be remembered in the local Music Map knowledge index. The explicit **Enrich selected** and **Enrich map (+8)** controls may contact MusicBrainz and enabled context plugins; they are user-initiated network enrichment, not background crawling.

**Pathfinder** is local. Route finding uses the current map's cached standardized Flow vectors and cached factual edges. It does not contact metadata services, plugins, an LLM or a remote recommender merely to find a path.

**Journey Designer** is also local. Semantic stages are scored from Flow/taste values already present in the current map, and staged routes reuse the prepared Pathfinder graph. Building a journey does not send the stage sequence or your library to an LLM or remote planner.

## Local intelligence plugins

The `library.suggest` contract is designed so useful local recommendation tools do not need the user's filesystem paths or taste database.

For each request Melodex creates ephemeral refs such as `t0` and can send:

```text
title / artist / album / duration
cached Flow analysis values
play/completion/skip/love/keep counts
relative days since last play
```

The contract does not include absolute local paths, provider-local IDs, SQLite/database keys, raw audio or absolute listening timestamps. Core retains the real track objects and maps returned ephemeral refs back after the plugin responds.

This is a **data-minimisation boundary**, not an OS sandbox. As with other desktop plugins, executable third-party extension code still runs with the current user's operating-system permissions unless stronger platform sandboxing is configured.

## Provider Bridge

The desktop app starts a loopback-only authenticated control bridge for local integrations.

If you explicitly enable LAN access, devices that can reach the Bridge and possess its bearer token can access the exposed API/source operations.

The Bridge state file contains the current bearer token and is written with user-only file permissions (`0600`) where the operating system supports them.

Treat the token like a password.

## MCP bearer token

The HTTP MCP token is also stored locally and written with `0600` where supported.

Do not paste Bridge or MCP tokens into model prompts, screenshots, public logs or issue reports.

## Third-party plugins

Desktop `.mdxprovider` and `.mdxplugin` packages can contain executable third-party code.

Process separation improves crash and failure isolation, but it is **not a complete operating-system sandbox**. A plugin can have the current user's OS permissions unless stronger platform sandboxing is configured.

Declared plugin permissions are transparency/review metadata today; they should not be read as universal OS-level enforcement.

See:

- [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md)
- [Permissions and security](developers/07_PERMISSIONS_SECURITY.md)
- [Security](../SECURITY.md)
