# Music Map

Music Map is Melodex's local spatial view of your analysed music library.

It deliberately separates two different questions:

> **What sounds similar?**

and

> **What is actually connected?**

The dots keep the same sonic positions while the **Connections** selector changes which relationships are drawn between them.

## 1. The sonic landscape

A mapped dot represents a local track with cached Flow analysis.

Its position is derived locally from:

- energy;
- tempo;
- spectral centroid / brightness;
- rhythmic density;
- tonal position and mode;
- intro/outro mixability.

Nearby dots therefore have similar combinations of those Flow features.

This is an explainable projection of Melodex's current analysis features, not a claim that musical similarity has one objectively correct geometry.

## 2. Sounds similar

Choose:

**Connections → Sounds similar · Flow**

Melodex draws local nearest-neighbour edges in the Flow feature space.

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

The **Colour** selector changes the dots:

- Sonic colour
- Energy
- Taste
- Rediscovery

The **Connections** selector changes the edges.

For example:

```text
Colour: Rediscovery
Connections: Production
```

shows which tracks may be ready to return while simultaneously revealing common production links.

That separation is intentional.

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

Select a track and choose:

**Start journey here**

The selected mapped track becomes the starting anchor for Mind + Flow.

This closes the loop:

```text
see a region
    ↓
inspect its sonic / factual relationships
    ↓
choose a track
    ↓
Start journey here
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
