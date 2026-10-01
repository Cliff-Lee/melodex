# Melodex Rich Now Playing

Rich Now Playing separates **audio playback** from **music knowledge**. A track can be played from any Melodex provider while its identity, artwork, lyrics, artist information, credits and context are enriched independently.

## Metadata stack

1. **Local tags/files** — title/artist/album, embedded artwork, embedded lyrics.
2. **Melodex private cache** — remembered artwork associations, imported/personal lyrics and cached online lyric results.
3. **Playback provider** — provider artwork when supplied.
4. **MusicBrainz** — recording/artist/release identity, artist relationships, tags/genres and structured credits.
5. **Cover Art Archive** — release or release-group artwork.
6. **Optional capability extensions** — additional lyrics, context, metadata or artwork.

Melodex uses a meaningful User-Agent, caches MusicBrainz responses, and serializes uncached requests so it does not exceed the public API's one-request-per-second guidance.

## Lyrics

Lyrics are a native Melodex feature. Extensions may supply lyric results, but they do not own a separate lyrics page.

The native toolbar is:

**Source · Refresh lyrics · Full screen · Translate · More**

Melodex checks saved/personal lyrics, sidecars and embedded tags, installed `lyrics.lookup` sources, then the explicit LRCLIB online fallback when needed.

Synchronized lyrics highlight with playback and can be selected to seek. The renderer uses explicit high-contrast colours so clickable synchronized lines remain readable in the dark theme.

Online LRCLIB results may be cached privately in Melodex's metadata cache so returning to a track does not repeatedly contact the service. Cached provider lyrics remain read-only and are not written into the audio file. **Refresh lyrics / Try again** can still make a fresh request.

**More** contains the secondary actions: edit a personal copy, add/paste lyrics, control Auto-find online, and manage optional lyric sources.

## Artwork and revisits

Downloaded artwork is remembered against stable album/artist aliases. When a track is revisited, Now Playing displays a known cached cover immediately before background enrichment begins. Album associations include year-independent aliases so raw tags and later MusicBrainz enrichment do not make a previously found cover disappear.

## Artist, Releases and Credits

These tabs are compact native summaries rather than nested browser/textbox panels:

- **Artist** shows identity, origin, tags, selected members/projects and useful links. The artist portrait is shown once in the Now Playing hero rather than duplicated in the tab.
- **Releases** shows a concise selection of release groups with MusicBrainz links for the full discography.
- **Credits** groups names by role instead of exposing a long relationship dump.

Artist-photo attribution is kept directly under the hero portrait in a short form such as **Photo · Commons · licence**; fuller attribution remains available in the tooltip/source data.

## Context

Context is also a native Melodex surface. Core track, artist and recording information is shown whenever Melodex already knows it, even if every optional context extension is offline.

Optional `context.lookup` extensions can add liner notes, MusicBrainz relationships, community listening signals and other sourced cards. Use **Sources…** to manage them.

Packaged provider/plugin child processes receive Melodex's trusted certifi CA bundle when the operating-system environment does not supply one. This keeps stdlib `urllib` HTTPS extensions working consistently in frozen desktop builds.

The Plugin Centre distinguishes transient network/TLS failures as **Unavailable**; actual extension process or protocol failures remain **Error**.

## Visual Now Playing

The **Now Playing** page provides:

- cached album artwork;
- artwork-derived accent/background colour;
- title, artist, release year, location and genre/tag context;
- synchronized lyric highlighting;
- compact artist, release and credit summaries;
- native core context plus optional sourced context cards;
- MusicBrainz identity links and metadata-match confidence.

Enrichment remains asynchronous. Playback is never blocked waiting for network metadata.
