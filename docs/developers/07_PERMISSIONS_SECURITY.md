# Extension Permissions and Security

## Minimum access

An extension should receive only what it needs.

Examples:

- artwork: canonical entity IDs and harmless display hints;
- lyrics: recording identity, title/artist and optional duration;
- identity: matching hints and existing non-secret identifiers.

An artwork plugin should never receive playback cookies.

## Current provider permissions

MPP manifests can declare:

```text
network_hosts
offline_downloads
local_files
browser_auth
lan_discovery
```

## Secrets never belong in catalog objects

Do not place API keys, OAuth tokens, passwords, cookies, authorization headers or private session IDs in normalized metadata or provenance.

## stdout/stderr

For desktop provider processes:

```text
stdout -> protocol JSON only
stderr -> logs/debug output
```

A stray debug print on stdout can corrupt the protocol stream.

## Download permission is separate

`playback` does not imply `offline`.

Only expose download/offline behavior when the upstream source permits it.
