# Responsible Use and Source Policy

Melodex is a general-purpose music player, sequencing engine, provider framework and automation surface. It is designed to work with media and services that the user is authorized to access.

## What the public repository contains

The current public repository contains, among other things:

- local-file playback;
- built-in User Streams for URLs/playlists the user explicitly adds;
- a Jamendo reference provider using Jamendo's documented API and a user-supplied client ID;
- source code for a first-party/reference Internet Archive provider;
- the source-neutral Melodex Provider Protocol (MPP) and Provider SDK;
- the experimental capability-extension framework;
- a public plugin registry/directory;
- legal/open reference examples using Radio Browser, LibriVox, MusicBrainz and Wikimedia Commons;
- Provider Bridge / REST / MCP / OpenAI-function integration surfaces;
- optional LLM integrations.

Not every source/example is installed or enabled by default, and the latest packaged release can lag behind the current `main` branch.

See [Release status](docs/RELEASE_STATUS.md).

## What the public project does not intentionally provide

The public repository is not intended to contain:

- private credentials, API keys, bearer tokens, cookies or account secrets;
- DRM/access-control circumvention;
- CAPTCHA/anti-bot bypass tooling;
- provider code whose purpose is to obtain media without authorization;
- undocumented private endpoints copied for the purpose of bypassing a service's intended access model;
- copyrighted music/sample files that the project lacks permission to redistribute.

## Third-party providers and extensions

Third-party extensions are separate software.

Compatibility with MPP/capability contracts—or presence in a community registry—does not mean Melodex guarantees that:

- the upstream service permits every possible use;
- every media item has identical rights;
- the package is harmless;
- the project endorses the publisher.

Provider authors and users remain responsible for checking current terms, licences, permissions and applicable law.

## Reference/open sources

Reference integrations should document their upstream access/rights assumptions in `SOURCE_POLICY.md`.

Where rights vary per item (for example Wikimedia Commons files or Creative Commons music), provenance/licence metadata should be preserved rather than replaced with a blanket claim.

LibriVox's own public-domain statement is U.S.-specific and explicitly advises users elsewhere to check local copyright status.

## Download/offline is a separate capability

Permission to stream/play something does not automatically imply permission to download or retain it offline.

Providers should expose offline/download behavior only when the upstream source and relevant media rights permit it.

## Registry policy

The registry is a discoverability/trust-metadata layer, not an endorsement marketplace.

Registry review labels are defined in [Registry governance](docs/developers/17_REGISTRY_GOVERNANCE.md).

Project maintainers may decline or block registry entries, code, links or instructions that expose secrets, circumvent controls, redistribute unauthorized media, or cannot explain an appropriate source/access basis.

## Security and privacy

Third-party desktop plugins execute code outside the GUI process but are not currently in a complete OS sandbox.

Review [SECURITY.md](SECURITY.md), [Privacy](docs/PRIVACY.md), and [Status, stability and trust](docs/developers/00_STATUS_AND_STABILITY.md).

## LLM use

LLM support is optional.

Melodex should not place provider credentials, playback cookies, Bridge/MCP tokens or unrelated private data in model context.

Users should review the privacy/retention policy of any remote model service they configure.

## Reporting concerns

For security-sensitive concerns, follow [SECURITY.md](SECURITY.md).

For source-policy questions, use an issue or pull request without posting credentials, access tokens, copyrighted media, or instructions for bypassing access controls.
