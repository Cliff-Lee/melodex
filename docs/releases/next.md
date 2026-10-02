# Next release — draft notes

**Development after Melodex v0.7.4.**

This file tracks changes intended for the next release after **v0.7.4**.

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

## Campaign J — Spatial Browsing UX

- Album Wall now opens near a readable sleeve-browsing scale instead of shrinking the whole collection to fit.
- Album Wall supports canvas-style mouse dragging and two-finger trackpad panning.
- Smooth bounded zoom uses the mouse wheel, or Cmd/Ctrl + trackpad scroll when ordinary trackpad gestures should remain panning.
- **Actual size** restores the normal browsing scale; **Overview** is now an explicit orientation action rather than the default.
- Double-click remains the direct album-play gesture.
- Album Wall maintenance actions move behind **Wall options…**, keeping the artwork canvas dominant.
- Music Map now defaults to **Selected relationships**, showing no connection web until a track is selected.
- Selecting a mapped track reveals only its immediate sonic relationships; **All sonic links** remains available explicitly.
- Music Map nodes are larger and the default fitted view is slightly closer for legibility.
- The map keeps the majority of the page: maintenance actions move behind **Map options…**, route planning behind **Plan a route…**, and Journey Designer controls behind **Journey options…**.
- Global **Power tools** no longer forces Album Wall or Music Map control panels open.
- Spatial pages share a consistent pan/zoom mental model and preserve double-click-to-play behavior.



## Large-library reliability — incremental rescanning

- Previously indexed local/NAS libraries now reuse cached raw tags when file size and modification time are unchanged.
- Rescan reopens only new or changed audio files instead of re-reading every track with Mutagen.
- SQLite persistence is incremental too: unchanged track rows are left untouched.
- New, updated, removed and unchanged counts are shown after a scan.
- Offline or partially enumerated NAS roots keep their previous cached snapshot instead of being mistaken for an empty library.
- Older indexes without fingerprints are refreshed once and then become incremental.


## Large-library reliability — disposable scan process

- GUI library scans now run outside the main Melodex process.
- If an SMB/NAS filesystem call wedges, Cancel first asks the scanner to stop and then terminates the disposable worker if necessary.
- The existing live catalog remains available after cancellation or forced termination.
- Changing music roots during a scan stops the stale worker and restarts against the current root set.
- Frozen desktop build checks now verify the built-in scan-worker mode.


## Large-library reliability — progressive My Music rendering

- My Music keeps the full library model but initially renders only 120 albums, 120 artists or 300 track rows.
- Albums, Artists and Tracks expand progressively instead of constructing thousands of Qt widgets at once.
- Search still covers the complete collection and resets to a small render window.
- Off-screen cards outside the current filtered window are released rather than accumulating in memory.
- Artwork and artist-image cache work follows the rendered window instead of the whole collection.


## Desktop packaging — bundle size measurement

- macOS builds now record the installed app size and compressed DMG size separately.
- CI publishes a breakdown of the largest bundle areas, files and file types.
- This establishes a reproducible baseline before removing unnecessary Qt/PySide payload in the next packaging campaign.


## Desktop packaging — minimal Qt bundle

- macOS and Windows builds no longer collect every PySide6 module.
- Frozen builds now keep only the Qt families Melodex imports plus required runtime dependencies.
- A bundle guard prevents heavyweight unused Qt payload such as WebEngine, QML/Quick3D, Designer, PDF and Charts from silently returning.
- The 8A bundle report remains in place so installed-app size can be compared directly against the 669.4 MB macOS baseline.
