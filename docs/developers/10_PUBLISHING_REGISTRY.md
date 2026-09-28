# Publishing and the Plugin Registry

## Distribution should stay decentralized

Plugin authors should be able to host source code and releases in their own repositories.

Melodex's registry should be an **index**, not the only hosting platform.

A registry entry can point to:

```text
source repository
release/package URL
homepage
documentation
issue tracker
```

## Suggested registry statuses

```text
example
community
reviewed
deprecated
blocked
```

`reviewed` should mean the extension passed Melodex technical/source-policy checks. It does not mean Melodex guarantees the upstream service or every item it contains.

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

A future Melodex UI can group extensions by capability:

```text
Playback
  Radio Browser

Metadata
  MusicBrainz

Artwork
  Wikimedia Commons

AI / automation
  ...
```

See [Publish a community plugin](../tutorials/ADD_PLUGIN_TO_REGISTRY.md).
