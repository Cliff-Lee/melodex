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

## P9b — shell-first window construction

P9a established the first baseline on the Linux CI runner:

- fresh profile: about **2.54 s** to the first event-loop turn;
- warm profile: about **490 ms**;
- warm profile with a cached 12,700-track library: about **535 ms**;
- the 12,700-track cache therefore added only about **45 ms** over the warm profile.

The dominant warm-start phase was not the library. Importing the MainWindow dependency
graph cost about **238 ms**, while constructing the complete UI cost about **55 ms**.
On the fresh process the same import graph cost about **1.84 s** because Python and Qt
modules were cold.

P9b changes startup from "build every page, then show Home" to **shell first**.

The Home/navigation/player surfaces still exist immediately. Four heavyweight pages now
start as tiny placeholders:

- My Music;
- Now Playing / visualisations;
- Album Wall; and
- Music Map.

On first navigation Melodex switches to the lightweight destination shell immediately,
lets Qt paint one frame, and only then imports and constructs that page. Subsequent
visits reuse the same widget tree.

Page-specific Python modules are also no longer top-level MainWindow imports. In
particular the library browser, Rich Now Playing, Living Canvas, Album Wall, Music Map,
their projection/model helpers, visualisation models and plugin-directory UI remain
unloaded until their feature is actually used.

The first construction time for each heavy page is recorded in
`lazy_page_build_metrics` for regression tests and future diagnostics.

Regression coverage verifies both halves of the contract:

- heavyweight page modules must not reappear as top-level imports; and
- a heavy page is absent at startup, shows its shell first, builds after the shell frame,
  and is constructed only once.

## P9c — warm-cache service startup

P9b moved the warm profile to about **334 ms** and the 12,700-track cached profile to
about **416 ms** on the Linux CI runner. The remaining large-library startup premium was
about **83 ms**, concentrated in ProviderManager/cache restoration rather than UI work.

P9c changes the warm-cache path so Home does not eagerly materialise data it does not
need.

### Deferred local catalog hydration

At startup Melodex now reads the persistent library index summary only. Home gets its
track count from SQLite without JSON-decoding every cached track.

For a large cached library:

- the 12,700 metadata rows remain on disk while Home appears;
- the local provider holds a one-shot cache loader;
- the first feature that actually needs the catalog (My Music, search, Play Something,
  local intelligence, etc.) hydrates it automatically;
- direct LocalFilesProvider search/browse/resolve APIs preserve their normal behaviour;
  and
- the in-memory catalog is loaded only once.

Changing configured roots explicitly discards any old deferred loader so a stale startup
snapshot cannot reappear after the user selects new folders.

### Warm SQLite fast path

The library-index schema now records its schema version in SQLite
`PRAGMA user_version`. Once an index is current, later launches skip repeated
`CREATE TABLE`, index creation and schema-version writes.

Configured roots are also compared with the existing root table before synchronisation,
so an unchanged warm launch performs no root-table writes.

### Plugins stay cold until used

The plugin registry is no longer constructed during ProviderManager startup. Importing
the registry client also imports its HTTP stack, so the registry now remains absent until
the user opens/uses registry-backed plugin features.

OS keyring discovery is similarly deferred. Provider and extension configuration can
install one-shot configuration loaders; secret values are resolved only immediately
before that external provider/extension is first called. Explicit configuration changes
still apply immediately.

Bundled provider archive manifests are cached after their first parse within a process,
avoiding repeated zip reads during startup bookkeeping.

### Measurement

P9c adds ProviderManager sub-phases to the existing startup timeline:

- settings/config files ready;
- bundled providers ready;
- local index summary ready;
- installed providers ready;
- capability extensions ready; and
- ProviderManager ready.

The same fresh/warm/12.7k startup artifact therefore shows both the end-to-end gain and
which provider/cache stage remains dominant.

Regression tests ensure the large cached catalog is not hydrated by construction or by
Home's count, the OS secret store stays uninitialised during cached-status work, and the
plugin registry remains lazy.

## Planned P9 sequence

## P9d — first-run and cold-profile startup

P9c made library size almost irrelevant to startup: in the same CI run a cached
12,700-track profile was only about **6.4 ms** slower than the warm empty profile.
The remaining startup problem is therefore the genuinely cold process/profile path.

The P9c fresh-profile trace showed the main-window import graph dominating first launch
on that runner: roughly **2.07 s** for the cold import phase versus roughly **0.31 s**
after the Python/module/file-system caches were warm. ProviderManager's own measured
sub-phases were comparatively small.

P9d therefore changes the import boundary rather than adding more SQLite tuning.

### NumPy only when audio analysis starts

Flow no longer imports NumPy merely to render Home or report whether deep analysis is
available. Startup checks module availability cheaply; the actual NumPy module is loaded
only immediately before uncached audio analysis.

Cached Flow lookups, transition rules and Home's "analysis available" status stay usable
without paying NumPy's import cost.

### Optional services only when first used

MainWindow no longer constructs these services during every cold launch:

- Mind session planning;
- local-intelligence snapshots;
- Music Knowledge storage/graph enrichment;
- metadata/network enrichment; and
- the optional LLM client.

They are exposed through lazy properties and preserve their existing call sites. A
fresh Home screen therefore constructs only services required for the first screen and
playback. Shutdown closes a lazy service only if it was actually created.

### Feature modules stay behind their feature boundary

Cold Home startup no longer imports Journey routing/replay/recipe modules, Music Map
knowledge graph helpers, playlist parsers, plugin setup dialogs/onboarding helpers,
diagnostics export code or the library scan process. Those imports now live in the
methods that actually invoke each feature.

The playback gateway also leaves the Requests HTTP stack cold while Melodex is only
playing local files. Requests is imported on the first remote/gateway playback request.

Regression tests parse MainWindow's top-level import graph and fail if those optional
features creep back onto startup. A subprocess regression also verifies that importing
`melodex.flow` does not import NumPy.

### Measurement

P9d now reports four launch shapes instead of conflating two different kinds of
"cold":

1. **OS-cold + profile-cold** — the first process in the CI job and a brand-new data
   directory. This is closest to a literal first-ever launch but is highly sensitive to
   hosted-runner filesystem cache noise.
2. **Warm** — the second launch of the same profile.
3. **Profile-cold after code warm-up** — a brand-new data directory after Python/Qt
   code pages have already been read. This isolates Melodex's one-time profile setup.
4. **12.7k cached** — the large-library warm-cache case retained from P9c.

The profile-cold-versus-warm delta is the useful P9d engineering signal. The literal
OS-cold result is still retained as an end-user worst-case observation, but it is not
used by itself to judge a code change because runner disk-cache variance can be larger
than the code change.

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
