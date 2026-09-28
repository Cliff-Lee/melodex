# Extension Permissions and Security

This page describes the **current public implementation**, not an idealized future sandbox.

For the broader maturity table, see [Status, stability and trust](00_STATUS_AND_STABILITY.md).

## Minimum access principle

An extension should receive only what it needs.

Examples:

- artwork: canonical entity IDs and harmless display hints;
- lyrics: recording identity, title/artist and optional duration;
- identity: matching hints and existing non-secret identifiers.

An artwork plugin should never receive playback cookies or unrelated account secrets.

## Declared permissions

MPP manifests can declare:

```text
network_hosts
offline_downloads
local_files
browser_auth
lan_discovery
```

Capability-extension descriptors currently declare:

```text
network_hosts
local_files
browser_auth
```

These declarations are useful for:

- Plugin Directory transparency;
- code/source review;
- future policy enforcement;
- explaining expected behavior to users.

## Important: declarations are not universal OS enforcement

Desktop providers/extensions run in **separate processes**, which improves crash/failure isolation.

They are **not currently placed in a complete cross-platform OS sandbox**.

A third-party process still executes with the operating-system permissions of the user running Melodex unless the operating system/container environment adds stronger restrictions.

Therefore:

> “declared network hosts” currently means “this is what the plugin says it needs”, not “the kernel guarantees it cannot contact anything else”.

Do not describe current third-party plugins as sandboxed.

## Process environment

Current subprocess launchers inherit the Melodex process environment before adding their protocol/runtime variables.

That means unrelated secrets exported into Melodex's environment could also be visible to a third-party process.

Until environment scrubbing plus an explicit credential broker is implemented:

- do not launch Melodex with unrelated secrets exported into its environment;
- do not depend on secret environment variables as the public provider-authentication design;
- never put secrets in manifests, descriptors, registry entries or provenance.

Environment isolation/credential brokering is a trust-roadmap item.

## Secrets never belong in normalized objects

Do not place API keys, OAuth tokens, passwords, cookies, authorization headers, private session IDs, Bridge bearer tokens or LLM keys in:

- catalog objects;
- provenance;
- playlists;
- registry metadata;
- fixtures committed to Git;
- public logs.

## stdout/stderr

For desktop provider/extension processes:

```text
stdout -> protocol JSON only
stderr -> logs/debug output
```

A stray debug print on stdout can corrupt the protocol stream.

## Download permission is separate

`playback` does not imply `offline`.

Only expose download/offline behavior when the upstream source permits it.

## Registry integrity

Registry installs verify package byte size and SHA-256 before installation.

That proves:

```text
downloaded bytes == bytes named by registry metadata
```

It does **not** prove publisher identity.

Publisher signatures/key management are planned but not implemented.

## Manual installs

Manual `.mdxprovider` / `.mdxplugin` installs record a local package hash for provenance, but there is no registry metadata to compare it with.

Treat a manual package as code you explicitly chose to trust.

## Current trust vocabulary

Use these phrases precisely:

- **registry-verified package** — hash/size matched the registry;
- **reviewed registry entry** — project review status;
- **manual install** — user-selected local package;
- **signed publisher** — **not implemented yet**.

Do not substitute one label for another.
