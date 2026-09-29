# Music sources

Melodex is source-neutral. A source is any provider that can search/browse music and resolve a selected track to a playable local file or stream.

## Built into the desktop app

### This computer

Your own local audio files. No network access required.

### Jamendo reference provider

A real online example using the public Jamendo API. You supply your own developer client ID. Melodex keeps Jamendo attribution and licence metadata with each result.

Jamendo's API has its own terms and licence requirements; review them before publishing an application that uses it.

## Plugin Directory on desktop

Use **Sources → Explore plugins…** to browse the registry.

The directory shows publisher, status, licence, capabilities, permissions, compatibility, source repository and package verification data before installation.

Installable packages are downloaded over HTTPS and must match the registry SHA-256 and byte size.

Plugins that need required configuration open a setup form immediately after installation. If setup is cancelled or incomplete, Melodex keeps the plugin installed but labels it **SETUP NEEDED** until configuration is completed.

## Health status

Installed third-party providers and extensions show a health state in Sources. Use **Test selected** to refresh it.

Provider checks use `provider.health`. Extensions that declare `extension.health` get a bounded active check; older extensions fall back to process startup. Runtime success/failure is still learned from actual extension calls and overrides stale health when necessary. A failed or unavailable plugin does not prevent unrelated providers/extensions from continuing to work.

## Manual third-party installation

Power tools still allow direct installation of `.mdxprovider` and `.mdxplugin` files. Manual installs use the same required-configuration setup form as Plugin Directory installs.

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

“REGISTRY VERIFIED” is the UI badge for a **registry-verified** install: package size/SHA-256 and package-declared ID/version matched the registry entry. It does not mean publisher signing or a full OS sandbox.

See [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md).
