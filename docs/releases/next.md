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
