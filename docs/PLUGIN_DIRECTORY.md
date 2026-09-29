# Melodex Plugin Directory

The desktop app includes a registry-backed **Plugin Directory** for discovering providers and capability extensions.

Open:

```text
Sources
→ Explore plugins…
```

## What the directory shows

Each entry can expose:

```text
name
stable plugin ID
publisher
version
kind
registry/review status
capabilities
licence
declared permissions
source repository
source-policy document
package format
package size
SHA-256
compatibility
last registry review date
linked review record
```

The point is not merely convenience. The directory makes the trust boundary visible before third-party code is installed and records evidence about how new installs reached the machine.

## Package types

```text
.mdxprovider   music providers (search, playback, recommendations, etc.)
.mdxplugin     identity/metadata/artwork/lyrics extensions
```

Both are installed through their existing isolated provider/extension runtimes.

## End-user install and setup flow

For a normal user the complete flow stays inside the directory:

```text
Sources
→ Explore plugins…
→ select a plugin
→ review permissions/source/review information
→ Install
→ configure required fields when prompted
→ Ready
```

If an installed plugin declares required configuration that is still missing, the directory marks it **SETUP NEEDED** rather than merely **INSTALLED**. Select it and use **Configure…** to finish setup later.

Plugins with no required setup install normally without an extra prompt. Existing configuration is preserved across reinstall/update unless the plugin's declared configuration changes.

The same shared configuration dialog is used from the Sources page and from the Plugin Directory. Secret values are never displayed back to the user; a stored secret is represented only as configured/not configured.

## Health and connection testing

Installed plugins can be checked from the GUI with **Test plugin**.

Melodex reports a small shared status vocabulary:

```text
READY
DEGRADED
NOT TESTED
SETUP NEEDED
AUTH REQUIRED
UNAVAILABLE
ERROR
DISABLED
```

The meaning of a test depends on the plugin type:

- **MPP providers:** Melodex calls the provider's standard `provider.health` method with the plugin's brokered configuration. The provider decides what its health method verifies, so a READY response is described as a **provider check**, not automatically as proof that every upstream operation works.
- **Capability extensions with `extension.health`:** Melodex calls the declared bounded health RPC. A result is described as an **upstream check** only when the extension returns `upstream_checked=true`.
- **Older capability extensions:** if no health contract is declared, Melodex verifies process startup and labels the result as a **process check**. Actual runtime successes/failures continue to update extension health when the extension is used.

Health checks are bounded so a broken provider cannot leave the GUI waiting indefinitely. Configuration changes, reinstalls and enable/disable actions invalidate cached results.

Health messages are redacted for common secret/token patterns before display or caching.

## Review records

Each canonical registry entry links to an append-only review record. In the desktop directory, select an entry and use **View review** to open it.

The latest review event is tied to the registry's current plugin version and package SHA-256. This makes status changes inspectable, but it does not turn a review into publisher signing or a legal/content endorsement.

`community` entries have a `community-intake` event; only entries whose current event/status is `reviewed` should be described as reviewed.

## Package verification

Installable registry entries must publish:

```text
HTTPS package URL
SHA-256 digest
package size
```

Melodex downloads to a temporary file, enforces a 25 MB registry package limit, verifies the exact byte count and SHA-256, then checks that the package-declared plugin ID/version match the registry entry before the install is recorded as **registry-verified**.

A changed or corrupted package is rejected.

SHA-256 proves that the downloaded bytes match the bytes named by the registry. It is **not** the same as publisher identity/signing. Cryptographic publisher signatures remain future work.

## Installation provenance

For new installs Melodex records:

```text
plugin ID
kind
version
install time
manual vs registry method
package name
package byte size
local package SHA-256
registry SHA-256 (when applicable)
registry verification result
publisher/source metadata (when applicable)
```

A registry install is shown as **registry-verified** only after package byte size/SHA-256 and package-declared ID/version match the registry entry.

A manual install records its local hash but is **not** called registry-verified.

Existing plugins installed before provenance tracking may show their origin as unknown.

## Update awareness

When a registry entry has a higher version than the installed plugin, the directory marks it as **UPDATE** and offers an explicit user-initiated update. If setup is also incomplete, the directory can show **UPDATE · SETUP NEEDED** so those two states are not confused.

Melodex does not silently auto-update third-party code.

## Cache and outages

The registry is cached locally for six hours.

If a refresh fails and a previous valid registry exists, Melodex can show the cached directory with a stale/offline warning.

The player does not depend on the registry to play music or use already installed plugins.

## Compatibility

Registry entries may declare:

```json
{
  "compatibility": {
    "melodex_min": "0.1.0",
    "mpp": "1.0",
    "contracts": {
      "artwork": "0.1"
    }
  }
}
```

Incompatible entries remain discoverable but cannot be installed from the directory.

## Status labels

Current registry status vocabulary:

| Status | Meaning |
| --- | --- |
| `example` | Maintained as a Melodex/reference learning example |
| `community` | Community-published; not represented as a reviewed registry entry |
| `reviewed` | Passed the project's current technical/source-policy review |
| `deprecated` | Still indexed for continuity but no longer recommended for new installs |
| `blocked` | Hidden/refused because it should not be installed |

A `reviewed` label is not a warranty for the upstream service or every media item returned by it.

## Default registry

The default directory reads:

```text
provider-sdk/registry/registry.json
```

from the public Melodex GitHub repository.

Developers/testers may override the registry URL with:

```bash
MELODEX_REGISTRY_URL=https://example.org/my-registry.json melodex
```

Registry package URLs must still use HTTPS and valid SHA-256 metadata.

## Reference packages

The first directory contains installable examples for:

- Radio Browser — playback provider;
- LibriVox — public-domain audiobook provider;
- MusicBrainz — identity/metadata enrichment;
- Wikimedia Commons — artwork enrichment.

These examples exist to teach the extension model using documented legal/open-access sources.

## For plugin authors

See:

- [Publish a community plugin](tutorials/ADD_PLUGIN_TO_REGISTRY.md)
- [Registry governance](developers/17_REGISTRY_GOVERNANCE.md)
- [Source and rights policy](developers/11_SOURCE_AND_RIGHTS_POLICY.md)
