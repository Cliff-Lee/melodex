# Privacy

Melodex is designed to be **local-first**, not network-free.

The current public code contains **no Melodex-operated account system, advertising SDK, analytics SDK, crash-reporting service, or telemetry endpoint**.

That does not mean Melodex never makes network requests. Network activity depends on the sources, plugins and optional integrations you choose to use.

## Stored locally

Depending on the features you use, Melodex can store locally:

- music folder locations and local-library indexes;
- Flow/audio-analysis data;
- listening history, completion and skip events;
- Love / Keep / dislike feedback;
- Moments, playlists and Vibes;
- provider/source configuration;
- user-added stream URLs;
- resolver preferences and wrong-match memory;
- cached artwork/metadata;
- installed provider/extension files;
- plugin registry cache;
- plugin installation provenance, including package hashes/version/source;
- local Bridge/MCP state and bearer tokens;
- optional LLM endpoint/model configuration.

Exact storage locations vary by platform. See the platform installation guides and troubleshooting documentation.

## Network requests

Melodex can contact third-party services when you deliberately use features that depend on them.

Examples include:

- Jamendo, when its reference provider is configured and used;
- music/catalog providers you install or connect;
- the Plugin Directory registry when it is opened/refreshed;
- MusicBrainz/Wikimedia or other enrichment services when the relevant feature/extension is active;
- direct radio/stream URLs added by the user;
- a Provider Bridge on your LAN;
- an MCP endpoint/client connection;
- an LLM/model endpoint you configure.

Those services receive the network information and request data needed to answer the request. Their own privacy policies/terms apply.

## Plugin Directory

Opening/refreshing the Plugin Directory fetches the public Melodex registry.

Installing a registry package downloads the package from the HTTPS URL listed in the registry and verifies its size/hash/identity before installation.

Melodex records local installation provenance so it can distinguish registry-verified installs from manual packages.

## Third-party plugins

A desktop `.mdxprovider` or `.mdxplugin` contains executable third-party code.

Current permission declarations improve transparency but are not a complete OS sandbox. A plugin with network access may contact external services according to its implementation.

Review the plugin's source, permissions, source policy and publisher information where available.

See [Security](../SECURITY.md) and [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md).

## LLM / AI

Melodex does **not** require an LLM.

Nothing is sent to an LLM/model service unless you configure one and make a request that uses it.

Depending on the feature, a request may contain a compact subset of:

- the current prompt;
- recent Ask Melodex conversation;
- current track;
- upcoming queue;
- taste summary;
- recent listening context.

Provider passwords, playback cookies, Bridge tokens and plugin credentials should not be placed in model context.

A local model such as Ollama can keep the model-inference part of the workflow on the local machine.

## Provider Bridge / MCP

Bridge and MCP bearer tokens should be treated like passwords.

A Bridge client sends search/control requests to the computer running Melodex. Remote/LAN clients may therefore reveal requested search terms and playback actions to that Melodex host.

Do not expose an unauthenticated Bridge/MCP service to an untrusted network.

## Android

The Android preview is a Bridge client. Search/resolve requests go to the configured Melodex Bridge and media is then played from the returned source.

The public Android code does not contain a Melodex telemetry SDK.

## Deleting local data

Uninstalling the application does not necessarily remove the separate Melodex application-data directory.

The macOS and Windows installation guides explain how to remove local Melodex state deliberately.

## Project transparency rule

If telemetry, accounts, hosted sync, crash reporting or another Melodex-operated data service is added later, this page should be updated **before** that behavior is presented as part of the normal product.
