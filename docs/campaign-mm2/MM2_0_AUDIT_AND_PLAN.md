# MM2 — Music Map as the primary discovery experience

Status: **MM2-0 code and UX audit completed (static review); runtime/CI baseline pending**  
Audit date: 2026-10-10  
Starting point: `main` at `4730b17fa27d2be317914ef2fe7ed8087648896e`  
Implementation branch: `campaign/mm2-map-first-experience`  
Release policy: **no direct changes to main or published artifacts before reviewed, tested integration**

## Product contract

Music Map should feel like a navigable listening landscape rather than a graph configuration screen.

1. **Music first.** In default browsing, the viewport should receive >=75% of the available main page area at ordinary desktop sizes, as a *design target* rather than a fixed minimum under every window size.
2. **The map never moves to make room for a tool.** View settings, selection actions, and Journey tools float above or beside the canvas. Opening/closing them must preserve camera center, zoom and selection.
3. **Direct manipulation.** Click selects; double-click plays; drag empty space pans; search locates; choose start/destination on the map; route rendering remains visible.
4. **Progressive disclosure.** Default chrome: search, concise view control, Journey control, return-to-now-playing and fit. Existing detailed Route/Compose/Live actions remain accessible.
5. **Fast listening.** The map must never block play/queue controls or require Flow analysis to play ordinary library music.
6. **No false promises.** The initial map is a bounded exploration sample, not all indexed tracks. Counts and missing analysis must be explained accurately.
7. **Local-first.** Keep current privacy boundaries and explicit opt-in requirements for metadata enrichment.

## MM2-0 — Repository observations

The following claims come from reading source on the starting commit, not from executing the app or timing a packaged build.

| Component | Current implementation | Consequence / change |
| --- | --- | --- |
| `desktop/melodex/journey_workspace.py` lines ~253–623 | `_build_music_map` creates a heading, subtitle, persistent play/queue/route actions, a `music_map_options_panel` inserted into the page layout, a `music_map_power_scroll` route/compose/live planner also inserted in that layout, and a `music_path_steps` list below the map. Route tool scroll can consume up to 420px. | **Root cause of reported map collapse**: vertically disclosed panels take space from the canvas. Extract content into independently positioned popover/drawer without changing journey algorithms. |
| `desktop/melodex/music_map.py` lines ~270–367 | `MusicMapWidget` contains a permanent colour/connection/search/zoom/fit toolbar *above* its `QGraphicsView`, plus a dense status label below it. | Simplify permanent toolbar and move status/explanations to contextual content; preserve accessible search and explicit zoom fallback. |
| `desktop/melodex/music_map.py` lines ~389–507 | `set_map` clears and rebuilds the `QGraphicsScene` and artwork queues. It restores viewport scale/center only when >=50% of old node refs overlap; route state resets. | Avoid rebuilds when opening menus and changing selection. Treat map refresh as a separately guarded operation; add tests for camera and route state. |
| `desktop/melodex/music_map_model.py` lines ~204–354 | Deterministic feature-space projection and graph, bounded to `max_nodes`; scored priority tracks and distributed sampling. 2D coordinates are scaled from projected components. | Don't treat all library tracks as plotted. Future semantic zoom/regions require hierarchical aggregation; coordinate stability needs measurement when library changes. |
| `desktop/melodex/journey_workspace.py` lines ~779–915 | Builds profiles from a local snapshot with `max_tracks=5000`, maps `max_nodes=700`, and builds knowledge graph for mapped refs. Refresh can stop a live journey and resets route/waypoint state. | Distinguish indexed/catalogue size vs analysed vs mapped. Avoid triggering refresh on passive navigation; protect live journey state. |
| `desktop/melodex/music_pathfinder.py` and workspace lines ~1056–1196 | Existing route engine uses graph features/knowledge, explanatory hops and play/queue emissions. | Reuse. Build a much smaller start/destination/preview interface around the established APIs. Never use 2D pixel proximity as a route metric. |
| `desktop/melodex/music_map.py` lines ~41–101 and ~721–850 | Smooth zoom, drag/pan, search, route highlighting and track-selected/activated signals exist. | Retain behaviour and add focus-now-playing, remembered camera, navigation history and contextual track actions incrementally. |
| `docs/UX_REDESIGN.md` | Listener / Collector / Explorer / Tinkerer roles; progressively disclosed advanced functionality. | MM2 implements this existing policy; it is not a competing product redesign. |
| `docs/MUSIC_MAP.md` | Explicitly states 700-node preview and existing disclosure controls. | Update documentation as each stage changes reality; don't document aspirational behaviour as shipped. |

### Screenshot-based UX findings (not automatically measured)

- Default screen shows too many equally prominent actions before any track is selected.
- Route / Options expansion hides most of the map, interrupting the core task.
- Covers overlap densely on the right, with no clear hierarchical navigation or landmarks.
- The same user goal is represented by multiple verbs: route, journey, composer, live, path.
- Labels such as `Improve map`, `Find map details (+8)` and `UA` do not explain their purpose.
- The small status line mixes counts, guidance and selected-track technical properties.

### Protect the existing strengths

- Local playback from single-click selection + activation on double-click.
- Sonic vs factual/knowledge connections, explicit origins and explanations.
- Route/Compose/Live support including queued and immediate playback.
- Background prepared artwork/prefetch and the responsiveness scheduler.
- Existing map camera restoration behaviour and small-window geometry safeguards.
- Power-tool availability for researchers/power users; no data loss or source substitution.

## Implementation plan and independent gates

### MM2-1: Canvas-first shell (first code change)

- Replace the stacked `music_map_options_panel` with an anchored menu/popover.
- Replace the stacked `music_map_power_scroll` and `music_path_steps` with an overlay Journey workspace that *does not participate in the canvas height layout*. At narrow sizes, overlay a dismissible, scrollable panel; avoid unbounded minimum widths.
- Keep existing route widgets and callbacks initially to avoid breaking the route engine; reparent them only where the widget ownership and lifetime are safe.
- Remove redundant globally displayed Play Selected and Queue Selected in favour of a contextual selected-track card; retain keyboard and accessibility actions.
- One user-visible primary path: **Explore → click → Play / Queue / Start journey**.
- Default close state is canvas-only. Escape closes the foremost overlay without unselecting the track or stopping playback.

**Gate:** tool open/close before/after camera center, transform, selection, map widget geometry; background audio unaffected. Acceptance at 1024x768, 1280x800, 1600x900; Qt offscreen plus manual Mac/Ubuntu checks.

### MM2-2: Navigation and track inspector

- Fit, Back/Forward, Find and Current Track location; hover previews that do not steal focus.
- Distinguish single click, double click, pan drag and track-to-journey drag without accidental playback.
- Results that are outside the currently mapped sample must explain the limitation; do not pretend search covers the entire library.

**Gate:** click/double-click semantics and camera/history tests; full keyboard path to Play / Queue / Journey; zoom under pointer preserved.

### MM2-3: Semantic zoom / stable visual hierarchy

- Overview: genuine grouped neighbourhoods with counts and representative artwork; mid zoom: album/artist landmarks; close zoom: tracks and explainable edges.
- Verify grouping against audio feature-space and knowledge graph, not arbitrary coordinates or genre names.
- Repeated artwork treatment, unknown-art fallback, collision reduction, label decluttering, consistent selection marks.
- Separate cached music graph/positions from rendering; full scene recreation must be exceptional.
- Do not exceed current map-node limits without evidence from load tests.

**Gate:** measurable legibility across 217 / 700 / 12,700 / 100,000 indexed tracks; compare spatial stability after small library delta; fallback quality when metadata/artwork is missing.

### MM2-4: Play from here

- One-click start of local-region session; Explore nearby; Surprise me.
- Use current listening engine and honour queue/preferred-source behaviour.
- Protect the under-4s-local / under-5s-NAS first-play campaign goals as non-regression targets, not claims of achieved speed on MM2 builds.

**Gate:** prompt playback starts without exposing analysis controls; graceful no-analysis and no-playable-track fallback.

### MM2-5: Graphical journeys

- Choose A and B by clicking mapped tracks, preview the existing pathfinder's route, play or queue it.
- Waypoints / live steering / detailed composer remain under Advanced.
- Route progress highlights current track, with optional follow-camera mode disabled if user manually pans.

**Gate:** start/destination/route visible simultaneously; explanations accessible; route search never uses screen distance.

### MM2-6: App-wide integration

- Find on Map from library and Now Playing, map-to-track actions, saved places and route recall.
- Consider Discover as main entry only after task testing against quick local playback and Collector workflows; don't forcibly make the map first-run default while unanalysed.

### MM2-7: Qualification and release

- Qt offscreen UI gates and unit tests for projection/pathfinder/queue integration.
- 1024x768 keyboard/screen-reader usability and packaged macOS/Windows/Linux QA.
- Stress datasets, view-motion responsiveness and memory; background map work must not starve playback.
- Documentation and screenshots updated to reflect shipped controls.
- PR/CI green, manual sign-off, staged release; update public default branch only after verification.

## First engineering slice / test matrix

Regression sources on main:
- `desktop/tests/test_spatial_browsing_ux.py`: existing progressive disclosure, camera/zoom retention, hover/artwork, compact node display.
- `desktop/tests/test_music_map_model.py`: deterministic sampling, graph building, no-edges mode.
- `desktop/tests/test_music_pathfinder.py`: pathfinding correctness and explanations.
- `desktop/tests/test_journey_workspace.py`: route and live workspace semantics.
- `desktop/tests/test_window_geometry_containment.py`: bounds/restore.
- `desktop/tests/test_responsiveness.py` and `desktop/tests/test_responsiveness_gate.py`: interaction latency.

New MM2-1 tests required:
1. Default map occupies a stable content rectangle with all overlays hidden.
2. Opening/closing View **does not change the map rectangle**, camera, zoom or selected track.
3. Opening/closing Journey **does not change the map rectangle**, camera, zoom or selected track.
4. Switching Route/Compose/Live preserves the canvas and each state.
5. ESC closes overlays safely; same mouse/keyboard operation remains usable afterward.
6. Responsive drawer bounds at 1024x768; no overlapping persistent transport.
7. Selected-track Play/Queue emit exactly once; passive selection never plays.

## MM2-0 sign-off and limitations

**Completed here:** source review, code ownership identified, root cause linked to widget layout, current map scaling constraints identified, implementation boundaries / gates documented, separate working branch created.

**Not yet completed:** local checkout/build, pytest run, live window instrumentation, packaged smoke tests, baseline FPS/memory measurements, UX interviews. These require a runnable source/build environment or repository CI and must not be represented as passed.

**Next step:** implement **MM2-1a** as the smallest code PR (overlay shell + viewport-retention tests), then extend to contextual actions only after those gates pass.
