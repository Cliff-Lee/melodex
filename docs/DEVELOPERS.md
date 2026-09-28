# Developer Gateway

Use this page to decide **which Melodex interface fits what you want to build**.

You do not need to understand the entire player first. Once you choose a path, move to its focused tutorial rather than reading the whole developer reference.

## Fastest route

If you want a working scaffold before reading the architecture:

**[→ Build something in 5 minutes](DEVELOPER_QUICKSTART.md)**

If you want the exact current maturity/security picture first:

**[→ Status, stability and trust](developers/00_STATUS_AND_STABILITY.md)**

## Pick one path

| You want to build… | Interface | Tutorial |
| --- | --- | --- |
| A music source / streaming provider | **MPP** | [Build a provider](tutorials/BUILD_A_PROVIDER.md) |
| Metadata, identity, artwork or lyrics | **Capability extension** | [Build an enrichment plugin](tutorials/BUILD_AN_ENRICHMENT_PLUGIN.md) |
| A mobile/desktop/web controller | **REST + OpenAPI** | [Control Melodex with REST](tutorials/CONTROL_MELODEX_WITH_REST.md) |
| An OpenWebUI / AI integration | **MCP** | [Connect OpenWebUI](tutorials/CONNECT_OPENWEBUI_MCP.md) |
| An OpenAI tool integration | **Function calling** | [Use OpenAI functions](tutorials/USE_OPENAI_FUNCTIONS.md) |
| Browse/install extensions | **Plugin Directory** | [Plugin Directory](PLUGIN_DIRECTORY.md) |
| A community-distributed extension | **Registry** | [Publish a plugin](tutorials/ADD_PLUGIN_TO_REGISTRY.md) |

## Architecture at a glance

```text
registry / Plugin Directory
          │
   ┌──────┴──────┐
   │             │
providers   capability extensions
   │             │
   └──────┬──────┘
          ▼
resolver + player
          ▲
          │
REST / OpenAPI / MCP / OpenAI
```

See the [canonical ecosystem architecture](developers/01_ECOSYSTEM_ARCHITECTURE.md) for the full map.

## Important boundaries

**MPP is for music sources.** If your extension searches or plays music, start with the Provider SDK.

**Enrichment is separate.** Do not make an artwork or metadata service pretend to be a complete playback provider.

**AI systems get high-level tools.** An AI client should ask Melodex to search, resolve, play or queue. It should not receive provider passwords, cookies or raw implementation details.

**Core stays source-neutral.** Service-specific parsing and quirks belong in extensions.

## Good first projects

- a provider for a documented legal/open music source;
- a MusicBrainz identity experiment;
- a Wikimedia artwork experiment;
- a generated client for the OpenAPI schema;
- an MCP client example;
- documentation for a source's permissions and rights model.

## Need deeper reference?

Use the **[developer reference index](developers/README.md)** when you need architecture, capability contracts, permissions/security, testing, registry governance, review checklists or the glossary.

Key truth/reference pages:

- [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md)
- [Ecosystem architecture](developers/01_ECOSYSTEM_ARCHITECTURE.md)
- [Provider SDK](../provider-sdk/README.md)

For contribution paths rather than interface documentation, use [Community](COMMUNITY.md).
