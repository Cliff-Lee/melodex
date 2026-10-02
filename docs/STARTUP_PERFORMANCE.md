# Startup performance

P9 follows the P8 large-library fluidity campaign. P8 made Melodex remain responsive
after the application is running; P9 focuses on how quickly the application becomes
visible and usable in the first place.

## Startup contract

Startup is measured from Python process entry to the first Qt event-loop turn after the
main window has been shown.

The trace contains timing labels only. It must not contain:

- local paths;
- track, album or artist names;
- provider credentials or URLs;
- plugin configuration values; or
- listening-history content.

P9 distinguishes three profiles:

1. **Fresh profile** — a new Melodex data directory. This includes first-run persistent
   stores and bundled-provider setup.
2. **Warm profile** — a second launch using the same profile.
3. **Large cached profile** — an already-initialised profile with a persistent
   12,700-track local-library index. No audio files are opened or copied.

The CI artifact records both wall-clock process duration and internal phase timings.

## P9a — startup baseline and phase instrumentation

P9a records:

- application-module and Qt application setup;
- single-instance acquisition;
- heavy MainWindow import time;
- ProviderManager construction and persistent library loading;
- user-state/database construction;
- Flow, metadata and other core-service construction;
- playback construction;
- full UI construction;
- Home population;
- local bridge startup;
- MainWindow construction completion;
- show request; and
- first event-loop turn.

The MainWindow import is also deferred until after the single-instance guard. A
secondary launch can therefore activate an existing Melodex window and exit without
importing the full desktop UI, provider, analysis and visualisation graph.

The baseline intentionally does not impose an arbitrary absolute startup budget yet.
The point of P9a is to establish which phases dominate on the CI runner and how much a
12,700-track cached library changes startup.

## Planned P9 sequence

### P9b — shell-first window construction

Build only the visible Home/player/navigation shell before first paint. Move expensive
page widgets such as Music Map, Album Wall, Now Playing visualisations, plugin directory
surfaces and other non-visible pages behind lazy construction.

Success criterion: first usable shell no longer waits for pages the user has not opened.

### P9c — warm-cache service startup

Optimise ProviderManager, bundled-provider discovery, plugin registry/configuration,
SQLite opening and cached-library restoration using the P9a phase data.

Success criterion: the common subsequent-launch path does only the work required for
the initial screen and local playback readiness.

### P9d — first-run and cold-profile work

Separate one-time setup from every-launch work. Keep bundled-provider installation,
migration and other cold-profile tasks visible and safe without making all future
launches pay their cost.

### P9e — packaged-app startup regression gate

Measure packaged macOS, Windows and Linux builds where feasible, retain startup JSON
artifacts, and add regression thresholds only after enough stable measurements exist.

## Why this is separate from P8

A program can be fluid after opening but still feel slow if it spends seconds
constructing hidden pages, loading plugins or restoring caches before showing a window.

P8's rule remains:

> Slow work is allowed. Frozen UI is not.

P9 adds a startup version:

> Work that is not needed for the first screen should not delay the first screen.
