# Privacy

Melodex is designed to be local-first, but “local-first” does not mean “no network activity” and it does not mean every local secret is currently stored in an OS credential vault.

## Stored locally

Melodex stores local application state including:

- music folder locations;
- Flow analysis/fingerprints;
- listening history;
- completion and skip events;
- Love / Keep feedback;
- Moments;
- saved playlists and Vibes;
- provider configuration;
- installed-plugin provenance;
- Plugin Directory cache/download state;
- LLM endpoint/model configuration.

### LLM API key storage

**Current implementation:** if you enter an LLM API key in **Ask Melodex → Connect LLM**, the key is stored in Melodex's local SQLite preferences database.

It is not committed to Git or intentionally sent anywhere except the configured model endpoint, but it is **not currently protected by the operating system's credential vault**.

Anyone/process that can read your Melodex application-data directory may therefore be able to read that key.

Moving third-party credentials to an OS-backed credential broker is a trust-roadmap item.

## What Ask Melodex sends

Nothing is sent to a configured LLM until you submit a prompt.

For the current desktop GUI, the request context can include:

```text
current track
up to 12 upcoming queue items
current Melodex page
taste summary
up to 15 recent tracks
up to 10 saved Vibes
your current prompt
```

The current GUI does **not** send prior chat history to the model between Ask Melodex requests.

Provider passwords, provider playback cookies, Bridge tokens, MCP tokens and local filesystem paths are not intentionally added to this model context.

If you use a remote model service, that service receives the prompt/context over the network and its own privacy/retention policy applies.

A local Ollama endpoint can keep model inference on your own machine.

## Other network activity

Network access can also occur when you deliberately use features that require it, for example:

- searching/browsing an online music provider;
- opening **Explore plugins…** and refreshing/downloading from the Plugin Directory;
- metadata/artwork enrichment using configured/built-in network sources;
- connecting to a remote/OpenWebUI/OpenAI-compatible LLM endpoint;
- using Provider Bridge/MCP across a LAN.

Local-file playback itself does not require those services.

## Provider Bridge

The desktop app starts a loopback-only authenticated control bridge for local integrations.

If you explicitly enable LAN access, devices that can reach the Bridge and possess its bearer token can access the exposed API/source operations.

The Bridge state file contains the current token and is written with user-only file permissions (`0600`) where the operating system supports them.

Treat the token like a password.

## MCP bearer token

The HTTP MCP token is also stored locally and written with `0600` where supported.

Do not paste Bridge/MCP tokens into model prompts, screenshots, public logs or issue reports.

## Third-party plugins

Desktop `.mdxprovider` and `.mdxplugin` packages are executable third-party code.

Process separation improves failure isolation but is not a complete OS sandbox. A plugin can have the current user's OS permissions unless stronger platform sandboxing is configured.

See [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md) and [Security](../SECURITY.md).
