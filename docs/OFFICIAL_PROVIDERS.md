# Official providers

Melodex keeps the desktop core source-neutral. Optional official providers are reference integrations built on the same public MPP interface available to third-party developers.

## Internet Archive

Source: `official-providers/internet-archive/`

The Internet Archive provider searches publicly accessible audio items, reads public item metadata, selects a playable representation, preserves source/licence metadata, and resolves playback through the Melodex Playback Gateway.

It does not require credentials for public content and does not bypass lending, login, DRM or restricted-item access controls.

### Install

If the release contains a packaged Internet Archive `.mdxprovider`:

1. Open **Sources**.
2. Enable **Show power tools**.
3. Choose **Install `.mdxprovider`...**.
4. Select the Internet Archive provider.
5. Search **Internet Archive** from Discover.

Developers can build the provider from `official-providers/internet-archive/`; see its README.

### Playback timing

Archive search is item-level and normally returns quickly. Starting playback can take several seconds while an item is resolved to a playable file. Very large aggregate recordings can take longer than ordinary tracks.

### Rights

Internet Archive content has item-specific rights/licence information. The provider does not claim that every Archive item is public domain.
