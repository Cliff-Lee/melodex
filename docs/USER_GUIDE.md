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

Click a node to inspect it. Double-click to play it. The page can also **Add selected to queue** or **Start journey here**, which hands that track back to Mind + Flow as the session anchor.

The map uses cached local analysis only. **Analyse my library** is an explicit action; simply opening the map does not silently analyse every file.

For large analysed libraries, the first implementation displays a bounded representative map rather than trying to draw every track at once.

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
