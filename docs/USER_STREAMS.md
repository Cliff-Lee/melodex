# User Streams

**User Streams** is a built-in Melodex source for audio the user explicitly
chooses to add.

It supports:

- direct `http://` and `https://` audio/stream URLs;
- internet radio endpoints;
- local `.m3u` / `.m3u8` stream playlists;
- local `.pls` stream playlists.

## Add a stream

Open **Sources → User Streams… → Add URL**.

Enter a display name, the stream URL and an optional genre. Melodex stores the
configuration locally in its normal source settings.

## Import a playlist

Open **Sources → User Streams… → Import playlist** and choose a `.m3u`, `.m3u8`
or `.pls` file.

Only HTTP(S) entries are imported. Local music files continue to belong in
**This computer**.

## Edit or remove

Use **Sources → User Streams…** to edit or remove a configured entry.

## Notes

A direct `.m3u8` URL can also be added as a URL when it is the playable HLS
endpoint itself. Playlist import is intended for local playlist files.

User Streams does not bypass access controls, supply credentials, or discover
private stream endpoints. Add streams you are authorised to access.
