# Next release — draft notes

**Planned target: Melodex v0.6.1. This release has not been tagged or published.** The latest downloadable release is [v0.6.0](v0.6.0.md).

The release summary will be updated as changes are selected and verified. These notes are a development placeholder, not release notes or a record of tested binaries.

See [Releasing Melodex](../RELEASING.md) for the release process.

## Album Wall

- Added a first-class **Album wall** desktop view for browsing local collections spatially by album artwork.
- Added **Sound**, **Familiarity**, **Time**, and deterministic **A–Z shelves** lenses.
- Sound placement reuses cached Flow analysis at album level; unanalysed albums remain visible at stable fallback positions.
- Added semantic zoom, search, Fit wall, Now playing centring, album playback/queueing, and lazy local/embedded artwork hydration.
- Expanded local tag indexing with album artist, date/year, genre, track number and disc number.
- Added an edge-free Music Map projection path so Album Wall can reuse the Flow projection efficiently without constructing track-neighbour edges.

See [Album Wall](../ALBUM_WALL.md).

## Desktop UX redesign

- Reorganised the desktop around listener goals rather than implementation modules: **Home**, **My Music**, **Explore**, **Journeys**, **Playlists**, and **Sources & plugins**.
- Added progressive disclosure: everyday actions stay visible while provider diagnostics, routing internals and other expert controls move behind persistent **Power tools**.
- Rebuilt **My Music** as an album-first visual library with artwork, Albums/Artists/Tracks views, search, hover actions and instructional empty states.
- Reworked **Home** around listening intentions: Play something, Comfort, Explore, Rediscover, Continue listening and visual exploration entry points.
- Made the persistent player the route into **Now Playing**, added cover artwork there, and changed Now Playing to lead with artwork/details before optional visualisations.
- Added an **Explore** hub for Search, Album Wall and Music Map rather than requiring new users to understand those tools independently.
- Simplified Sources into friendly status cards and one contextual setup action, while preserving install/remove/priority/bridge/diagnostic controls for power users.
- Added contextual help tooltips, a Ctrl/Cmd+K command palette, clearer empty-state guidance, and listener-language labels for advanced listening controls.
- Added offscreen Qt smoke tests for the redesigned shell and visual Library.

See [UX redesign](../UX_REDESIGN.md).
