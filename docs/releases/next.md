# Next release — draft notes

**Development after Melodex v0.7.1.**

This file tracks changes intended for **v0.7.2**.

## Campaign I — Native Lyrics UX

- Lyrics is now a native Melodex listening surface rather than exposing plugin-management chrome in Now Playing.
- Installed `lyrics.lookup` extensions still participate automatically underneath the native UI.
- The old **Lyrics helpers / Add lyrics source…** strip is removed from the listener-facing Lyrics tab.
- The primary toolbar is reduced to **Source / Refresh lyrics / Full screen / Translate / More**.
- Edit, file import, paste, auto-find and lyric-source management move into **More**.
- **Refresh lyrics** rechecks saved, embedded and installed lyric sources before using LRCLIB as an online fallback.
- Installed lyric extensions are shown as ordinary source names rather than internal plugin IDs.
- Plain lyrics and synchronized lyrics now use explicit high-contrast dark-theme typography.
- Synced lyrics use larger current-line typography while keeping click-to-seek and full-screen behavior.
- The source selector remains native even when only one source is available.
- Plugin/source management remains available from **More** and Sources & plugins, but is no longer the way a listener “opens” or uses Lyrics.

