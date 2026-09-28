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
```

The point is not merely convenience. The directory makes the trust boundary visible before third-party code is installed.

## Package types

```text
.mdxprovider   music-source/catalog/playback providers
.mdxplugin     identity/metadata/artwork/lyrics extensions
```

Both are installed through their existing isolated provider/extension runtimes.

## Package verification

Installable registry entries must publish:

```text
HTTPS package URL
SHA-256 digest
package size
```

Melodex downloads to a temporary file, enforces a 25 MB registry package limit, verifies the exact byte count and SHA-256, and only then passes the package to the appropriate installer.

A changed or corrupted package is rejected.

SHA-256 proves that the downloaded bytes match the bytes named by the registry. It is **not** the same as publisher identity/signing. Cryptographic publisher signatures remain future work.

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
| `community` | Community-published; not represented as Melodex-reviewed |
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
