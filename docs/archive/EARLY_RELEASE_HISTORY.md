# Early Melodex release history

This page preserves two historical files that were originally kept in the repository root. They are retained for provenance, not as current instructions.

## Original GitHub publication notes

The repository is already public. Current release instructions live in:

- [Release process](../RELEASING.md)
- [Releases, main, and version numbers](../RELEASES_AND_MAIN.md)

The original first-release workflow targeted v0.1.0 and should not be used as a template for current releases.

## Melodex 0.1.0 public preview

The first public preview established the source-neutral foundation:

- macOS and Windows desktop source;
- Android Bridge-client source;
- native GitHub Actions build workflows;
- Local Files and a legal/reference online provider;
- installable desktop providers;
- Provider Bridge with authenticated local-media streaming;
- Flow, Play for Me, taste memory, Moments and playlists;
- optional OpenWebUI/Ollama/OpenAI-compatible control;
- Provider SDK and initial user/developer documentation.

The original build plan produced macOS ARM64/Intel packages, Windows portable/installer packages, Android preview packages and a source archive.

Production store distribution still requires platform signing identities/keys; the public repository intentionally contains no private signing material.
