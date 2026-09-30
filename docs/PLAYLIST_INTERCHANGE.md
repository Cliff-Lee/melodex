# Playlist interchange

Melodex can import and export **XSPF**, **M3U**, and **M3U8** playlists.

## Paste a playlist from an AI chat

From **Playlists → Paste from AI…**, paste a playlist copied from ChatGPT or another AI and choose **Analyse Playlist**. No AI account or connection is needed. Melodex accepts its JSON playlist format, common JSON track lists, Markdown lists or tables, TXT, CSV/TSV, and pasted M3U text. **Copy ChatGPT Prompt** copies a prompt with the recommended JSON shape; **Import File…** can load a playlist or text file instead.

Melodex sends no playlist text to an AI service. It resolves artist/title metadata using the user's connected music sources, which may receive search queries as part of matching. Matched tracks are saved as a local playlist and placed in the queue; unmatched entries are kept with the playlist for later matching.

## Import

Imported entries may contain:

- a local file path;
- an HTTP/HTTPS media URL; or
- only artist/title/album metadata.

Local files and direct URLs are preserved as playable entries. Metadata-only entries are passed to the Universal Resolver, so an XSPF/M3U playlist does not have to name the same provider that will ultimately play a track.

## Export

Melodex writes standard XSPF or extended M3U. Normal players can use the ordinary locations in the file. Melodex also writes ignorable metadata (`meta` elements in XSPF and `#MELODEX:` comments in M3U) so provider IDs and richer metadata survive a round trip.

When a track has metadata but no fixed media location, M3U/M3U8 uses a `melodex://resolve?...` locator. Other players may ignore that entry; Melodex will resolve it against the listener's connected sources when re-imported.

## Design goal

A playlist describes **what should be played**, while the resolver decides **where it should be played from**. This keeps playlists portable across local libraries and provider combinations.
