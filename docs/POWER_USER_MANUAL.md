# Melodex Power User Manual
## Version 0.2

This manual covers providers, resolver behaviour, playlist portability, Playback Gateway, Provider Bridge, MCP control, security boundaries and release architecture.

[Download the designed PDF edition](manuals/Melodex_Power_User_Manual_v0.2.pdf).

## 1. Architecture

```text
playlist / search / AI request
            |
     Universal Resolver
            |
      Provider Protocol
            |
      playable resource
            |
  Melodex Playback Gateway
            |
        QMediaPlayer
```

Core owns playback, queueing, Flow, taste memory and AI control. Providers supply catalogue metadata and authorised playback access.

## 2. Providers

Built-ins are This computer and User Streams. Jamendo is the reference provider. Internet Archive is an official optional provider. Third-party providers are installable `.mdxprovider` bundles.

## 3. Trust and permissions

Provider manifests declare capabilities and network hosts. Provider code still runs with normal OS-user permissions unless separately sandboxed.

## 4. Playback resources

Provider SDK v0.2 can represent URL, headers, cookies, expiry, refresh token, timeout, allowed playback hosts and a gateway-required flag.

These are internal playback state, not ordinary track metadata.

## 5. Playback Gateway

The loopback gateway supports authorised stateful/temporary media requests while validating provider-declared hosts.

On macOS the FFmpeg + gateway path also avoids a remote playback case that could otherwise fail or appear to play silently.

## 6. Resolver

Resolver scoring emphasizes title, artist and album similarity, duration agreement where available, and penalties for mismatched live/remix/cover/acoustic variants.

Provider priority is only a small tie-break.

## 7. Match memory

Use **Play this match**, **Prefer**, **Wrong match**, and **Reset memory** for song-specific resolver corrections.

## 8. Playlist portability

XSPF/M3U/M3U8 entries may contain a path, URL, provider identity or only metadata. Metadata-only entries can resolve against the listener's own connected sources.

## 9. Provider SDK v0.2

```bash
cd provider-sdk
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

melodex-provider init my-provider
melodex-provider validate my-provider
melodex-provider doctor my-provider
melodex-provider pack my-provider
```

## 10. Frozen builds and Python providers

v0.2 includes a hidden provider-runner mode so Python `.mdxprovider` entrypoints run correctly inside PyInstaller builds without opening another GUI instance.

## 11. MCP and OpenWebUI

Melodex has a private authenticated desktop control bridge plus an optional MCP server.

```bash
python -m melodex.mcp_server --transport streamable-http --host 0.0.0.0 --port 8787
```

Use bearer authentication.

## 12. Provider Bridge

Android uses an authenticated Provider Bridge instead of executing downloaded provider code.

## 13. Security boundary

Sensitive playback fields are stripped from control/LLM status, including headers, cookies, refresh/access tokens, signed stream URLs and local paths.

## 14. Release architecture

v0.2 targets macOS ARM/Intel DMGs, Windows installer/portable ZIP, Linux AppImage, Android APK/AAB and source ZIP.

## 15. Release gate

Release checker, desktop tests, Provider SDK tests, packaged-provider playback, redaction tests, native CI builds and documentation must all be green/current before tagging.
