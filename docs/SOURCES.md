# Music sources

Melodex is source-neutral. A source can supply searchable/browsable music and resolve a selected item to playable audio.

## Built in

### This computer
Your own local audio files. No network access is required for local playback.

### User Streams
A built-in source for direct HTTP(S) audio, internet radio and user-supplied stream playlists.

It can import local `.m3u`, `.m3u8` and `.pls` files, taking only HTTP(S) stream entries.

See [User Streams](USER_STREAMS.md).

## Reference provider

### Jamendo
Jamendo is the reference online provider. You supply your own developer client ID.

See [Jamendo reference provider](JAMENDO_REFERENCE_PROVIDER.md).

## Official optional provider

### Internet Archive
The official Internet Archive `.mdxprovider` searches and plays publicly accessible Archive audio through the same MPP interface available to third-party developers.

Public items do not require Archive credentials. The provider does not bypass login, lending, DRM or restricted-item protections.

See [Official providers](OFFICIAL_PROVIDERS.md).

## Third-party providers on desktop

Use **Sources -> Show power tools -> Install `.mdxprovider`...**.

Providers run out-of-process over MPP JSON-RPC, but provider code still executes with your normal OS-user permissions unless you add OS-level sandboxing.

Install only providers you trust.

## Provider priority

Power tools can move sources up/down in resolver priority. Priority is a small tie-break; metadata similarity and match safety remain more important.

## Android

Android uses the authenticated Provider Bridge rather than executing arbitrary downloaded provider code.
