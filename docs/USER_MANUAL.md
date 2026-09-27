# Melodex User Manual
## Version 0.2

**Don't shuffle. Flow.**

Melodex is a local-first music player for macOS, Windows and Linux, with an Android Bridge client. It can play your local library, direct streams and compatible providers, remember how you listen, and shape queues into more intentional listening journeys.

[Download the designed PDF edition](manuals/Melodex_User_Manual_v0.2.pdf).

## 1. What Melodex does

1. **Your music stays central.** Local files remain where they are.
2. **Sources are interchangeable.** Local files, User Streams and compatible providers can feed the same queue.
3. **Flow is not shuffle.** Melodex can reorder a queue to make transitions feel more deliberate.
4. **Taste memory is local.** Love, Keep, skips, completions and Moments help Melodex remember what matters.
5. **AI is optional.** Use the normal interface without an LLM, or connect one later.

## 2. Install

See [Install Melodex](INSTALL.md) for macOS, Windows, Linux and Android preview.

## 3. First launch

1. Open **Sources**.
2. Add a local music folder.
3. Open **My music** and confirm tracks appear.
4. Test one track.
5. Open **Play for Me**.
6. Choose a mode, duration and **Familiar - Surprising** level.
7. Build the session.

## 4. Home and Play for Me

Home gives quick access to **Play for me**, Comfort, Surprise me and Add my music.

Play for Me modes include **Balanced**, **Comfort**, **Rediscover** and **Explore**.

## 5. Flow

Flow tries to make the order of the queue meaningful rather than random.

Where analysis is available it can consider tempo, energy, key, loudness, timbre and structure. Without deep analysis it falls back rather than inventing audio facts.

## 6. Taste memory

Use Love, Keep, completions, skips and Moments as lightweight signals. Taste data is stored locally.

## 7. Music sources

v0.2 supports **This computer**, **User Streams**, **Jamendo**, **Internet Archive**, and compatible third-party `.mdxprovider` packages.

## 8. Universal Resolver

Metadata-only track requests are matched across connected sources. Open **Match** to Prefer, reject or reset a song-specific match.

## 9. Playlists

Melodex imports and exports XSPF, M3U and M3U8. A playlist can describe what should play without forcing every listener to use the same provider.

## 10. Now Playing

Melodex can enrich playback independently with MusicBrainz, Cover Art Archive, Wikimedia/Wikidata, credits and local lyrics.

## 11. Optional AI

Melodex works without an LLM. If you connect one, playback-only credentials and private local paths are stripped from LLM/control status context.

## 12. Android preview

Android currently uses the authenticated Provider Bridge running on a computer/server.

## 13. Help

- [Visual tour](VISUAL_TOUR.md)
- [FAQ](FAQ.md)
- [Troubleshooting](TROUBLESHOOTING.md)
