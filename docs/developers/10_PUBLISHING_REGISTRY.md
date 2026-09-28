# Publishing and the Plugin Registry

## Distribution stays decentralized

Plugin authors can host source and releases in their own repositories.

Melodex's registry is an **index**, not the only hosting platform.

A registry entry can point to:

```text
source repository
release/package URL
homepage
documentation
issue tracker
```

## Package formats

```text
.mdxprovider   catalog/playback providers
.mdxplugin     capability extensions
```

Build them with:

```bash
melodex-provider pack .
melodex-extension pack .
```

## Suggested registry statuses

```text
example
community
reviewed
deprecated
blocked
```

`reviewed` means the extension passed Melodex technical/source-policy checks. It does not mean Melodex guarantees the upstream service or every item it contains.

## Useful registry metadata

```text
id
name
publisher
version
kind
capabilities
permissions
license
source repository
package URL
compatibility
source policy
review status
```

## Discovery UI

Melodex can increasingly group extensions by capability:

```text
Playback
  Radio Browser

Identity / metadata
  MusicBrainz

Artwork
  Wikimedia Commons

Lyrics
  ...

AI / automation
  ...
```

The desktop Sources page now includes **Explore plugins…**, backed by the canonical registry. Installable entries are downloaded over HTTPS and verified against registry SHA-256/size metadata before the existing provider/extension installer sees them.

See [Publish a community plugin](../tutorials/ADD_PLUGIN_TO_REGISTRY.md).


## Registry tooling

```bash
melodex-registry validate registry/registry.json
melodex-registry summary registry/registry.json
melodex-registry verify-packages registry/registry.json --packages registry/packages
```

See [Registry governance](17_REGISTRY_GOVERNANCE.md).
