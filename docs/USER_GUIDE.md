# Melodex user guide

This guide matches the Melodex desktop v0.7.2 release.

Melodex is a music player first. Add music from your computer, search connected sources, and let a listening session take the shape you want. AI features are optional.

## Start listening

Home is the quickest place to begin. Choose **Play something** for a balanced session, or pick **Comfort**, **Explore**, or **Rediscover** first. **Continue listening** returns to your most recent track.

Choose **Tune it…** to adjust a session. Its **Familiar — Adventurous** control sets how far the session can move from music you already know.

If you have not added local music, open **Explore → Search everything** to search connected music sources.

## Add and browse your music

Open **My Music → + Add music** and choose a folder. Melodex indexes supported files where they are; it does not move or upload them.

The **Albums** view makes it easy to scan a collection by its covers. Choose **Find missing artwork** to look for covers that are not already available locally. In **Artists**, **Get artist photos** looks for artist portraits; cards use a neutral placeholder when no suitable photo is found. Album covers are not used as artist portraits.

In **Tracks**, choose **Edit** to correct a title, artist, album, album artist, year, or genre. Melodex keeps these corrections locally and does not change the original audio file or embedded tags.

See [My Music](MY_MUSIC.md) for artwork and metadata details.

## Find music and explore the collection

**Explore → Search everything** searches connected music sources. Desktop Melodex includes ccMixter, SomaFM, Radio Browser, Wikimedia Commons Audio, LibriVox, and Internet Archive Audio. These services host their own catalogues and audio. More sources and optional extensions are available through [Sources & plugins](SOURCES.md).

**Album Wall** lays out your collection so you can browse and play albums visually. **Music Map** shows relationships between local tracks and lets you plan a listening route. Both are available from Explore. Their detailed controls are in the [Album Wall guide](ALBUM_WALL.md) and [Music Map guide](MUSIC_MAP.md).

## Now Playing and lyrics

Select the current track in the persistent player to open **Now Playing**. The **Lyrics** tab is part of Melodex itself. Available lyrics appear in one synchronized view, including results from installed lyric extensions.

- **Source** switches between available lyric versions.
- **Refresh lyrics** checks available sources again.
- **Full screen** opens a larger, synchronized view.
- **Translate** uses a configured language model only when you request a translation.
- **More** contains personal-copy and online lookup settings.

Synchronized lines follow playback; select a line to seek to that point in the track. Lyrics are optional. You can keep using the player without setting up an extension or AI service.

The separate **Visuals** tab has optional music visualisations. They use cached analysis when it is available and do not analyse audio during playback.

See [Now Playing](RICH_NOW_PLAYING.md) for more.

## Queue and Flow

The queue shows what is coming up. Choose **Flow queue** to reorder queued tracks into a smoother sequence. Flow uses local audio analysis when available and falls back to track information when it is not.

## Playlists

Open **Playlists** to import or export a playlist. Choose **Paste from AI…** to bring in a list made in ChatGPT, Claude, Gemini, or another chat. Copy the list into Melodex and choose **Analyse Playlist**. No AI connection or API key is needed.

Melodex parses the text on your device. To find playable matches, it may send artist and title searches to music sources you have connected. Requests that cannot be matched remain in the saved playlist for later.

See [Playlist interchange](PLAYLIST_INTERCHANGE.md) for supported formats and details.

## Teach Melodex what you like

Use **Keep** when a track belongs in your collection of favourites, or choose **♥** for a stronger positive signal. Skipping and finishing tracks also help shape future sessions. Taste history stays on your device.

Save a **Moment** when you want to remember a particular point in a track. Moments can be opened from My Music or Now Playing.

## More help

- [Make Melodex yours](TINKERERS_GUIDE.md) for optional sources, plugins, routes, and integrations.
- [5-minute visual tour](VISUAL_TOUR.md)
- [Journeys](JOURNEY_LIBRARY.md)
- [Music sources](SOURCES.md)
- [Privacy](PRIVACY.md)
- [Troubleshooting](TROUBLESHOOTING.md)
