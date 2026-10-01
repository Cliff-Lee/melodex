# Next release — draft notes

**Development after Melodex v0.7.0.**

Use this file for changes intended for the next release after v0.7.0. Stable v0.7.0 notes are in [v0.7.0.md](v0.7.0.md).

See [Releasing Melodex](../RELEASING.md) for the release process.

## v0.7.1 development

### Artist browsing

- Artist cards now reserve imagery for **real artist portraits** rather than reusing album covers as if they were artist photographs.
- **Get artist photos** is the explicit enrichment action in Artists.
- Portrait lookup can conservatively resolve an artist name through MusicBrainz before following Wikidata/Wikimedia image metadata.
- Lookup now falls through Wikidata portrait → linked free Wikipedia lead image → conservative Wikipedia artist-page search → installed artwork portrait plugins → conservative Wikimedia Commons artist search.
- One click processes the complete missing-artist list in small background batches rather than stopping after the first batch.
- Album covers/logos and ambiguous artist/image matches are rejected rather than guessed.
- Artist cards now offer **Photo…** as a manual fallback; the selected local image is copied into Melodex's artwork cache and remembered for that artist.

### Plugin usability

- Installed plugins now expose a direct **Use plugin/source** action.
- Provider plugins open Search already filtered to that provider.
- Local recommendation plugins open Tune your listening.
- Artwork plugins route to My Music.
- Lyrics/context/metadata/identity extensions route to Now Playing, where their enrichment is used automatically.
- Plugin Directory now has its own **Use plugin/source** button after installation/configuration.

### Public provider boundary

- Legacy private development providers are quarantined when found in an old local data folder and are not loaded, searched or played.
- Manual attempts to install those legacy development adapters into a public build are rejected.
- The public bundled provider payload remains restricted to the six audited bundled providers.


### Artwork lookup reliability

- **Get artist photos** now advances one artist at a time, so progress updates after every lookup instead of waiting for a large batch.
- A failed artist lookup no longer strands the full pass; Melodex skips it and continues.
- **Find missing artwork** now traverses the complete set of missing album covers rather than stopping after 12.
- Album-cover progress is visible on the action button and advances after each album.
- Artist and album enrichment passes cannot run simultaneously, avoiding competing metadata/network crawls.
- Unexpected worker errors now return control to the queue so the next item can continue.


### Plugin Centre and lyrics audit

- Sources & plugins is regrouped into built-in connections, sources included with Melodex, separately installed music plugins and installed enhancements.
- Source/plugin cards now use native feature icons and origin badges instead of anonymous initial tiles.
- Added **Check installed** to run bounded health checks across installed plugin packages on the current machine.
- The registry window is redesigned as **Plugin Centre**, with visual cards, plain-language capabilities/permissions and technical package details hidden behind progressive disclosure.
- Reference/example plugins are labeled as such, and overlapping examples (such as Radio Browser/LibriVox) explain that equivalent functionality already ships with Melodex.
- Lyrics now support persistent user-imported/pasted text and LRC without rewriting source audio files.
- Local lyric discovery recognises common title and artist-title sidecar names and a `Lyrics/` subfolder.
- The Lyrics tab adds **Add lyrics file…**, **Paste lyrics…** and **Find lyrics plugin…**.
- The empty Lyrics state now explains that Core checks local/user lyrics and installed lyrics extensions but does not scrape commercial lyrics sites.
