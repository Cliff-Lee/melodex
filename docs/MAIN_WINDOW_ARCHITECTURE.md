# P12c6 — MainWindow Residual Architecture Audit

## Purpose

P12c6 is an audit-only stage. It measures the architecture that remains after
P12c1–P12c5 and decides whether `MainWindow` is ready to stop decomposing.

This stage deliberately does **not** chase line-count reduction. The question is
whether `MainWindow` now behaves primarily as a top-level composition and
coordination shell, or whether substantial feature/page responsibilities still
live inside it.

## Baseline

Audit baseline:

- branch: `codex/p12c5-source-policy-controller-2026-10-03`
- commit: `0a9d0bcab92ecb491a1700492b61e0fa93e3116a`
- P12c5 PR: #178
- P12c5 mergeable at audit start
- P12c5 Tests workflow: green
- Python 3.11: green
- Python 3.12: green
- Code health guardrails: green
- Fluid Melodex release gates: green
- Fluid soak (12.7k): green
- Large-library baseline (12.7k): green
- Elastic-library qualification (12.7k): green
- NAS fault qualification: green
- Startup baseline: green
- desktop package build: green
- Linux package build: green

Measured `desktop/melodex/main_window.py`:

- Campaign 12 baseline: **7,629 physical lines**
- current: **7,163 physical lines**
- reduction: **466 lines / about 6.1%**
- `MainWindow` methods: **248**
- methods spanning more than about 50 lines: **31**
- methods spanning more than about 100 lines: **9**
- distinct internal Melodex modules referenced: **39**
- in-method relative imports: **51**
- current structural guardrail: `main_window.py <= 7,163`

The in-method imports must not be treated as style debt automatically. Several
were introduced deliberately to keep cold-start imports small. Any future page
or controller extraction must preserve that startup behavior.

Already extracted during P12c:

- scan worker lifecycle → `LibraryScanController`
- scan presentation calculations → `library_scan_status.py`
- queue mutation boundary → `FlowPlayer`
- navigation/lazy-page lifecycle → `NavigationController`
- source/plugin decision policy → `SourcePolicyController`

## Audit result

**Recommendation: continue P12c.**

The remaining window is not yet primarily a composition shell.

The strongest evidence is not the 7,163-line size by itself. It is that the
window still contains multiple coherent feature subsystems with their own state
machines, large page builders, domain decisions, persistence interactions and
async workflows.

The remaining architecture has four especially clear unresolved boundaries:

1. Sources/plugins still form a roughly thousand-line vertical slice in the
   window even after pure policy was extracted.
2. Music Map/Journeys still own the largest feature-specific state machine and
   roughly 1,400+ method-lines under journey/music-prefixed behavior.
3. Playback/Now Playing still mixes session state, visual enrichment, taste,
   resolver, prefetch and page UI around the otherwise well-contained player.
4. Library presentation still combines scan completion, provider snapshot
   application, metadata correction, artwork/artist enrichment and page UI.

Moving directly to P12d would leave Campaign 12's largest architectural problem
only partially addressed.

---

## Measurement notes

The responsibility table below uses contiguous source regions because
`main_window.py` is already broadly grouped by feature. "Approx lines" includes
comments and spacing inside the region and should not be interpreted as exact
executable LOC.

Method spans are measured from one class-level method definition to the next.
They are useful for locating hotspots, not as a complexity score.

## Responsibility map

| Responsibility | Approx lines | Methods | Largest method | Qt coupled? | Domain logic? | State owned? | Suggested owner |
|---|---:|---:|---|---|---|---|---|
| Composition / lazy services | 199 | 7 | `__init__` — 140 | Partial | Low–medium | App services, lazy services | `MainWindow` + eventual app/service context |
| Global shell / layout | 859 | 5 | `_build_ui` — 813 | Yes | Low | Sidebar, queue panel, activity strip, player bar, shortcuts | App shell / small persistent UI components |
| Page construction | 1,284 | 22 | `_build_sources` — 250 | Yes | Mixed | Most page widgets | Independent page components |
| Window / Home / Explore behavior | 170 | 11 | `_show_home` — 39 | Yes | Low–medium | Home/explore presentation state | Home/Explore pages |
| Sources page refresh / routing | 386 | 7 | `_refresh_sources` — 253 | Yes | Medium | Source page rendering/selection | Sources vertical slice |
| Library presentation / metadata / artwork | 420 | 13 | `_library_online_artwork_requested` — 100 | Yes | Yes | Library UI enrichment state | Library page/controller |
| Journey recipes / history | 356 | 12 | `_apply_pending_journey_replay` — 54 | Partial | Yes | Recipe/replay state | Journey workspace controller |
| Playlists / moments / taste | 202 | 13 | `_open_ai_playlist_import` — 69 | Yes | Medium | Page selection/import state | Playlist/Moments pages |
| Library scan UI integration | 289 | 9 | `_local_scan_done` — 109 | Yes | Medium | Scan presentation/session state | Library controller + existing scan controller |
| Plugin / source / stream management | 532 | 22 | `_user_streams_dialog` — 100 | Yes | Yes | Plugin health/install/config UI state | Sources page + source-management controller |
| Search / local intelligence | 349 | 19 | `_show_search_report` — 73 | Yes | Yes | Search sequences/results | Discover/Recommendation controller |
| Album Wall / Music Map / journey orchestration | 1,067 | 58 | `_journey_live_apply_result` — 86 | Mixed | High | Large journey/music state machine | Journey/Music workspace |
| Playback / Now Playing / taste / resolution | 563 | 32 | `_on_track_changed` — 87 | Mixed | High | Session/visual/taste state | PlaybackSessionController + NowPlaying page |
| LLM / bridge / external control | 282 | 15 | `_translate_lyrics` — 62 | Mixed | Medium | Bridge/command state | Feature controllers + small external-control boundary |
| Async / window lifecycle | 109 | 3 | `_run_async` — 79 | Partial | Low | Global async generation/cancellation | Shared async coordinator / MainWindow lifecycle |

The largest areas are not random utility clutter. They correspond to real
application capabilities, which is why further extraction should remain
vertical and responsibility-led.

---

## Largest remaining methods

| Rank | Method | Start line | Approx span |
|---:|---|---:|---:|
| 1 | `_build_ui` | 296 | 813 |
| 2 | `_refresh_sources` | 2609 | 253 |
| 3 | `_build_sources` | 2189 | 250 |
| 4 | `_build_music_map` | 1690 | 249 |
| 5 | `__init__` | 156 | 140 |
| 6 | `_build_for_you` | 1324 | 130 |
| 7 | `_build_home` | 1155 | 129 |
| 8 | `_build_journeys` | 1972 | 109 |
| 9 | `_local_scan_done` | 4119 | 109 |
| 10 | `_library_online_artwork_requested` | 3175 | 100 |
| 11 | `_user_streams_dialog` | 4694 | 100 |
| 12 | `_on_track_changed` | 6314 | 87 |
| 13 | `_journey_live_apply_result` | 6035 | 86 |
| 14 | `_library_artist_images_requested` | 3332 | 83 |
| 15 | `_run_async` | 7063 | 79 |
| 16 | `_test_all_plugins` | 4442 | 75 |
| 17 | `_show_search_report` | 4907 | 73 |
| 18 | `_edit_local_metadata` | 3035 | 72 |
| 19 | `_build_explore` | 1545 | 71 |
| 20 | `_open_ai_playlist_import` | 3835 | 69 |

### Interpretation

The top four are especially informative:

- `_build_ui` is still a hidden UI monolith.
- `_build_sources` and `_refresh_sources` show that Sources is already a
  natural page/controller boundary.
- `_build_music_map` is not merely layout; it wires a large interactive
  journey subsystem whose state and behavior continue for hundreds of lines
  elsewhere in the class.

---

## UI construction audit

### Global shell

`_build_ui` remains **813 lines**.

Inside that one method it creates and wires at least:

- primary sidebar/navigation
- Power tools toggle
- top-level page stack
- contextual queue panel
- background scan/activity strip
- persistent player bar
- previous/play/next controls
- now-playing cover/title/meta
- seek control
- Keep/Love controls
- player power actions
- command-palette shortcuts
- global styling

The method assigns at least 22 long-lived instance attributes and contains at
least 21 signal connections.

This is legitimate top-level UI territory, but the method is too large to be a
healthy composition root. It currently combines composition with component
implementation.

### Page construction

The page-construction region is about **1,284 lines**.

Important page builders:

| Builder | Span | Long-lived attributes | Signal connections | Natural standalone component? |
|---|---:|---:|---:|---|
| `_build_home` | 129 | 12 | 9 | Yes |
| `_build_now_playing` | 40 | 3 | 13 | Yes; already wraps strong widgets |
| `_build_for_you` | 130 | 6 | 10 | Yes |
| `_build_discover` | 49 | 6 | 6 | Yes |
| `_build_library` | 42 | 2 | 18 | Yes; `LibraryBrowser` already exists |
| `_build_explore` | 71 | 5 | 6 | Probably |
| `_build_album_wall` | 68 | 5 | 10 | Yes; `AlbumWallWidget` already exists |
| `_build_music_map` | 249 | 16 | 35 | Strong yes |
| `_build_journeys` | 109 | 7 | 12 | Strong yes |
| `_build_playlists` | 54 | 4 | 7 | Yes |
| `_build_moments` | 26 | 3 | 2 | Yes, but lower priority |
| `_build_ask` | 5 | 2 | 1 | Too small to prioritize alone |
| `_build_sources` | 250 | 10 | 22 | Strong yes |

Page extraction should not mean "move the builder into another file and keep
all callbacks in `MainWindow`". The valuable boundary is a page owning its
widgets and page-local interaction state, exposing a small signal/callback
interface to application-level coordination.

---

## Feature-cluster measurements

Method-name clustering provides another view of the remaining architecture.
These clusters overlap conceptually, so they are evidence rather than additive
LOC accounting.

| Cluster | Methods | Approx method-lines | Largest examples |
|---|---:|---:|---|
| Sources/plugins | 28 | ~1,048 | `_refresh_sources`, `_build_sources`, `_user_streams_dialog`, `_test_all_plugins` |
| Music Map/Journeys | 58 | ~1,484 | `_build_music_map`, `_build_journeys`, live journey methods |
| Library | 25 | ~702 | scan completion, artwork, artist images, library page |
| Playback/Now Playing | 47 | ~879 | track change, visual context, prefetch, taste, lyrics/resolver |
| Search/intelligence | 17 | ~514 | For You, Discover, search and local intelligence |
| Playlists/moments | 16 | ~297 | playlist builder/import/export and moments |

This confirms that the remaining class is still a collection of feature
controllers rather than a thin application shell.

---

## MainWindow-owned state

### Application composition — mostly appropriate

Current composition-root state includes:

- `data_dir`
- `providers`
- `source_policy`
- `state`
- `motion`
- `flow`
- `player`
- `local_scan`
- `navigation`
- `background_scheduler`
- `responsiveness`
- `bridge`
- lazy services:
  - `_mind`
  - `_local_intelligence`
  - `_knowledge`
  - `_llm`
  - `_metadata`

Most of these are reasonable things for a composition root to construct or
wire. The issue is not that `MainWindow` knows these major services exist; it
is that page/feature behavior continues to operate them directly throughout the
class.

### Music Map / Journey state — should move

The window still stores a large, cohesive feature state block:

- `music_path_start_ref`
- `music_path_end_ref`
- `music_path_result`
- `music_journey_stages_data`
- `music_live_active`
- `music_live_route`
- `music_live_original_route`
- `music_live_destination_ref`
- `music_live_avoid_refs`
- `music_live_avoid_artists`
- `music_live_replanning`
- `music_live_run_id`
- `music_live_played_refs`
- `music_active_recipe_id`
- `music_active_recipe`
- `pending_journey_recipe`
- `pending_journey_replay`

In addition, the window owns many Music Map/Journey widgets:

- `music_map`
- `music_path_mode`
- `music_path_label`
- `music_path_steps`
- `music_map_journey_panel`
- `music_journey_preset`
- `music_journey_constraint`
- `music_journey_stages`
- `music_live_steering`
- `music_live_label`

This is the clearest case where `MainWindow` is acting as storage for another
subsystem.

### Playback / Now Playing state — should largely move

The player engine owns the audio queue, but `MainWindow` still owns playback
session/presentation state:

- `current_history_id`
- `current_track_started`
- `current_track`
- `_visual_position_ms`
- `_visual_duration_ms`
- `_visual_analysis_signals`
- `_visual_context_signals`
- `_visual_context_sequence`
- `_visual_neighbour_tracks`
- `_prefetched_track_assets`
- `_prefetch_sequence`
- `_prefetch_delay_ms`

And persistent/player widgets:

- `player_cover`
- `now_title`
- `now_meta`
- `seek`
- `keep_button`
- `love_button`
- `queue_panel`
- `queue_list`
- `rich_now`
- `living_canvas`

This state should not move into `FlowPlayer`; the audio engine should stay
focused. It suggests a separate playback-session / Now Playing boundary.

### Library / scan presentation state — split ownership

`LibraryScanController` correctly owns the disposable worker lifecycle, but
`MainWindow` still owns:

- `_local_scan_started_at`
- `_local_scan_last_progress`
- `_local_scan_session`
- background activity widgets/timer
- `library_browser`
- artwork enrichment presence
- metadata correction UI
- artwork and artist-image enrichment callbacks

That split is coherent enough for now, but the remaining fields naturally
belong in a future Library page/controller rather than back in
`LibraryScanController`.

### Sources / plugins — split ownership after P12c5

`SourcePolicyController` owns pure policy, but the window still owns:

- `_source_config_refresh_in_progress`
- `source_check_all`
- `sources_overview`
- `source_primary_button`
- `source_feature_picker`
- `source_feature_buttons`
- `sources_list`
- `source_hint`
- `source_welcome`
- `legacy_source_notice`
- `source_power_panel`
- source/plugin installation, removal, health and configuration workflows
- user stream dialogs

This is a deliberately incomplete vertical slice and should be completed rather
than left permanently split between policy and the window.

### Search / recommendation state — should move

The window still owns:

- `_search_sequence`
- `_search_pending_sequence`
- `_search_loading_delay_ms`
- `search_box`
- `search_source`
- `search_button`
- `search_status`
- `results`
- `intelligence_results`
- For You controls such as `mode`, `minutes`, `adventure`

This is a smaller but still coherent controller/page boundary.

### Global async state — potentially appropriate, but oversized implementation

Cross-cutting state includes:

- `_ui_callback_dispatcher`
- `_async_closing_event`
- `_async_generations`
- `_async_invalidations`
- `_async_stale_results_dropped`

A global async coordinator is appropriate infrastructure. The current
`_run_async` implementation is still 79 lines, so it may eventually deserve a
small reusable coordinator, but this is lower priority than feature boundaries.

---

## Dependency map

Current significant dependencies can be summarized as:

```text
MainWindow
├── composition / infrastructure
│   ├── ProviderManager
│   ├── UserState
│   ├── FlowEngine
│   ├── BackgroundScheduler
│   ├── UiResponsivenessMonitor
│   ├── MotionController
│   └── ProviderBridge
├── extracted boundaries
│   ├── NavigationController
│   ├── LibraryScanController
│   ├── SourcePolicyController
│   └── FlowPlayer
├── lazy services
│   ├── MindEngine
│   ├── LocalIntelligenceService
│   ├── MusicKnowledgeStore
│   ├── RichMetadataService
│   └── LLMClient
├── page widgets
│   ├── LibraryBrowser
│   ├── RichNowPlayingWidget
│   ├── LivingCanvasView
│   ├── AlbumWallWidget
│   └── MusicMapWidget
├── journey / map feature modules
│   ├── music_journey
│   ├── music_journey_live
│   ├── music_pathfinder
│   ├── journey_recipe
│   ├── journey_replay
│   ├── music_map_model
│   └── music_knowledge
├── source/plugin feature modules
│   ├── plugin_directory
│   ├── plugin_configuration_dialog
│   ├── plugin_onboarding
│   ├── plugin_health
│   └── diagnostics
├── content / playback feature modules
│   ├── metadata
│   ├── visualization_models
│   ├── playlist_io
│   └── llm_bridge
└── Qt widgets / dialogs / signals
```

### Appropriate dependencies for a composition root

These are reasonable for `MainWindow` or a nearby application composition
layer to know about:

- major controllers/services
- top-level page components
- player engine
- global responsiveness/motion infrastructure
- global background scheduler
- external-control bridge
- shutdown/lifecycle hooks

### Dependencies that indicate unresolved responsibility

These should largely disappear from `main_window.py` as vertical slices are
completed:

- `journey_recipe`
- `journey_replay`
- `music_journey`
- `music_journey_live`
- `music_pathfinder`
- `music_map_model`
- `plugin_configuration_dialog`
- `plugin_directory`
- `plugin_onboarding`
- `playlist_io`
- direct metadata/artwork enrichment helpers
- visualization-model builders

The presence of these modules is more informative than the raw dependency
count. They show that `MainWindow` is still executing feature internals.

---

## Completeness of P12c1–P12c5 boundaries

### LibraryScanController

**What it now owns**

- active disposable scan runner
- runner sequence identity
- pending rescan state
- scanned-root identity
- pause/resume
- cancellation
- shutdown
- worker signal bridging

**What remains in MainWindow**

- scan start UX
- scan progress presentation state
- background activity widgets
- completion/cancel/error user messaging
- provider snapshot application
- storage/NAS outcome presentation
- rescan scheduling into the UI

**Assessment**

The worker-lifecycle extraction is complete enough and should not absorb Qt UI.
The remaining scan behavior belongs with a future Library controller/page.

### FlowPlayer

**What it now owns**

- audio engine
- queue storage/mutation
- queue append/replace/jump APIs
- playback navigation
- seek/volume
- crossfade behavior

**What remains in MainWindow**

- current-track session state
- history/taste updates
- next-track prefetch
- Now Playing page state
- visual-analysis/context orchestration
- resolver UI
- lyrics translation
- player-bar widgets
- queue presentation

**Assessment**

Do not grow `FlowPlayer` into a UI/session god object. Add a
`PlaybackSessionController` / Now Playing boundary above it.

### NavigationController

**What it now owns**

- navigation generation
- stale callback rejection
- stale async-scope invalidation
- lazy-page builder state
- lazy-page timing metrics
- deferred population
- primary nav active-state policy

**What remains in MainWindow**

- `current_page`
- page registry/widgets
- page-specific refresh callbacks
- thin `open_page()` entry point
- compatibility aliases for refresh delay / built pages / metrics

**Assessment**

There is no duplicate navigation state machine, but the controller is still
host-coupled because the pages themselves have not become components. Page
extraction should eventually replace private-host dispatch with explicit page
interfaces/callbacks. Compatibility aliases can then disappear.

### SourcePolicyController

**What it now owns**

- capability naming
- setup-required decisions
- selection presentation copy
- primary action routing
- searchable-source filtering
- active plugin-presence filtering
- selected plugin-id normalization

**What remains in MainWindow**

- Sources page construction
- Sources page rendering
- configuration-status refresh orchestration
- install/remove/configure/test workflows
- plugin directory
- diagnostics export
- user streams dialogs
- source ordering
- health-test presentation

**Assessment**

This is the most obviously incomplete existing boundary. Leaving policy in one
object and all operational source management in `MainWindow` would be a
half-separated architecture. The next extraction should complete this vertical
slice.

---

## Highest-value next extraction candidates

### 1. Sources vertical slice — highest priority

**Why first**

- completes the deliberately partial P12c5 boundary;
- around 1,000 source/plugin-related method-lines remain;
- `_build_sources` and `_refresh_sources` are each about 250 lines;
- source/plugin widgets and workflows are highly cohesive;
- plugin configuration, directory and health dependencies can leave the window;
- testability improves substantially because source view models and operations
  can be exercised without a full application window.

**Qualitative assessment**

- cohesion: very high
- coupling inside current window: high but localized
- state ownership opportunity: medium-high
- testability gain: high
- dependency reduction: high
- expected MainWindow reduction: roughly 800–1,100 lines
- behavioral risk: medium
- likely future change: high
- completes existing partial extraction: yes

**Suggested boundary**

```text
SourcesPage
  owns source widgets and page-local presentation

SourceManagementController
  owns refresh/status orchestration, install/remove/configure/test/ordering

SourcePolicyController
  remains pure decision policy

MainWindow
  wires page/controller to ProviderManager and navigation
```

### 2. Music Map / Journey workspace

This is the largest stateful feature cluster.

The journey/music-prefixed cluster contains about **58 methods / ~1,484 method
lines**, plus a substantial block of instance state and the 249-line
`_build_music_map`.

**Qualitative assessment**

- cohesion: high
- current coupling: high
- state ownership opportunity: very high
- testability gain: very high
- dependency reduction: very high
- expected MainWindow reduction: roughly 1,200–1,500 lines
- behavioral risk: medium-high
- likely future change: very high
- reusable boundary: high

**Suggested boundary**

A `JourneyWorkspaceController` owning path, staged journey, recipe/replay and
live-replanning state, paired with Music Map/Journeys page components.

Do not split every journey utility into a tiny class. Treat the workspace as a
cohesive user capability.

### 3. Playback session / Now Playing

The player engine is already a good lower-level boundary, but the window still
contains roughly **47 playback/Now-Playing-related methods / ~879 method-lines**
by broad method-name clustering.

**Qualitative assessment**

- cohesion: high
- current coupling: high
- state ownership opportunity: high
- testability gain: high
- dependency reduction: medium-high
- expected MainWindow reduction: roughly 600–800 lines
- behavioral risk: high
- likely future change: high
- completes existing partial extraction: yes

**Suggested boundary**

`PlaybackSessionController` above `FlowPlayer`, plus a `NowPlayingPage` and
possibly a small persistent `PlayerBar`.

The controller should own current-track/history/prefetch/visual-session state,
while `FlowPlayer` stays focused on audio/queue mechanics.

### 4. Library vertical slice

The broad library cluster is about **25 methods / ~702 method-lines**.

**Qualitative assessment**

- cohesion: high
- current coupling: medium-high
- state ownership opportunity: medium-high
- testability gain: high
- dependency reduction: medium
- expected MainWindow reduction: roughly 550–750 lines
- behavioral risk: medium
- likely future change: high
- completes existing partial extraction: yes

**Suggested boundary**

A Library controller/page owning:

- `LibraryBrowser`
- metadata-correction interaction
- artwork/artist-image enrichment
- scan progress presentation
- scan completion/NAS outcome presentation

It should compose with `LibraryScanController`, not replace it.

### 5. Discover / For You / search-intelligence slice

This cluster is roughly **17 methods / ~514 method-lines**, plus the 130-line
For You and 49-line Discover builders.

Good candidate after the higher-value stateful features are isolated.

### 6. App shell / residual page composition

`_build_ui` should eventually stop being an 813-line hidden monolith, but
moving it first would mostly relocate Qt code without clarifying feature
ownership.

It should be decomposed **after** the major vertical slices above, when the shell
can compose stable page components instead of wiring hundreds of callbacks back
into `MainWindow`.

Likely components:

- `AppShell`
- `Sidebar`
- `PlayerBar`
- `BackgroundActivityBar`
- contextual queue panel

This should be a convergence stage, not the next stage.

---

## What MainWindow should own

The architectural contract for `MainWindow` should be:

### MainWindow may own

- the top-level `QMainWindow`
- application startup/window lifecycle
- construction of major application services/controllers
- composition of top-level page components
- global navigation container
- high-level wiring between major components
- global shortcuts/menu entry points
- genuinely cross-feature coordination
- application shutdown
- startup timeline / global responsiveness hooks

### MainWindow should not own

- provider/plugin decision tables
- provider install/remove/test state machines
- library scan worker logic
- scan presentation state
- playback queue mutation
- playback-session state
- search sequencing
- metadata transformations/enrichment workflows
- artwork/artist-image workflows
- journey path/recipe/live-replanning state
- page-specific widget trees
- page-specific dialogs
- playlist parsing/export details
- resolver policy
- subsystem-specific async state machines
- large domain decision branches

A useful test for future code reviews is:

> If a method only exists because it needs access to five widgets belonging to
> one page, the page probably needs an owner.

And:

> If several methods mutate the same non-window state fields, that state
> probably belongs to a controller or model.

---

## Recommended remaining P12c sequence

### P12c7 — Sources vertical slice

Create a real Sources page/management boundary around the existing
`SourcePolicyController`.

Primary goals:

- move Sources widget ownership out of MainWindow;
- move refresh/install/remove/configure/health/order/stream orchestration;
- keep ProviderManager unchanged;
- keep policy pure;
- remove plugin-management implementation imports from `main_window.py`.

### P12c8 — Journey workspace vertical slice

Move Music Map, path planning, staged journeys, recipes/replay and live journey
state behind a cohesive workspace controller/page boundary.

Primary goals:

- move the large `music_*` state block;
- remove journey/path/replay/live modules from MainWindow;
- preserve lazy page loading and current Flow/Player contracts.

### P12c9 — Playback session / Now Playing

Introduce a session controller above `FlowPlayer` and a page/persistent-bar
boundary.

Primary goals:

- move current-track/history/prefetch/visual state;
- keep audio mechanics in `FlowPlayer`;
- remove resolver/visual/lyrics page orchestration from the window where
  practical;
- preserve Fluid responsiveness and playback behavior exactly.

### P12c10 — Library vertical slice

Complete the scan/library boundary.

Primary goals:

- own `LibraryBrowser` and library widgets in a page component;
- own metadata/artwork/artist-image interaction;
- own scan progress/completion presentation;
- compose with `LibraryScanController`;
- preserve NAS behavior and large-library performance.

### P12c11 — Discover / recommendation / smaller pages

Consolidate For You, Discover/search, and other remaining page-local behavior
where there is a coherent interface.

This stage can also move low-risk Playlist/Moments page ownership if doing so
simplifies the remaining shell.

### P12c12 — Shell composition and MainWindow convergence

Only after feature boundaries are stable:

- split `_build_ui` into persistent shell components;
- remove compatibility aliases left by earlier extractions;
- reduce direct feature-module imports;
- consider extracting the global async coordinator if it remains large;
- rerun the MainWindow audit;
- define the final line/method/import guardrails from the new architecture.

The exact numbering may change if an earlier stage reveals a better seam, but
the order should remain architecture-led rather than LOC-led.

---

## P12c exit criteria

P12c should stop only when the following are true.

### Responsibility

`MainWindow` is primarily top-level composition, wiring and lifecycle.

### Feature ownership

Large page-specific and subsystem-specific clusters have explicit owners.

### State ownership

Feature state such as journey, playback session, search and library
presentation state is no longer stored centrally merely because the window is
globally reachable.

### Testing

Important policy and orchestration can be tested without constructing the full
Qt application window.

### Dependency direction

`main_window.py` mostly imports major services/controllers/pages rather than
low-level feature implementation modules.

### Navigation/pages

Page components expose explicit signals/callbacks/interfaces rather than
reaching through a giant host object for all behavior.

### Method size

No giant method remains because it contains several responsibilities.

A declarative shell builder may still be larger than ordinary methods, but an
800-line `_build_ui` should not remain the final architecture.

### UI construction

No single page builder or refresh method acts as a second monolith.

### Guardrails

The architecture makes the right location for new feature code obvious, and
code-health checks make it difficult to put extracted responsibility back into
`MainWindow`.

### Performance

All decomposition continues to respect:

- Fluid Melodex responsiveness
- startup lazy-import behavior
- large-library behavior
- NAS fault tolerance
- package/release contracts

### Line count

Line count remains a secondary signal only. P12c does **not** need to hit an
arbitrary number to finish.

However, if the responsibility contract above is genuinely achieved, a
7,000-line `MainWindow` would be unexpected and should trigger another audit.

---

## Guardrail decision for P12c6

No new structural guardrail is added in this audit.

The current one-way line ceiling remains useful:

```text
desktop/melodex/main_window.py <= 7163 physical lines
```

Adding a method-size failure gate now would simply freeze known giant methods
such as `_build_ui`, `_refresh_sources` and `_build_sources` into a
baseline.

More meaningful future guardrails should be added when their associated
extractions land:

- after P12c7: prevent source-management implementation imports returning to
  `main_window.py`;
- after P12c8: prevent journey/path/replay/live implementation imports returning
  to `main_window.py`;
- after page extraction: add a maximum MainWindow method-size ratchet;
- after convergence: consider an allowlist of application-level imports for
  `main_window.py`.

Those checks will encode real architecture rather than arbitrary style.

---

## Validation for P12c6

P12c6 changes documentation only.

Validation expectations:

- no production behavior changes;
- no runtime dependency changes;
- no guardrail threshold change;
- no package behavior change;
- existing P12c5 code-health and test matrix already green at the audit
  baseline;
- ordinary documentation/static checks are sufficient for this PR.

The repository's normal PR automation may still run broader workflows, but this
audit itself does not require another expensive performance qualification to
establish its conclusions.

---

## Decision

### A — Continue P12c

P12c6 recommends **continuing P12c**.

The next stage should be **P12c7 — Sources vertical slice**.

The reason is architectural, not cosmetic: P12c5 extracted source/plugin policy
but left a large, cohesive Sources subsystem split between the controller and
`MainWindow`. Completing that vertical slice reduces dependency surface,
improves testability, removes two of the three largest remaining
feature-specific methods, and finishes an already-started boundary before
opening another one.
