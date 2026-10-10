# Music Map

Music Map is Melodex's local spatial view of your analysed music library.

It deliberately separates two different questions:

> **What sounds similar?**

and

> **What is actually connected?**

The dots keep the same sonic positions while the **Connections** selector changes which relationships are drawn between them. The default is deliberately **Selected relationships**: the map starts visually quiet, then reveals the selected track's immediate sonic relationships. This avoids turning a library into an unreadable web before the listener has chosen what to inspect.

## 1. The sonic landscape

A mapped point represents a local track with cached Flow analysis. Album-cover art is used for each point when available locally. Hovering a point expands it into a track card with title, artist, album, and analysis details.

Its position is derived locally from:

- energy;
- tempo;
- spectral centroid / brightness;
- rhythmic density;
- tonal position and mode;
- intro/outro mixability.

Nearby dots therefore have similar combinations of those Flow features.

This is an explainable projection of Melodex's current analysis features, not a claim that musical similarity has one objectively correct geometry.

## 2. Focus first, then expand

The default view is:

**Connections → Selected relationships**

No connection web is drawn until you select a track. Melodex then shows only that track's immediate sonic neighbours, keeping the spatial layout readable and making the selected object the clear focus.

When you explicitly want the whole sonic network, choose:

**Connections → All sonic links**

Melodex then draws the local nearest-neighbour edges in the Flow feature space using deliberately quieter lines.

These edges answer:

> Which analysed tracks are sonically closest according to Melodex's current local feature model?

Outliers can remain islands rather than being connected by a misleading long edge.

## 3. Actually connected

Choose:

**Connections → Actually connected · all**

or filter to one factual relationship family:

- **Same artist**
- **Same album**
- **Production**
- **Performers**
- **Composition credits**
- **Shared works**
- **Samples / remixes / versions**
- **Artist relationships**
- **Recording places**

These edges come from cached local knowledge rather than from sonic distance.

Examples:

```text
Track A ── produced by Jane Producer ── Track B

Track C ── guitar: Player X ── Track D

Track E ── performance of Work W ── Track F

Track G ── samples ── Track H

Track I ── recorded at Studio Z ── Track J
```

Knowledge coverage depends on the metadata available for your particular music. Missing an edge does **not** prove the real-world relationship does not exist.

## 4. Where knowledge comes from

Music Map can learn from several sources already inside Melodex:

1. **local tags**
   - artist / album;
   - MusicBrainz identifiers when your files contain them;

2. **normal Now Playing enrichment**
   - MusicBrainz recording/artist identity;
   - recording credits and linked works;
   - artist relationships;
   - context plugin cards;

3. **explicit Music Map enrichment**
   - **Enrich selected**
   - **Enrich map (+8)**

The local knowledge index is stored in Melodex's application data so ordinary listening gradually improves the factual graph.

## 5. Network behaviour

Simply opening or refreshing Music Map does **not** start a hidden metadata crawl.

Normal map refresh uses:

- cached Flow analysis;
- local tags;
- the local Music Map knowledge index.

The explicit enrichment buttons may contact MusicBrainz and enabled context plugins.

**Enrich selected** enriches one mapped track.

**Enrich map (+8)** processes a bounded batch of at most eight mapped tracks that still have incomplete knowledge. The batch is deliberately bounded because MusicBrainz and other public services have rate limits and because users should remain in control of network enrichment.

## 6. Song Connections plugin

If the **MusicBrainz Song Connections** context plugin is installed and enabled, its cached results can add direct track-to-track edges for relationships such as:

- samples;
- sampled-by;
- remixes;
- edits;
- mash-ups;
- alternate versions;

when both recordings exist in the mapped local library.

Without that plugin, Music Map still supports local artist/album links and MusicBrainz credits, works and artist relationships.

## 7. Knowledge colours and sonic colours are independent

The **View** selector changes the dots:

- Sonic colour
- Energy
- Taste
- Rediscovery

The **Connections** selector changes the edges.

For example:

```text
View: Rediscovery
Connections: Production
```

shows which tracks may be ready to return while simultaneously revealing common production links.

That separation is intentional.

## Progressive disclosure and navigation

Music Map keeps the **graph visible while its tools open**. Its main browsing surface has
a compact search field, **View**, zoom controls, **Fit**, a separate **Journey** action
and a quiet **More…** menu for occasional analysis and enrichment.

- **Select a track once** to reveal a contextual Play / Queue / Start journey card.
  A second/double-click activates playback as before; selecting does not play.
- When the selected track has *actual mapped relationships*, the contextual card
  also shows up to **two Explore nearby suggestions**. Suggestions are based on
  existing audio-feature similarity edges and/or cached metadata relationships,
  not spatial pixel distance. The hover tooltip states the evidence, while a
  concise connection type is visible on the chip. Selecting a suggestion changes
  map focus and adds a navigation history entry; **it does not start playback**.
  If a track has no mapped neighbours, no speculative suggestions are shown.
- **View** floats over the graphics viewport and contains colour modes and the
  detailed connection filters. It never occupies a new row in the page layout.
- **Journey** opens a right-hand overlay containing existing Route / Compose / Live
  controls. It does not push the map down. Select a start and destination on the map,
  then preview and play or queue the result.
- **More…** contains explicit local-analysis, refresh and metadata-detail actions.
  Its overlay is anchored *below* the search toolbar.
- Only one settings/Journey overlay is shown at a time. Contextual track actions
  temporarily hide while a tool is open and return when it closes.
- **Escape** dismisses an open overlay without cancelling selection or playback.
  The Journey drawer also has an explicit Close control.
- Both the Journey drawer and compact track card stay inside the graphical
  viewport at supported window sizes rather than increasing the page's height.

Map movement is unchanged: drag empty space to pan, trackpad scroll to pan,
mouse-wheel or Cmd/Ctrl-scroll to zoom, and use **+ / −** and **Fit** if preferred.
At overview zoom, dense regions are grouped into representative album-cover
tiles labelled with a mapped-track count; clicking a group zooms into its
individual tracks. The groups are **spatial summaries of the existing Flow
feature projection**, not inferred genres or factual links. Selected,
currently-playing and active-route tracks stay individually visible. On
closer zoom, all individual covers reappear; zoom navigation can be reversed
with Back. Small or dispersed maps are left unclustered.

**MM2-3b** adds artist-grounded landmarks beneath overview covers, with
the count displayed on each tile. If no artist is strongly represented
in that cell, the label says "Mixed artists"; it never invents a genre
or listening mood. On clustered overviews, an optional **Regions** control
lists up to eight of the largest mapped groups. Selecting one zooms in
without changing playback, and **Back** restores the previous viewpoint.
The Regions control disappears when the map shows individual tracks.

The full semantic-zoom/artist-landmark system is still being developed.
All mapped tracks keep their original graph identities and route calculations,
and the entire map remains a bounded analysed preview, not the whole library.

### Navigation (MM2-2a)

- **Back** and **Forward** (or Alt+Left / Alt+Right) revisit positions reached through track searches, **Now Playing**, or **Fit**. History stores the position, zoom and selected track; returning to a location does not change playback.
- **Find playing track** (◎) locates the currently playing song **only if it is represented among the mapped tracks**. When a playing track is outside the bounded preview, Melodex explains that limitation and leaves the map where it is.
- Searching for a mapped artist or track selects and centres it, adding the previous camera to Back history.
- Manual panning and zooming remain free-form; history is recorded at deliberate navigation actions, not at every pixel of dragging.
- Refreshing/rebuilding a projection clears camera history, preventing older saved scene coordinates from leading to misleading locations.

These navigation features are **in the MM2 development branch** and are not yet part of a public release.

Global **Power tools** does not force the map's advanced panels open.

## 8. Privacy

The Music Map itself is Core-owned and local.

Opening the map does not:

- upload audio;
- send your graph to an LLM;
- use a remote embedding service;
- publish your library;
- send the graph to the Plugin Directory.

The explicit enrichment actions send the metadata required by their documented metadata/context sources. They do not upload your audio files.

See [Privacy](PRIVACY.md) for the wider Melodex data model.

## 9. Large libraries

The current preview renders a bounded map of up to 700 analysed tracks.

For larger analysed collections, Melodex retains strong/rediscoverable tracks plus a deterministic breadth sample from the remaining library.

The map is therefore an exploration view, not an assertion that every indexed track is simultaneously visible.

## 10. Starting a journey

Select a track and choose **Start journey** in its contextual card. This sets
the selected song as the Pathfinder start and opens Journey tools; choose another
mapped track as a destination and request a route. Within Journey, **Start listening
here** is a separate way to launch an open-ended Mind + Flow listening session.

The selected mapped track becomes the starting anchor for Mind + Flow.

This closes the loop:

```text
see a region
    ↓
inspect its sonic / factual relationships
    ↓
choose a track
    ↓
Start Mind journey here
    ↓
Mind + Flow builds the listening path
```

Music Map is intended to be a listening interface, not just a visualization.

## 11. Pathfinder

Pathfinder turns the map into an explainable route planner.

Workflow:

1. click a mapped track and choose **Set start**;
2. click another mapped track and choose **Set destination**;
3. choose a routing mode;
4. choose **Find path**.

Available modes:

- **Balanced** — combines Flow similarity and factual knowledge;
- **Sonic** — uses Flow similarity only;
- **Knowledge-first** — prefers documented relationships and uses an explicitly labelled sonic bridge only when needed to cross disconnected factual regions.

The route is computed in the full standardized Flow feature space rather than by measuring 2D screen distance.

Each hop records its reason. Examples:

```text
Flow similarity 87%

Producer P · producer · Flow similarity 61%

shared work: Work W · Flow similarity 54%

samples · Flow similarity 32%
```

The map draws the resulting route as a numbered overlay while a step list shows the same explanations in text.

Choose **Play route** to replace the queue with the route, or **Queue route** to append it.

Pathfinder is deterministic and local. Finding a route does not contact MusicBrainz, context plugins, an LLM or a remote recommender. It only uses the sonic vectors and factual knowledge already present in the current map.

## 12. Journey Designer

Journey Designer adds ordered waypoints and semantic constraints on top of Pathfinder.

The composer shows a **Start → stages → Destination** route shape. Drag a track from Music Map onto either endpoint or into the timeline as an exact waypoint. You can also click an endpoint to use the currently selected track. Click a direction to add it at the end, or drag it into a particular position. Drag existing stages to reorder them; Move up / Move down remain available for keyboard and precise control. Hover a direction to see what its label means.

Stages are optional. With an empty timeline, **Build journey** finds a direct route from Start to Destination.

It uses the same **start**, **destination** and routing mode as Pathfinder, but the route can be required to pass through stages such as:

- **Calm**
- **Darker**
- **Forgotten**
- **Energetic**
- **Bright**
- **Rhythmic**
- **Familiar**
- **Surprising**

You can also add the currently selected mapped track as an exact waypoint.

A journey can therefore express:

```text
Start
  ↓
Calm
  ↓
Darker
  ↓
specific track waypoint
  ↓
Forgotten
  ↓
Energetic
  ↓
Destination
```

Starting shapes include:

- **Gentle → darker → energy**
- **Calm → rhythm → energy**
- **Familiar → rediscovery → bright**
- **Surprising → darker → bright**

### How semantic stages are scored

These labels are not LLM judgements.

They are transparent combinations of fields already present in the map:

- **Calm** — low energy, gentler tempo and lower rhythmic density;
- **Darker** — lower spectral brightness, minor-mode character and suitable mid/low energy;
- **Forgotten** — high local rediscovery signal plus positive taste history;
- **Energetic** — energy, tempo drive and rhythmic density;
- **Bright** — higher spectral brightness, major-mode character and energy;
- **Rhythmic** — rhythmic density, tempo drive and mixability;
- **Familiar** — positive taste plus prior plays;
- **Surprising** — low prior exposure and lower familiarity.

Each chosen waypoint stores its stage-fit score and the component explanation.

If a requested stage is not represented strongly enough in the current mapped library, Journey Designer fails explicitly rather than assigning a misleading label to a weak candidate.

### Route construction

Journey Designer:

1. scores potential waypoints for the requested stage;
2. prefers candidates near the appropriate part of the start→destination sonic trajectory;
3. checks that the candidate is actually routable;
4. checks that the final destination remains reachable;
5. builds the complete journey from reusable Pathfinder segments.

The expensive sonic/knowledge routing network is prepared once and reused while waypoint candidates are evaluated.

Purple-outlined nodes are semantic or explicit Journey waypoints. The route remains numbered and every normal Pathfinder hop explanation is preserved.

### Network and privacy behavior

Journey design is local.

It uses only:

- current Music Map Flow vectors;
- local taste/rediscovery values already in the map;
- cached factual knowledge edges.

Building a journey does not call an LLM or trigger metadata enrichment. Network enrichment remains a separate explicit user action.

## 13. Journey Live

Journey Live makes a designed journey adaptive **while it is playing** without turning it into an opaque recommender.

Start with a successful Journey Designer result, then choose **Play live journey**.

Melodex keeps:

- the fixed destination;
- the stages already completed;
- the stages still unsatisfied;
- the current routing mode;
- the current track already playing.

Only the **remaining queue tail** is eligible for replacement.

### Explicit steering

The first steering controls are:

- **Calmer next**
- **More energy next**
- **Darker next**
- **Brighter next**
- **More rhythmic next**
- **More familiar next**
- **More surprising next**
- **Rediscover next**

A steering request is implemented as a temporary transparent semantic stage at the front of the unfinished journey.

For example:

```text
current track
    ↓
More energy next
    ↓
Forgotten
    ↓
Energetic
    ↓
original destination
```

Once that temporary steering stage has been reached, later replans do not restart it.

### Skip + replan

During an active Journey Live session, the normal **Next** button and **Skip + replan** are explicit adaptation events.

Melodex:

1. advances to the next track normally;
2. keeps that new current track playing;
3. excludes the skipped track from the remaining plan;
4. replans only what comes after the current track.

If the skipped track was a semantic waypoint and it was abandoned within the first 30 seconds, that semantic stage is reopened and Journey Live looks for an alternative waypoint.

This 30-second rule deliberately matches Melodex's existing conservative skip signal.

Automatic completion and normal crossfades do **not** trigger Journey Live replanning.

### Avoid current artist

**Avoid current artist** adds the playing artist to the remaining-route exclusion set.

That artist cannot be used as a new waypoint or intermediate bridge track. The already-playing track is never interrupted, and a fixed final destination remains allowed even when it belongs to an avoided artist.

### Replan remaining

**Replan remaining** rebuilds the unfinished journey from the current track using the current stages, avoid rules and routing mode.

### Restore designed route

**Restore designed route** clears Live avoid rules and reconstructs the unfinished portion from the original Journey Designer result.

Completed stages remain completed; restore does not rewind playback.

### Failure safety

If a Live replan cannot satisfy the remaining route, Melodex leaves the existing queue unchanged and explains the failure.

A stale replan result is also discarded if playback advances while planning; Melodex recalculates from the new current track.

### Map refreshes

Music Map refs are intentionally request-local. Refreshing/rebuilding the map therefore ends the active adaptation session rather than pretending old refs are still valid. Playback continues using the existing queue.

### Local-only behavior

Journey Live uses:

- cached Flow route vectors;
- current map taste/rediscovery values;
- cached factual edges;
- the original local Journey Designer result.

It does not contact metadata services, extensions, an LLM or a cloud planner while adapting the route.
