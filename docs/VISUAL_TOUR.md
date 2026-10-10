# Melodex visual tour — v0.7.29

These are the screens and interactions in the October 2026 desktop release. The latest real-world screenshot set is prepared for the gallery; see the screenshot upload instructions below. For the older Home and library screens, the illustrations below remain useful orientation aids.

## Explore: three ways into the library

Open **Explore** from the left sidebar. Its deliberately simple landing page offers **Search everything** (find artists, albums and tracks), **Album Wall** (browse by artwork), and **Music Map** (explore track relationships). Quick actions let you find music similar to the current track, rediscover an old favourite, or ask Melodex for help. You do not need AI or a connected server just to browse and play local files.

## Album Wall: your collection as a place

**Explore → Album Wall** shows a pannable field of album covers rather than a long text list. Arrange by **Sound** to explore a sonic layout; use **Find** to locate an artist or album and **Now playing**, **Actual size**, and **Overview** to navigate. Selecting an album reveals actions for playback and queueing. Artwork loads progressively: an on-screen count of loaded covers is not the number of albums in the library.

## Music Map: explore how tracks relate

**Explore → Music Map** presents songs and clusters as cover-art nodes. Pan, zoom, search, and fit the map to the window. Selecting a track opens a small action card with **Play**, **Queue**, **Play from here**, **Plan a journey**, and nearby relationships. Cluster labels/counts summarize grouped positions. This is a navigable local map, **not** a claim that every link represents a verified factual music relationship.

## Plan a path through your music

Select a starting track and a destination on the Music Map to build a path. **Preview route** displays the proposed hops on the map before you choose **Play** or **Queue**. In the illustrated four-hop example the route summary explicitly distinguishes **0 factual** from **4 sonic** connections and reports a score of **11%**. These numbers describe that example, not a universal accuracy or relevance guarantee.

## Now playing: context, artwork, lyrics

Select the current track in the bottom playback bar, then use **Now Playing** to see large cover art, artist/release details, optional MusicBrainz enrichment and contextual sections (**Lyrics**, **Artist**, **Releases**, **Credits**, **Context**, **Info**). Choose a lyrics source, refresh, search or open full screen. Where timed lyrics exist, the player can highlight lines in sync with playback; synchronization quality depends on available lyric data. Optional translation may require a configured model.

## Visuals: Constellation

In **Now playing → Visuals**, select **Constellation** to browse related music as interactive nodes around the current track. Hover for details and double-click where prompted to queue a song. This is a music navigation surface, not just a decorative screen saver.

## Persistent playback

The bottom bar remains available throughout the app, with transport controls, seek position and actions for **Keep**, favourites, **Taste**, **Queue**, and **Match**. Advanced controls stay secondary so the music remains the focus.

## First launch

1. [Get the desktop installer](https://github.com/Cliff-Lee/melodex/releases/latest).
2. Choose **My Music → + Add music** and point to your music folder.
3. Return to **Home** to begin listening, or open **Explore** for Album Wall and Music Map.

Mac builds are currently unsigned; follow the [macOS security instructions](INSTALL_MACOS.md) rather than disabling Gatekeeper globally.

## Screenshot set for this version

Six screenshots supplied from the running v0.7.29 desktop app have been optimized as WebP assets for the planned gallery:

| Asset filename | What it demonstrates |
| --- | --- |
| `now-playing-lyrics.webp` | Current track, enriched recording context and synced lyric controls |
| `explore.webp` | Minimal Explore landing page and three entry points |
| `album-wall.webp` | Artwork-first browsing and arrangement/search controls |
| `music-map.webp` | Track clusters, search and nearby-song actions |
| `music-map-route.webp` | Path preview with sonic hops and route actions |
| `now-playing-constellation.webp` | Interactive Constellation visual and playback timeline |

These image files still need to be uploaded into `docs/images/v0.7.29/` to complete the gallery. Until then, the older repository images are not being presented as v0.7.29 captures.

For additional detail, read the [Album Wall](ALBUM_WALL.md) and [Music Map](MUSIC_MAP.md) guides.
