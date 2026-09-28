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

Provider and capability-extension subprocesses start with a **scrubbed child environment**.

Melodex forwards a small allowlist of ordinary operating-system/runtime variables plus the package identity and package-local Python path. Arbitrary parent API keys, tokens, cookies and unrelated credentials are not forwarded by default.

This reduces accidental secret inheritance. It is still **not** an operating-system sandbox.

## Declared configuration broker

Providers and capability extensions can declare configuration fields in their package metadata:

```json
{
  "configuration": [
    {"key": "api_token", "label": "API token", "type": "secret", "required": true},
    {"key": "region", "label": "Region", "type": "string"},
    {"key": "use_preview", "label": "Use preview API", "type": "boolean"}
  ]
}
```

Supported field types are `string`, `secret` and `boolean`.

The Sources page builds the configuration UI from those declarations. At runtime, Melodex sends only declared values to that plugin under the reserved `_melodex_config` request parameter.

Non-secret values are stored in Melodex's application-data configuration file. Secret values are stored in the operating-system credential store when a usable keyring backend is available. If secure persistent storage is unavailable, secrets fall back to **session-only memory** rather than being written to ordinary JSON.

A plugin declaration is not itself permission to read arbitrary Melodex settings or environment variables.

## Limited host enforcement

Provider `network_hosts` declarations are still **not a process-wide network sandbox**.

One narrower boundary is enforced today: when an external provider returns an HTTP(S) playback resource, the Playback Gateway checks the initial playback host and every redirect against the provider's declared `network_hosts`.

That prevents Melodex's own playback proxy from forwarding provider-supplied headers/cookies to undeclared playback hosts. It does **not** stop the plugin process itself from making other network connections with the current user's OS permissions.

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
