# Playlist interchange

Melodex can import and export **XSPF**, **M3U**, and **M3U8** playlists.

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
