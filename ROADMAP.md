# Melodex Roadmap

The roadmap has two parallel goals:

1. make Melodex an excellent local-first music player;
2. make Melodex a useful open music platform that other developers can extend.

## Current foundation

- macOS and Windows desktop builds
- Android Bridge client
- Local Files and external providers
- MPP provider installation
- universal multi-source resolver
- resolver inspection and per-song match memory
- Flow
- Play for Me
- taste memory
- Moments
- optional LLM control
- local authenticated control bridge
- MCP control server
- OpenAI-compatible LLM client

## Ecosystem — current work

- developer documentation portal
- provider tutorials
- experimental capability contracts: identity, metadata, artwork and lyrics
- provenance/merge model
- plugin registry design
- legal/open reference providers
- OpenAPI contract for the local control API
- OpenAI function-tool schemas
- example community plugins
- desktop Capability Broker for identity, metadata, artwork and lyrics
- `.mdxplugin` install/enable/disable/remove flow
- `melodex-extension` init/validate/doctor/pack tooling
- registry-backed Plugin Directory in the desktop app
- SHA-256 verified remote package installation
- canonical registry with installable legal/open reference packages
- `melodex-registry` validate/verify tooling
- installation provenance (manual vs registry, package hash/version/time)
- Plugin Directory update awareness
- 5-minute developer quickstart + explicit status/stability/trust documentation
- CI documentation-link integrity checks

## Next — trust and platform

- child-process environment scrubbing;
- explicit credential/configuration broker for third-party providers;
- richer user-configurable preferred capability-provider UI;
- capability/provider health and diagnostics UI;
- redacted diagnostic export;
- stronger permission-policy enforcement where practical;
- registry review history;
- signed provider/plugin packages;
- verified-publisher keyring / revocation;
- generated API-client examples.

## Next — player

- improved local-library indexing
- artwork cache
- more reliable phrase/beat-grid analysis
- transition preview UI
- Android queue and Flow controls
- taste sync through Bridge

## Later

- optional encrypted multi-device state sync
- iOS client through Provider Bridge
- desktop stem-assisted transitions where hardware permits
- audio-analysis extension capabilities
- playlist import/export ecosystem
- scrobbling capability
- presence/now-playing capability
