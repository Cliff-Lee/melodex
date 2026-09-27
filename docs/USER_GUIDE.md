# Melodex User Guide

For the polished illustrated release guide, download the **[Melodex User Manual v0.2](manuals/Melodex_User_Manual_v0.2.pdf)**.

## Home

**Play for me** is the default action. It uses your catalogue, local listening history and available audio analysis to create a session without requiring an LLM.

The Home page also gives quick routes to **Comfort**, **Surprise me** and **Add my music**.

## Discover

Search all connected sources at once, or choose one source from the selector.

- Double-click a result to play it.
- Use **Add selected to queue** to preserve the current track.
- **Open source page** returns to the provider's public source page when available.

External providers may need several seconds to resolve playable media. Very large Internet Archive items can take longer than ordinary tracks.

## My music

Add one or more folders. Melodex scans supported audio files and reads tags where available. Your originals remain in place.

Common formats include MP3, FLAC, M4A, AAC, OGG, Opus, WAV, AIFF and WMA.

## Play for Me

Modes:

- **Balanced** - familiar with some discovery.
- **Comfort** - stronger preference for known positive signals.
- **Rediscover** - bring back music you liked but have not heard recently.
- **Explore** - allow more novelty.

Choose a session length and move **Familiar - Surprising** to describe what you want now.

## Flow

Flow is not random shuffle. It tries to make the sequence itself make sense.

When local analysis is available, Flow can consider tempo, key, loudness, energy, onset density, timbre, intro/outro mixability and ending type. If deep analysis is unavailable, Melodex falls back rather than inventing audio facts.

## Taste controls

- **Keep** - this track belongs in your musical world.
- **Love** - stronger positive signal.
- completed tracks - positive evidence.
- early skips - weak negative evidence.

One skip is not a permanent judgement.

## Moments

Use **... -> Save Moment** to bookmark the exact playback position of a lyric, solo, transition, drop or other moment you want to remember.

## Queue

Open **Queue** to inspect or jump to upcoming tracks. Use **Flow queue** when you want Melodex to resequence the remainder of the session.

## Playlists

Melodex imports and exports **XSPF, M3U and M3U8**.

A playlist can contain local files, direct URLs, provider identities, or only artist/title/album metadata. Metadata-only entries are resolved against the sources connected on the current device.

See [Playlist interchange](PLAYLIST_INTERCHANGE.md).

## Now Playing

Playback and music knowledge are separate.

Melodex can progressively enrich a track with MusicBrainz identity, Cover Art Archive artwork, Wikidata/Wikimedia Commons imagery, credits, relationships, release information and local lyrics.

Metadata lookups do not need to block playback.

## Sources

### This computer
Your indexed local files.

### User Streams
Open **Sources -> User Streams...** to add direct HTTP(S) audio/radio streams or import local `.m3u`, `.m3u8` and `.pls` stream playlists.

### Jamendo
Supply your own developer client ID through **Sources -> Jamendo settings...**.

### Internet Archive
Internet Archive is an official optional `.mdxprovider` for publicly accessible Archive audio. Public items do not require Archive credentials. The provider does not bypass login, lending, DRM or restricted-item protections.

### Third-party providers
Enable **Show power tools**, choose **Install `.mdxprovider`...**, and review publisher/permissions before installing. Provider packages are executable software.

## Universal Resolver and Match

Melodex can resolve an artist/title/album request across multiple sources.

If a match is wrong, open **Match** and use **Play this match**, **Prefer**, **Wrong match**, or **Reset memory**.

Match memory is song-specific; it does not globally force one provider.

## Ask Melodex

AI is optional. Connect Ollama, OpenWebUI or another compatible model if you want natural-language control.

> Keep this mood, but make the next hour stranger.

Playback-only secrets such as headers, cookies, refresh tokens, signed stream URLs and local file paths are stripped from LLM/control status context.

See [LLM Guide](LLM_GUIDE.md) and [MCP Control](MCP_CONTROL.md).

## More help

- [User Manual v0.2 PDF](manuals/Melodex_User_Manual_v0.2.pdf)
- [Visual tour](VISUAL_TOUR.md)
- [Sources](SOURCES.md)
- [FAQ](FAQ.md)
- [Troubleshooting](TROUBLESHOOTING.md)
