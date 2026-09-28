# Music sources

Melodex is source-neutral. A source is any provider that can search/browse music and resolve a selected track to a playable local file or stream.

## Built in

### This computer

Your own local audio files. No network access required.

### User Streams

User-defined radio/stream URLs stored in Melodex. Playback naturally uses the network endpoint you add.

### Jamendo reference provider

A real online example using the public Jamendo API. You supply your own developer client ID. Melodex keeps Jamendo attribution and licence metadata with each result.

Jamendo's API has its own terms and licence requirements; review them before publishing an application that uses it.

## Optional reference/community plugins

These are separate from built-in Core sources.

Use **Sources → Explore plugins…** to browse the registry on Melodex builds that include the Plugin Directory.

The directory shows publisher, status, licence, capabilities, permissions, compatibility, source repository and package verification data before installation.

Installable packages are downloaded over HTTPS and must match the registry SHA-256 and byte size. Registry installation also checks that the package-declared ID/version match the registry entry.

## Manual third-party installation

Power tools still allow direct installation of `.mdxprovider` and `.mdxplugin` files.

Before installing any third-party code, review its publisher, permissions and source code when available.

## Android

Android uses Provider Bridge rather than arbitrary downloaded provider code.


## Trust labels

For newly tracked third-party installs Melodex can distinguish:

```text
REGISTRY VERIFIED
MANUAL
origin unknown (older install)
```

“Registry verified” means package bytes matched registry SHA-256/size metadata. It does not mean publisher signing or full OS sandboxing.

See [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md).
