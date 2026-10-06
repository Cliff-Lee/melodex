# Album Wall

Album Wall is a visual, local-first way to browse a Melodex collection as a place rather than a scrolling list.

Open **Album Wall** from Explore. Each album appears once as a cover tile. The wall opens near a readable sleeve size rather than shrinking the whole collection into one overview. Drag with the mouse or use two-finger trackpad scrolling to pan around the collection; double-click a cover to play the album in disc and track order. At the normal browsing scale the wall keeps to covers, revealing album names on hover, selection, or closer zoom to keep dense collections readable.

For local libraries, a release folder is the primary album boundary, so separate editions of the same artist/title remain separate tiles. Common multi-disc folders such as `CD1` and `Disc 2` are folded back into their parent album.

## Lenses

The same collection can be rearranged without changing the underlying library:

- **Sound** — albums are placed near records whose analysed tracks have similar Flow audio characteristics. An album's position is the centroid of its analysed tracks.
- **Familiarity** — moves more familiar records across a familiar-to-less-familiar axis while retaining a second sonic dimension.
- **Time** — places dated albums along a release-year axis while retaining a second sonic dimension.
- **A–Z shelves** — a deterministic artist/album layout for conventional browsing.

Changing lenses rearranges the same album objects rather than opening a separate browser.

## Stable spatial memory

Album Wall deliberately avoids a recommendation-feed model. For a given library and analysis state, positions are deterministic. The intent is that users can gradually learn where music lives.

When Flow analysis is unavailable or an album has not yet been analysed, that album still appears at a deterministic fallback position. It does not disappear from the wall. Using **Wall options → Improve sonic layout** progressively turns those fallback locations into sonic neighbourhoods.

The layout also packs album tiles into nearby free cells. This keeps semantic position meaningful while preventing hundreds of covers from being drawn directly on top of one another.

## Artwork and performance

Opening Album Wall does not trigger a large batch of internet artwork requests.

Visible albums request artwork lazily, in small batches. The initial implementation looks only for:

1. an explicitly supplied local artwork path;
2. common sidecar files such as 'cover.jpg', 'folder.png', or 'front.webp';
3. artwork embedded in the representative local audio file.

If none exists, Melodex renders a deterministic generated record-cover placeholder. Panning to another part of the wall hydrates that area on demand.

The wall currently displays at most 1,200 albums at once. Very large libraries preserve important analysed/familiar/rediscovery records plus a deterministic breadth sample. Covers already loaded stay resident while the model refreshes or the viewport moves; remaining local covers are prepared in low-priority background batches. Labels stay out of the way at the normal scale and appear on hover, selection, or close zoom.

## Interaction

The wall is designed to feel like a large canvas rather than a tiny diagram.

- **Drag** — pan around the collection.
- **Two-finger trackpad scroll** — pan naturally in both directions.
- **Mouse wheel** — zoom smoothly around the pointer.
- **Cmd/Ctrl + trackpad scroll** — zoom on trackpads without turning ordinary two-finger navigation into accidental zoom.
- **Find** — search artist or album and centre it.
- **Now playing** — return to the album containing the current local track.
- **Actual size** — return to the normal sleeve-browsing scale.
- **Overview** — temporarily fit the whole collection when you want orientation.
- **Single click** — select an album and reveal its details.
- **Double click** — play the album.
- **Play selected / Queue selected** — explicit playback controls above the wall.

Album Wall intentionally does **not** fit the entire collection on every open. An overview is useful for orientation, but it makes real album covers too small for ordinary browsing.

The currently playing album gets a distinct outline so it remains visible while exploring elsewhere.

## Relationship to Music Map

Music Map is track-level and is designed for sonic/knowledge relationships, pathfinding, and journey design.

Album Wall is album-level and optimised for visual browsing and spatial memory. It reuses the cached Flow projection rather than maintaining a separate recommendation model.

This distinction is intentional:

    Music Map   → understand connections between tracks
    Album Wall  → inhabit and browse a collection of records

## Progressive disclosure

Ordinary browsing keeps only the lens, search, navigation and selected-album playback controls visible. **Wall options…** reveals the less-frequent actions—rebuild, sonic analysis and missing-cover recovery—without permanently reducing the canvas.

Global **Power tools** does not force this panel open.

## Current scope

The current implementation provides the spatial album browser, lenses, smooth bounded zoom, trackpad/mouse panning, playback/queue integration, current-album highlighting, stable fallback positions, and lazy local artwork.

Potential later extensions include drawing a route across albums to create a Flow journey, pinning personal album locations, saved wall viewpoints, artist stacks, visual rediscovery dust, and shareable Atlas layouts. Those are not part of the current implementation.
