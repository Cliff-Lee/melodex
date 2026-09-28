# Tutorial — Publish a Community Plugin

Melodex uses a decentralized publishing model:

```text
your repository
    ↓
source + docs + tests
    ↓
.mdxprovider / .mdxplugin release
    ↓
Melodex registry entry
    ↓
Sources → Explore plugins…
```

The registry indexes your package. It does not need to host your source code.

## 1. Prepare the project

A public extension should normally include:

```text
README.md
LICENSE
SOURCE_POLICY.md
tests / fixtures
manifest.json       # .mdxprovider
or
capabilities.json   # .mdxplugin
```

## 2. Use a stable ID

Prefer reverse-domain style:

```text
org.example.my-provider
com.example.artwork
```

Changing the ID later makes the extension look like a different plugin.

## 3. Build and test

MPP provider:

```bash
melodex-provider validate .
melodex-provider doctor .
melodex-provider pack .
```

Capability extension:

```bash
melodex-extension validate .
melodex-extension doctor .
melodex-extension pack .
```

Also run your fixture/unit tests.

## 4. Document source policy

Answer:

- Which upstream API/source is used?
- Is the access method documented by the upstream service, or otherwise explicitly permitted?
- What authentication is required?
- What rate limits apply?
- What may be cached?
- Is offline/download access allowed?
- Are there commercial restrictions?
- What attribution is required?
- Are rights different per media item?

A public endpoint is not automatically permission to redistribute its content.

## 5. Publish the package

Normally publish the generated `.mdxprovider` or `.mdxplugin` in your own GitHub release or other HTTPS release infrastructure.

Do not silently replace package bytes behind an existing version.

## 6. Calculate integrity metadata

macOS/Linux:

```bash
shasum -a 256 my-plugin-1.0.0.mdxplugin
wc -c my-plugin-1.0.0.mdxplugin
```

Python alternative:

```bash
python - <<'PY'
from pathlib import Path
import hashlib

p = Path("my-plugin-1.0.0.mdxplugin")
print("sha256:", hashlib.sha256(p.read_bytes()).hexdigest())
print("size:", p.stat().st_size)
PY
```

The registry records both values.

## 7. Add the registry entry

Example:

```json
{
  "id": "org.example.artwork",
  "name": "Example Artwork",
  "publisher": "Example Developer",
  "version": "1.0.0",
  "kind": "enrichment",
  "status": "community",
  "description": "Artist artwork from Example API.",
  "capabilities": ["artwork"],
  "license": "MIT",
  "source": {
    "repository": "https://github.com/example/example-artwork",
    "homepage": "https://example.org/",
    "documentation": "https://github.com/example/example-artwork#readme"
  },
  "distribution": {
    "package_url": "https://github.com/example/example-artwork/releases/download/v1.0.0/example-artwork-1.0.0.mdxplugin",
    "format": "mdxplugin",
    "sha256": "64-hex-character-sha256",
    "size_bytes": 12345
  },
  "compatibility": {
    "melodex_min": "0.1.0",
    "mpp": null,
    "contracts": {
      "artwork": "0.1"
    }
  },
  "permissions": [
    "network:api.example.org"
  ],
  "source_policy": "https://github.com/example/example-artwork/blob/main/SOURCE_POLICY.md"
}
```

For a playback/catalog provider use:

```json
{
  "kind": "provider",
  "distribution": {
    "format": "mdxprovider"
  },
  "compatibility": {
    "mpp": "1.0"
  }
}
```

## 8. Validate the registry

From the Melodex Provider SDK:

```bash
melodex-registry validate registry/registry.json
melodex-registry summary registry/registry.json
```

If package files are stored in the Melodex repository:

```bash
melodex-registry verify-packages \
  registry/registry.json \
  --packages registry/packages
```

Community packages hosted elsewhere become **registry-verified installs** only when the downloaded byte size/SHA-256 and package-declared ID/version match the registry entry.

## 9. Open a registry PR

A registry PR should explain:

- what the extension adds;
- why the upstream source is appropriate;
- declared capabilities;
- declared permissions;
- test coverage;
- source/rights policy;
- package URL;
- SHA-256 and byte size.

Initial third-party entries normally use:

```text
status: community
```

A later project review may move an entry to `reviewed`.

## 10. What users see

In:

```text
Sources → Explore plugins…
```

users see the source, publisher, licence, capabilities, permissions, status, package hash and compatibility before installation.

Melodex downloads the package over HTTPS and refuses installation if the bytes do not match the registry SHA-256/size.

## Updating a release

For a new version:

1. publish a new package;
2. update the registry version;
3. update package URL if needed;
4. update SHA-256 and byte size;
5. update compatibility/permissions if changed;
6. validate;
7. open a registry PR.

See [Registry governance](../developers/17_REGISTRY_GOVERNANCE.md).
