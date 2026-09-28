# Responsible use and source policy

Melodex is a general-purpose music player, sequencing engine, and provider framework. It is designed to work with music that a user is authorized to access.

## What the public project ships

The public Melodex repository includes source-neutral Core plus documented legal/open reference integrations, currently including:

- local-file playback for media you control or are permitted to use;
- user-defined streams;
- Jamendo reference integration using its documented API and a user-supplied client ID;
- Radio Browser reference provider;
- LibriVox public-domain audiobook reference provider;
- MusicBrainz identity/metadata enrichment;
- Wikimedia Commons artwork enrichment;
- an optional Internet Archive reference provider for public/unrestricted material;
- the source-neutral Melodex Provider Protocol (MPP), capability-extension contracts and Provider SDK;
- Provider Bridge support for authorized local/LAN access;
- optional LLM integrations for playlist and player control.

The presence of a reference integration is not a blanket claim that every item exposed by the upstream service has the same rights. Per-item rights/licence metadata and upstream terms still matter.

## What the public project does not ship

The public repository does not include:

- credentials, private API keys, bearer tokens, cookies, or account secrets;
- source-specific access-control or DRM circumvention code;
- provider code intended to obtain media without authorization;
- undocumented private endpoints copied from third-party services;
- copyrighted music files or sample libraries that are not redistributable.

## Third-party providers

Third-party providers are separate software. Their inclusion in, compatibility with, or mention alongside the Melodex protocol does not mean Melodex endorses a provider or guarantees that its use is permitted.

Provider authors and users are responsible for checking the relevant service terms, licences, permissions, and applicable law. Providers should use documented APIs or other access methods for which they have permission.

Melodex maintainers may decline links, packages, instructions, issues, or pull requests that add source-specific bypass logic, expose credentials, redistribute copyrighted media without permission, or are primarily intended to facilitate unauthorized access.

## Security

Desktop `.mdxprovider` and `.mdxplugin` packages can contain executable third-party code. Review the publisher, declared permissions and source code where available before installation.

Registry SHA-256 verification proves package-byte integrity relative to registry metadata; it is not publisher signing or a sandbox.

See `SECURITY.md` and the Provider SDK trust model for more detail.

## LLM privacy

LLM support is optional. Melodex should not send provider credentials to an LLM. Users should review their chosen LLM provider's privacy policy before enabling remote model access.

## Reporting concerns

For security-sensitive concerns, follow `SECURITY.md`. For source-policy questions, open an issue without posting credentials, access tokens, copyrighted media, or instructions for bypassing access controls.
