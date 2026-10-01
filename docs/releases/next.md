# Next release — draft notes

**Development after Melodex v0.7.0.**

Use this file for changes intended for the next release after v0.7.0. Stable v0.7.0 notes are in [v0.7.0.md](v0.7.0.md).

See [Releasing Melodex](../RELEASING.md) for the release process.

## v0.7.1 development

### Artist browsing

- Artist cards now reserve imagery for **real artist portraits** rather than reusing album covers as if they were artist photographs.
- **Get artist photos** is the explicit enrichment action in Artists.
- Portrait lookup can conservatively resolve an artist name through MusicBrainz before following Wikidata/Wikimedia image metadata.
- Ambiguous artist-name matches are rejected rather than guessed.

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

