# Melodex Sources

## What appears on a fresh install

Melodex now presents sources by origin rather than as one technical list:

- **Your music & connections** — local files, your own stream URLs, and the optional built-in Jamendo connector.
- **Included with Melodex** — Internet Archive Audio, LibriVox, NicheDB Radio, Radio Browser, SomaFM, Wikimedia Commons Audio and ccMixter.
- **Installed music plugins** — providers you separately installed from the registry or a local package.
- **Installed enhancements** — artwork, lyrics, metadata, context or recommendation extensions.

The included providers are carried with the desktop app and installed automatically on first run unless you explicitly remove/disable one. Registry examples are optional and are not preinstalled. If an older Radio Browser Example or LibriVox Example is already installed, Melodex automatically ignores that reference copy while the audited bundled replacement is available, preventing duplicate Search entries.

Use **Check connections** for a bounded live health check on the current computer/network. A package passing repository tests does not by itself prove its upstream service is currently reachable.

See [Plugin and source audit](PLUGIN_AUDIT.md) for the complete matrix.

## Source architecture

Melodex is source-neutral. A source is any provider that can search/browse music and resolve a selected track to a playable local file or stream.

## Built into the desktop app

### This computer

Your own local audio files. No network access required.

### Jamendo reference provider

A real online example using the public Jamendo API. You supply your own developer client ID. Melodex keeps Jamendo attribution and licence metadata with each result.

Jamendo's API has its own terms and licence requirements; review them before publishing an application that uses it.

### Bundled desktop providers

On first launch, the desktop app installs these seven providers into the user's local Melodex data folder:

| Provider | What it offers | Source notes |
| --- | --- | --- |
| ccMixter 0.1.3 | Creative Commons music search and playback | Check each track's licence and attribution. |
| SomaFM 0.1.1 | Curated live internet radio | Streams come from SomaFM; station terms apply. |
| NicheDB Radio 0.1.2 | Daily-refreshed radio search with genre/country/language/codec/popularity metadata | Discovery uses NicheDB; playback connects directly to each station stream. |
| Radio Browser 0.1.2 | Community radio station search and playback | Availability and rights depend on each station. |
| Wikimedia Commons Audio 0.1.1 | Openly licensed and public-domain audio | Licence and attribution are specific to each file. |
| LibriVox 0.1.4 | Public-domain audiobooks and spoken-word audio | Searches the Internet Archive LibriVox collection; public-domain status can depend on jurisdiction. |
| Internet Archive Audio 0.1.1 | Publicly accessible audio search and playback | Search is lightweight; file metadata resolves only when a result is opened or played. Rights and access vary by item. |

These provider packages connect to their respective sources; the installer does not contain music or audiobook files. LibriVox 0.1.4 deliberately uses Internet Archive's LibriVox collection for search and hosted MP3 playback, avoiding interactive search load on the volunteer-hosted LibriVox API. In **Sources & plugins → Power tools**, choose **Remove selected provider** to remove one. Removed bundled sources stay removed across restarts. Choose **Restore bundled sources** to install them again. A newer manually installed provider is kept when it is newer than the bundled copy.

Old private development adapters are **not** part of the public bundled-provider set or public registry. If an earlier development build left one in the local Melodex data folder, current development builds quarantine it: it is not loaded, searched or played, and its old local files are left untouched.

## Plugin Centre on desktop

Use **Sources & plugins → Add features…** to browse the registry. The registry currently contains reference/example packages; none are installed automatically.

The Plugin Centre shows the user-facing purpose, capabilities, permissions and installation state first. Compatibility, package verification, source repository and review metadata remain available under **Technical details**.

Installable packages are downloaded over HTTPS and must match the registry SHA-256 and byte size.

Plugins that need required configuration open a setup form immediately after installation. If setup is cancelled or incomplete, Melodex keeps the plugin installed but labels it **SETUP NEEDED** until configuration is completed. NicheDB Radio needs no setup or API key for normal use.

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
BUNDLED
MANUAL
origin unknown (older install)
```

“REGISTRY VERIFIED” is the UI badge for a **registry-verified** install: package size/SHA-256 and package-declared ID/version matched the registry entry. It does not mean publisher signing or a full OS sandbox.

See [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md).
