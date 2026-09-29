# Ecosystem Architecture

This is the canonical high-level map of the current Melodex extension platform.

## The whole system

```text
                         DISCOVERY / DISTRIBUTION

                      GitHub / author releases
                               │
                               ▼
                         Registry index
                               │
                               ▼
                         Plugin Directory
                    HTTPS + size + SHA-256
                               │
             ┌─────────────────┴─────────────────┐
             │                                   │
       .mdxprovider                         .mdxplugin
             │                                   │

                              RUNTIME

     ┌──────────────────┐              ┌──────────────────┐
     │ Provider Manager │              │ Capability Broker│
     │       MPP        │              │ v0.1 contracts   │
     └────────┬─────────┘              └────────┬─────────┘
              │                                 │
       catalog/playback                 identity/metadata
              │                       artwork/lyrics/context
              │                        library suggestions
              └──────────────┬──────────────────┘
                             ▼
                    Universal Resolver
                             │
                    progressive metadata
                             │
                         Player / Flow

                         EXTERNAL CONTROL

                REST / OpenAPI / MCP / OpenAI
                             │
                             ▼
                         Melodex Core
```

The registry is **not** the runtime. The runtime does not require the registry after a plugin is installed.

## Package boundaries

### `.mdxprovider`

Use when the integration supplies a music/catalog source.

Typical jobs:

```text
search
browse
track / album / artist
playback.resolve
offline (when authorized)
library
recommendations
auth
```

Desktop Python providers currently run as separate processes speaking newline-delimited JSON-RPC.

### `.mdxplugin`

Use when the integration enriches an entity Melodex can already use.

Current experimental v0.1 jobs:

```text
identity.resolve
metadata.enrich
artwork.lookup
lyrics.lookup
context.lookup
library.suggest
```

These also run outside the GUI process.

## Core owns composition

Plugins contribute capabilities and candidates.

Melodex Core owns:

- provider lifecycle;
- resolver/fallback;
- queue/player;
- capability routing;
- merge policy;
- taste/Flow;
- external-control API;
- user-facing installation state.

A plugin should not reach into Core databases or UI internals. Local-intelligence plugins receive privacy-preserving snapshots brokered by Core instead of direct library/taste-database access.

## Progressive enrichment

```text
raw provider result
      ↓
playable
      ↓
identity
      ↓
metadata
      ↓
artwork
      ↓
lyrics
```

A slow artwork or lyrics service should not prevent playback.

## Identity layers

A provider-local ID:

```json
{
  "provider_id": "org.example.source",
  "provider_track_id": "8472"
}
```

is not automatically a global identity.

Cross-provider identity may use:

```text
ISRC
MusicBrainz recording/release/artist IDs
Wikidata IDs
```

The Capability Broker can add canonical identity after discovery.

## Trust boundary

Current desktop isolation means:

```text
Melodex GUI process
      │
      ├── JSON-RPC ── provider process
      │
      └── JSON-RPC ── capability-extension process
```

A process crash or protocol timeout can be isolated from the player.

This is **fault isolation, not a complete OS sandbox**.

See [Status, stability and trust](00_STATUS_AND_STABILITY.md) and [Permissions and security](07_PERMISSIONS_SECURITY.md).

## Distribution boundary

Community authors normally host their own source and package releases.

The Melodex registry stores discoverability/trust metadata:

```text
stable ID
publisher
version
capabilities
licence
source repository
package URL
SHA-256
byte size
compatibility
permissions
source policy
review status
```

Melodex can therefore be open and decentralized without making Core responsible for every integration.

## Code map

| Area | Location |
| --- | --- |
| Desktop provider runtime | `desktop/melodex/provider.py` |
| Provider manager | `desktop/melodex/provider_manager.py` |
| Capability Broker | `desktop/melodex/capabilities.py` |
| Registry client | `desktop/melodex/plugin_registry.py` |
| Plugin Directory UI | `desktop/melodex/plugin_directory.py` |
| Universal resolver | `desktop/melodex/resolver.py` |
| Local control API | `desktop/melodex/bridge_server.py` |
| OpenAPI schema | `desktop/melodex/api_schema.py` |
| OpenAI tool schemas | `desktop/melodex/openai_tools.py` |
| Provider SDK | `provider-sdk/` |
| Capability schemas | `provider-sdk/spec/extensions/v0.1/` |
| Canonical registry | `provider-sdk/registry/registry.json` |

## Where to start

If you want to build something rather than study architecture first, use the [5-minute developer quickstart](../DEVELOPER_QUICKSTART.md).
