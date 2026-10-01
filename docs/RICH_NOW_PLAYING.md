# Melodex Rich Now Playing

Rich Now Playing separates **audio playback** from **music knowledge**. A track can be played from any Melodex provider while its identity, artwork, credits, local lyrics and plugin-supplied context are enriched independently.

## Metadata stack

1. **Local tags/files** — title/artist/album, embedded artwork, embedded lyrics.
2. **Playback provider** — provider artwork when supplied.
3. **MusicBrainz** — recording/artist/release identity, artist relationships, tags/genres and structured credits.
4. **Cover Art Archive** — cached release or release-group artwork.
5. **Context extensions** — optional sourced cards such as liner notes, song relationships and aggregate listening context.

Melodex uses a meaningful User-Agent, caches MusicBrainz responses, and serializes uncached requests so it does not exceed the public API's one-request-per-second guidance.

## Lyrics

The public app does not scrape commercial lyric sites. Lyrics are local-first and extensible:

- lyrics explicitly imported or pasted into Melodex;
- synchronized `.lrc` and plain `.txt` sidecars, including common title / artist-title naming and a `Lyrics/` subfolder;
- common embedded lyric tags (including ID3 USLT/SYLT where available);
- installed extensions implementing the `lyrics.lookup` capability contract.

The Lyrics tab exposes **Add lyrics file…**, **Paste lyrics…** and **Find lyrics plugin…**. Imported/pasted lyrics are copied into Melodex's metadata cache and survive restarts without rewriting the source audio file.

The current registry includes a small public-domain lyrics reference plugin for contract testing, not a general modern-song lyrics service. Licensed services can implement the same lyrics contract without coupling copyrighted lyric acquisition to Core.

## Visual Now Playing

The **Now playing** page provides:

- large cached album artwork;
- artwork-derived accent/background colour;
- title, artist, release year, location and genre/tag context;
- synchronized lyric highlighting as playback advances;
- a single artist portrait in the hero with compact attribution underneath;
- a compact **Artist** summary with selected membership, related-project and link information;
- a compact **Releases** summary showing up to six release groups with direct MusicBrainz links;
- grouped recording/work **Credits** rather than a long raw relationship list;
- a **Context** tab populated by `context.lookup` extensions;
- MusicBrainz identity links and metadata-match confidence.

All enrichment is asynchronous; playback is not blocked by network metadata lookups.
