# My Music

**My Music** is Melodex's local collection browser. It is designed around recognition and musical identity rather than file-system detail.

Your audio files remain where they are. Melodex indexes the folders you choose and builds visual **Albums**, **Artists**, and **Tracks** views from the metadata and artwork it can find.

## Add your collection

Open **My Music** and choose **+ Add music**.

Melodex scans supported audio files in place. It reads tags such as title, artist, album, album artist, year, genre, track/disc number and MusicBrainz IDs when available.

Use **Rescan** after adding files or changing tags outside Melodex.

## Albums

Albums are the default view.

Melodex tries artwork in this order:

1. artwork explicitly supplied with the track;
2. common cover files beside the music, such as `cover.jpg`, `folder.jpg` or `front.png`;
3. embedded artwork inside the audio file;
4. an online artwork match that Melodex previously found and remembered.

Choose **Find missing artwork** to explicitly look online for albums that still have placeholders. One click now walks the complete missing-album set in small background steps rather than stopping after the first 12. The button shows the remaining count while the pass is running.

A successful online match is cached **and associated with the album**, so it remains available when you:

- leave My Music and return;
- restart Melodex;
- rebuild the visual cards.

Opening My Music by itself does not trigger a bulk online-cover search.

### Compilations and multi-artist albums

Melodex honours explicit **Album Artist** metadata first.

When that metadata is absent, it applies conservative repair rules for obvious compilations, tribute albums and soundtracks so one release is less likely to appear as a separate album for every performer. Distinct editions can still remain separate when release metadata such as year differs.

## Artists

The **Artists** view is visual rather than a text-only list.

Each artist card is semantically an **artist portrait**, not an album tile.

It shows:

- a real artist photo when one has been identified and cached;
- otherwise a neutral artist placeholder;
- album count;
- track count;
- quick View / Play actions.

Melodex deliberately does **not** use an album cover as though it were a photograph of the artist.

Choose **Get artist photos** to explicitly enrich missing portraits. One click walks the whole missing-artist list one artist at a time so the visible remaining count advances after every lookup. A failed lookup is skipped and the pass continues instead of leaving the button stuck.

The lookup is layered:

1. cached artist portrait;
2. MusicBrainz identity;
3. Wikidata portrait (P18);
4. freely licensed Wikipedia lead image from a linked page (English preferred, with other Wikipedia languages as fallback);
5. conservative Wikipedia artist-page search by name when no reliable link exists;
6. installed artwork plugins that explicitly return portrait/thumbnail imagery for an artist;
7. conservative Wikimedia Commons artist search.

If a representative track does not already contain an artist ID, Melodex can conservatively resolve the artist by name first. Single-word/common names require stronger music-context evidence before a Wikipedia page is accepted. Album covers, logos and ambiguous image matches are rejected rather than guessed.

Found photos are cached with their Wikimedia provenance and reused later.

If an artist still has no suitable freely usable portrait, hover the artist card and choose **Photo…**. Melodex copies the chosen local image into its own artwork cache and remembers it for that artist. The original image file is left untouched.


## Tracks

The **Tracks** view uses album artwork beside each track, making long lists easier to scan visually.

Each row shows:

- track title;
- artist;
- album;
- album cover;
- Play;
- Queue;
- **Edit**.

Tracks whose artist is missing are marked **Needs artist**.

## Correct bad or missing metadata

Choose **Edit** on a local track to correct:

- Artist
- Track title
- Album
- Album artist
- Year
- Genre

These corrections are stored by Melodex in its own local metadata-overrides file.

**Melodex does not rewrite the audio file or its embedded tags.**

This means a correction:

- survives a Melodex rescan;
- can immediately improve Albums, Artists and Tracks;
- can be removed later with **Use file tags again**.

This is deliberately safer than silently modifying a user's music collection.

## Unknown artists

If a track has enough title/album information, metadata lookup can still try to identify it without pretending that the literal phrase **Unknown artist** is the artist name.

For ambiguous tracks, manual correction remains the authoritative option.

## Privacy and network behavior

Local scanning, local cover files, embedded artwork and Melodex metadata corrections stay on the device.

Network requests happen only when a feature that needs them is explicitly used, such as:

- **Find missing artwork**;
- **Get artist photos**;
- other metadata-enrichment actions documented by the relevant plugin/service.

Artwork and metadata remain subject to the rights and attribution rules of their original sources.
