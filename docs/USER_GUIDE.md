# Melodex user guide

## Home

**Play for me** is the default action. It uses local listening history and your local catalogue to create a session without requiring an LLM.

## Discover

Search all connected sources at once, or choose one source from the selector.

Double-click a result to play it. Use **Add selected to queue** to keep your current track playing.

## My music

Use **Sources → Add local folder…** to add one or more folders. Melodex scans supported audio formats and reads tags where available.

The **My music** page also has an **Add folder…** shortcut to the same picker, then becomes the main place to browse your indexed local library.

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

Use **Explore gallery…** to browse community/project Recipes by tag, preview their stages, and add validated copies to your local Journey Library. Gallery Recipes are data-only and SHA-256 checked before being added.

See [Journey Library](JOURNEY_LIBRARY.md) for the file format, privacy boundary and replay behavior, and [Journey Recipe Gallery](JOURNEY_GALLERY.md) for discovery/publishing details.

## Flow queue

Flow is not random shuffle. It evaluates the current queue and, when local audio is available, analyses BPM, key, loudness, energy, onset density, timbre, intro/outro mixability and ending type. It chooses an order designed to make the next track feel intentional.

If audio analysis is unavailable, Flow falls back to metadata-only ordering rather than pretending it knows more than it does.

## Play for me

Modes:

- **Balanced** — familiar with some discovery.
- **Comfort** — stronger preference for known positive signals.
- **Rediscover** — brings back music you liked but have not heard recently.
- **Explore** — a larger novelty budget.

The Familiar ↔ Surprising slider controls how adventurous the session may be.

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

Open **Sources → User Streams…** to add direct HTTP(S) audio or internet radio streams. You can also import `.m3u`, `.m3u8` and `.pls` stream playlists. Configured streams become a normal Melodex source and can be searched, queued and played alongside other connected sources.
