# Melodex Rich Now Playing

Rich Now Playing separates **audio playback** from **music knowledge**. A track can be played from any Melodex provider while its identity, artwork, credits and local lyrics are enriched independently.

## Metadata stack

1. **Local tags/files** — title/artist/album, embedded artwork, embedded lyrics.
2. **Playback provider** — provider artwork when supplied.
3. **MusicBrainz** — recording/artist/release identity, artist relationships, tags/genres and structured credits.
4. **Cover Art Archive** — cached release or release-group artwork.

Melodex uses a meaningful User-Agent, caches MusicBrainz responses, and serializes uncached requests so it does not exceed the public API's one-request-per-second guidance.

## Lyrics

The public app does not scrape commercial lyric sites. Built-in lyrics support is local-first:

- synchronized `.lrc` beside the audio file;
- plain `.txt` beside the audio file;
- common embedded lyric tags (including ID3 USLT/SYLT where available).

A future lyrics-provider interface can support licensed services without coupling copyrighted lyric acquisition to the core player.

## Visual Now Playing

The **Now playing** page provides:

- large cached album artwork;
- artwork-derived accent/background colour;
- title, artist, release year, location and genre/tag context;
- synchronized lyric highlighting as playback advances;
- artist/band membership and related-project relationships when MusicBrainz has them;
- structured recording/work credits;
- MusicBrainz identity links and metadata-match confidence.

All enrichment is asynchronous; playback is not blocked by network metadata lookups.
