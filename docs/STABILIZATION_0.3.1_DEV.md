# v0.3.1.dev0 Stabilization Audit

This branch is a stabilization pass over the full v0.3.1.dev0 feature stack after packaged-app testing.

## Confirmed packaged-app issue

Python providers/extensions were launched with `sys.executable`.

In a source checkout this is the Python interpreter. In a PyInstaller app it is the Melodex executable itself, so starting a plugin could relaunch the Melodex GUI.

The packaged app now has a dedicated Python child-worker mode and a separate single-instance GUI guard.

## Reliability hardening

The audit also covers:

- bounded provider JSON-RPC calls;
- child stdout/stderr draining;
- timeout/process cleanup;
- registry-cache isolation by registry URL;
- external playback host validation;
- staged/atomic plugin package installation;
- archive traversal/symlink/duplicate/size checks.

## Ecosystem audit

The first-party example ecosystem was reviewed with deterministic fixtures and adversarial response tests.

Audited implementations include:

- Radio Browser;
- LibriVox;
- Openverse Audio;
- Last.fm Recommendations;
- MusicBrainz Enrichment;
- MusicBrainz Song Connections;
- ListenBrainz Tags;
- ListenBrainz Community Pulse;
- Wikimedia Artwork;
- Wikimedia Liner Notes;
- Cover Art Archive;
- Sonic Neighbours;
- Bridge Builder;
- Forgotten Favourites;
- Public Domain Lyrics.

Source fixes that changed package bytes were rebuilt as patch-version packages with updated registry SHA-256, sizes and review events.

## Personal testing priority

On macOS Apple Silicon, verify these first:

1. opening Melodex twice raises the existing window instead of creating a second GUI;
2. opening Sources / testing plugins does not create another Melodex window;
3. plugin health checks return or time out rather than loading forever;
4. update the audited Gallery/Directory plugins when an update is shown;
5. search/playback for Radio Browser, Openverse and LibriVox;
6. MusicBrainz/Wikimedia/ListenBrainz enrichment from Now Playing;
7. Music Map / Pathfinder / Journey workflows after plugins have been exercised.

Report the exact action, plugin/source name and visible error text for any remaining failure.

## Additional regression gates

- Windowed macOS and Windows builds now launch a bundled child worker and exchange a JSON-RPC request over inherited pipes.
- Desktop CI tests Python 3.11 and 3.12 and compiles the bundled ecosystem examples.
- A separate-process test checks that a second launch activates the existing instance and exits.
- Package checks reject unsafe IDs, portable path collisions and oversized extracted data.
- Playback drops authorization and cookie headers when a redirect changes origin.
