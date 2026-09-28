# Melodex 0.1.0 Public Preview

> **Historical release note.** This page describes the 0.1.0-era preview and is not a current feature/status reference. See [Release status](docs/RELEASE_STATUS.md) and [Status, stability and trust](docs/developers/00_STATUS_AND_STABILITY.md).

This is the first clean, source-neutral public foundation.

## Included

- macOS/Windows desktop source
- Android Bridge-client source
- GitHub Actions native build workflows
- Local Files provider
- Jamendo legal/reference online provider requiring the user's own client ID
- installable MPP v1 desktop providers
- Provider Bridge with authenticated local-media streaming and byte-range support
- Flow local DSP engine
- Play for Me / taste memory
- Moments and playlists
- optional OpenWebUI/Ollama/OpenAI-compatible control
- complete Provider SDK
- user and developer documentation

## Build outputs after tagging on GitHub

- macOS ARM64 DMG
- macOS Intel DMG (while the `macos-13` GitHub runner remains available)
- Windows portable ZIP
- Windows Inno Setup EXE
- Android directly installable debug APK for preview/testing
- Android unsigned release AAB for subsequent store signing
- source ZIP

## Important release note

Production app-store distribution still requires your own platform signing identities/keys. The repository intentionally contains no private signing material.
