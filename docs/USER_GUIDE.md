# Melodex user guide

## Home

Home is organised around listening intentions rather than setup.

Use:

- **Play something** for a balanced session from your local library;
- **Comfort** to stay closer to familiar positive signals;
- **Explore** to allow more surprise;
- **Rediscover** to bring back music you have not heard recently;
- **Tune it…** when you want explicit duration/style/familiarity controls.

**Continue listening** provides a visual way back to the most recent track.

Core playback, taste memory and local Flow do not require an LLM.

## Now Playing and Visuals

Open **Now Playing** by clicking the current track in the persistent player.

The default **Now Playing** tab leads with artwork, lyrics and track context. Optional visualisations live under **Visuals** so the music remains primary.

### Native Lyrics

Open the **Lyrics** tab while a track is selected. Lyrics are a built-in Melodex experience even when an installed extension supplies the words.

The compact toolbar contains:

- **Source** — choose between available lyric results such as saved/local lyrics, an installed lyric source, or LRCLIB;
- **Refresh lyrics** — re-check saved, embedded and installed lyric sources first, then use the online fallback only if nothing else matches;
- **Full screen** — open the synchronized large-type view;
- **Translate** — explicitly use your configured LLM for a temporary translation;
- **More** — edit a saved personal copy, add/paste lyrics, control Auto-find online, or manage optional lyric sources.

Synchronized lines highlight with playback and remain click-to-seek. Installed `lyrics.lookup` extensions participate automatically; you do not open or operate a separate plugin page to use them.

Online LRCLIB results can be cached privately in Melodex's local metadata cache so returning to the same track is immediate. The cache does not rewrite your music files, and provider-supplied lyrics remain read-only.

### Artist, Releases, Credits and Context

These tabs are native Now Playing summaries rather than separate plugin pages.

- **Artist** gives a compact identity, origin, tags, members/projects and useful links. The artist portrait appears once in the Now Playing hero rather than being repeated in the tab.
- **Releases** shows a concise selection of release groups with MusicBrainz links for the full discography.
- **Credits** groups names by role instead of presenting a long relationship dump.
- **Context** always uses the track, artist and recording information Melodex already knows. Optional context extensions can add liner notes, relationships and community signals, but an unavailable source does not leave the whole tab empty.

Choose **Context → Sources…** when you want to inspect or manage optional context extensions.

In **Visuals**, choose a view from the selector. Each track has a repeatable visual identity. Cached Flow features shape its scene when available; album artwork supplies a sampled colour palette.

The modes include the animated Living Canvas, Song Fingerprint, the seekable Musical Journey, a queue/history Constellation, local Lyrics Typography, Album World, Sonic Weather, a local Visual Memory atlas and Minimal. Constellation stars can be inspected with a click and queued with a double-click. Visual Memory can zoom by session, album, week or year; it reads only the listening history already stored on this device.

Click or drag the journey contour to seek, or focus it and use the arrow keys. Flow analysis is read from its cache in the background. If no cached analysis exists, Melodex shows an identity-based scene and a clear fallback message. It never analyses audio during playback. Auto quality is capped at 15 fps and reduces detail if drawing slows down; Eco, High (30 fps) and Battery (static) are available. Animation pauses when playback pauses, the visualizer tab is hidden, or the window is minimized.

Use **Add visualizer…** to add a `.mdxviz` recipe. These are bounded JSON scene descriptions, not executable plugins. See the [visualizer author guide](visualizers/README.md) for the format and example.

The canvas uses a restrained track-colour backdrop and clear track labels. The seekable Musical Journey combines its waveform and progress position in one control; click or drag it to seek, or focus it and use the arrow keys.

## Playlists

Open **Playlists** to import or export a playlist file, or choose **Paste from AI…** to bring in a playlist created in ChatGPT, Claude, Gemini or another AI chat. Choose **Copy ChatGPT Prompt** for a ready-to-use prompt, paste the reply into the box (or use **Paste Clipboard**), then choose **Analyse Playlist**. No AI connection or API key is needed.

Melodex reads the track list and matches it through your connected music sources. Matched tracks are saved as a playlist and added to the queue; unmatched requests are kept in the saved playlist for later matching. Melodex does not send the pasted text to an AI service. Your connected music providers may receive artist/title searches during matching. JSON, Markdown lists or tables, plain text, CSV/TSV and M3U text are supported; **Import File…** also accepts JSON, text, CSV/TSV, XSPF and M3U/M3U8 files.

## Explore and Search

Open **Explore** when you want to move beyond the current session.

It offers three clear routes:

- **Search everything** — search connected music sources;
- **Album Wall** — browse your own collection spatially;
- **Music Map** — explore sonic relationships and plan routes.

Search can query all connected sources at once. Desktop Melodex includes six bundled streaming providers on first launch: ccMixter, SomaFM, Radio Browser, Wikimedia Commons Audio, LibriVox and Internet Archive Audio. Their catalogues stay online at their original services; Melodex does not bundle or redistribute their audio.

Provider internals, diagnostics and priority controls live under **Sources & plugins → Power tools**. See [Music sources](SOURCES.md) for details and rights notes.

## My Music

Open **My Music** to add and browse local music.

Choose **+ Add music** to add one or more folders. Melodex scans supported audio formats in place and reads tags where available.

The default **Albums** view is a responsive artwork grid. **Artists** is also visual, using cached artist photos when available and falling back to representative album artwork. **Tracks** uses album art beside each track so long lists remain recognisable.

Choose **Find missing artwork** to explicitly look online for missing album covers. Successful matches are cached and remembered, so they remain when you leave the page, restart Melodex or rebuild the cards.

In Artists, **Find artist photos** explicitly looks for missing artist imagery and remembers successful matches.

If a local track has incomplete metadata, open **Tracks → Edit**. You can correct artist, title, album, album artist, year and genre. Corrections are stored by Melodex and survive rescans, but **do not rewrite your original audio files or their embedded tags**.

See [My Music](MY_MUSIC.md) for the full artwork, metadata and privacy model.

## Music map

**Music map** turns cached local Flow analysis into a zoomable sonic landscape.

Each dot is an analysed local track. Nearby dots have similar combinations of tempo, energy, key, timbre, rhythmic density and mixability. Thin lines connect the nearest local neighbours.

Use the colour selector to view the same landscape through different lenses:

- **Sonic colour** — key/energy-oriented colour;
- **Energy** — calmer to more energetic;
- **Taste** — stronger positive local taste signals;
- **Rediscovery** — tracks that have positive history and may be ready to return.

Click a node to inspect it. Double-click to play it. The page can also **Add selected to queue** or **Start Mind journey here**, which hands that track back to Mind + Flow as the session anchor.

The map uses cached local analysis only. **Analyse my library** is an explicit action; simply opening the map does not silently analyse every file.

The **Connections** selector separates two questions:

- **Sounds similar · Flow** — nearest neighbours in the local Flow feature space;
- **Actually connected · all** — cached factual links such as same artist/album, production, performers, composition credits, shared works, sample/remix/version relationships, artist relationships and recording places.

Normal Now Playing enrichment gradually grows the factual graph. **Enrich selected** enriches one mapped track; **Enrich map (+8)** explicitly enriches a bounded batch using MusicBrainz and enabled context plugins.

**Pathfinder** can then route between two mapped tracks. Set a start and destination, choose **Balanced**, **Sonic** or **Knowledge-first**, and press **Find path**. The route is highlighted and every hop explains whether it used Flow similarity, a factual relationship, or both. **Play route** and **Queue route** turn the result directly into listening.

**Journey Designer** adds ordered constraints/waypoints to those same endpoints. Load the **Calm → Darker → Forgotten → Energetic** preset, add individual semantic stages, or add the selected mapped track as an exact waypoint. **Build journey** chooses transparent stage fits, highlights the chosen waypoints in purple and preserves an explanation for every hop. If the library cannot honestly satisfy a requested stage, Melodex says so rather than silently weakening the meaning.

**Journey Live** makes that designed journey adaptive during playback. Choose **Play live journey**, then use Calmer/More energy/Darker/Brighter/Rhythmic/Familiar/Surprising/Rediscover steering, **Avoid current artist**, or **Replan remaining**. A manual Next/Skip replans only the queue tail; normal completion/crossfade does not. **Restore designed route** clears Live avoid rules and returns the unfinished journey toward the original design.

For large analysed libraries, the first implementation displays a bounded representative map rather than trying to draw every track at once.

See [Music Map](MUSIC_MAP.md) for the detailed model and privacy/network behaviour.

## Journeys

**Journeys** is the local library for reusable Journey Recipes and private Journey Live run history.

A **Recipe** saves the Journey Designer intent—routing mode, semantic stages and optional exact-track waypoints—but deliberately does not save start/destination tracks. Use **Save current design**, **Load into Music Map**, **Import…** and **Export…** to reuse or share that shape as a `.mdxjourney` file.

Exact track waypoints are exported using portable identity selectors rather than local file paths. Loading a recipe refreshes Music Map, restores the routing mode/stages and reports any exact waypoint that cannot be found.

A **Run** is private local history of a Journey Live session. **Inspect** compares the designed route with the final adapted route and lists steering/skip/avoid/replan decisions. **Replay designed** and **Replay final** rematch the recorded tracks onto the current Music Map; missing tracks are reported rather than silently substituted.

See [Journey Library](JOURNEY_LIBRARY.md) for the file format, privacy boundary and replay behavior.

## Flow queue

Flow is not random shuffle. It evaluates the current queue and, when local audio is available, analyses BPM, key, loudness, energy, onset density, timbre, intro/outro mixability and ending type. It chooses an order designed to make the next track feel intentional.

If audio analysis is unavailable, Flow falls back to metadata-only ordering rather than pretending it knows more than it does.

## Tune your listening

Home exposes simple listening intentions first. Choose **Tune it…** when you want the underlying session controls.

Modes:

- **Balanced** — familiar with some discovery.
- **Comfort** — stronger preference for known positive signals.
- **Rediscover** — brings back music you liked but have not heard recently.
- **Explore** — a larger novelty budget.

The Familiar ↔ Surprising slider controls how adventurous the session may be.

### Local intelligence

The Play for me page can ask installed plugins to work with a sanitized snapshot of your own library:

- **More like current** finds close sonic neighbours;
- **Forgotten favourites** resurfaces positive-but-stale tracks;
- **Bridge current → next** suggests a local track that could connect the two;
- **Find a detour** keeps one sonic feature and deliberately changes two others.

Use **Improve suggestions** to prepare Flow features first. Suggestions and taste history stay local; plugins receive no audio, file paths or database IDs.

## Taste controls

- **Keep**: positive ownership/interest signal.
- **♥**: explicit strong positive signal.
- early skips: weak negative signal.
- full listens: positive completion signal.

Taste data is stored locally.

## Moments

Save the exact playback position of a musical moment you want to remember.

## Queue

Open the Queue panel to inspect or jump to upcoming tracks. **Flow queue** can reorganise it.

## User Streams

Open **Sources & plugins → My streams** to add direct HTTP(S) audio or internet radio streams. You can also import `.m3u`, `.m3u8` and `.pls` stream playlists. Configured streams become a normal Melodex source and can be searched, queued and played alongside other connected sources.
