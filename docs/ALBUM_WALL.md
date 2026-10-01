# Album Wall

Album Wall is a visual, local-first way to browse a Melodex collection as a place rather than a scrolling list.

Open **Album wall** from the desktop sidebar. Each album appears once as a cover tile. Drag the wall to explore it, use the mouse wheel to zoom, search by artist or album, and double-click a cover to play the album in track order.

## Lenses

The same collection can be rearranged without changing the underlying library:

- **Sound** — albums are placed near records whose analysed tracks have similar Flow audio characteristics. An album's position is the centroid of its analysed tracks.
- **Familiarity** — moves more familiar records across a familiar-to-less-familiar axis while retaining a second sonic dimension.
- **Time** — places dated albums along a release-year axis while retaining a second sonic dimension.
- **A–Z shelves** — a deterministic artist/album layout for conventional browsing.

Changing lenses rearranges the same album objects rather than opening a separate browser.

## Stable spatial memory

Album Wall deliberately avoids a recommendation-feed model. For a given library and analysis state, positions are deterministic. The intent is that users can gradually learn where music lives.

When Flow analysis is unavailable or an album has not yet been analysed, that album still appears at a deterministic fallback position. It does not disappear from the wall. Running **Analyse my library** progressively turns those fallback locations into sonic neighbourhoods.

The layout also packs album tiles into nearby free cells. This keeps semantic position meaningful while preventing hundreds of covers from being drawn directly on top of one another.

## Artwork and performance

Opening Album Wall does not trigger a large batch of internet artwork requests.

Visible albums request artwork lazily, in small batches. The initial implementation looks only for:

1. an explicitly supplied local artwork path;
2. common sidecar files such as 'cover.jpg', 'folder.png', or 'front.webp';
3. artwork embedded in the representative local audio file.

If none exists, Melodex renders a deterministic generated record-cover placeholder. Panning to another part of the wall hydrates that area on demand.

The wall currently displays at most 1,200 albums at once. Very large libraries preserve important analysed/familiar/rediscovery records plus a deterministic breadth sample.

## Interaction

- **Drag** — pan around the collection.
- **Wheel** — semantic zoom. At low zoom the wall is primarily artwork; labels appear as you move closer.
- **Find** — search artist or album and centre it.
- **Now playing** — return to the album containing the current local track.
- **Fit wall** — show the whole collection.
- **Single click** — select an album.
- **Double click** — play the album.
- **Play album / Queue album** — explicit controls above the wall.

The currently playing album gets a distinct outline so it remains visible while exploring elsewhere.

## Relationship to Music Map

Music Map is track-level and is designed for sonic/knowledge relationships, pathfinding, and journey design.

Album Wall is album-level and optimised for visual browsing and spatial memory. It reuses the cached Flow projection rather than maintaining a separate recommendation model.

This distinction is intentional:

    Music Map   → understand connections between tracks
    Album Wall  → inhabit and browse a collection of records

## Current scope

The first implementation establishes the spatial album browser, lenses, semantic zoom, playback/queue integration, current-album highlighting, stable fallback positions, and lazy local artwork.

Potential later extensions include drawing a route across albums to create a Flow journey, pinning personal album locations, saved wall viewpoints, artist stacks, visual rediscovery dust, and shareable Atlas layouts. Those are not part of the current implementation.
