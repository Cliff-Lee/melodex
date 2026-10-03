# Codebase health baseline — Campaign 12 / P12a

Snapshot: main at commit 66657d257b4dbad1b5be87006ee8325cec18c8d3 on 2026-10-03.

## Purpose

P12a is a measurement and architecture-discovery stage. It deliberately does not refactor production code.

The objective is to establish repeatable structural facts before Campaign 12 starts moving responsibilities between modules. File size, method counts and import connectivity are signals, not quality scores. A large module is only a refactor target when it also concentrates responsibilities or makes safe change difficult.

## Repository baseline

At this snapshot:

- 625 tracked files.
- 230 Python files.
- 92 Python test files matched under the repository test paths.
- 8 GitHub Actions workflow files.
- The desktop application has strong behavioural gates: compileall, pytest on Python 3.11 and 3.12, documentation/release checks, Fluid responsiveness gates, 12.7k large-library baselines, soak testing, startup baselines, elastic-library qualification and NAS fault qualification.
- The provider SDK already has Ruff configured for E, F, I, UP and B rules.
- The desktop package itself has no Ruff or mypy configuration, and the main test workflow does not currently run Ruff against desktop code.

This means the codebase is not under-tested; the main maintainability gap is structural consistency and static-quality coverage around a fast-growing desktop package.

## Primary hotspots

| Module | Approx. lines | Function definitions | Broad Exception handlers | Initial assessment |
| --- | ---: | ---: | ---: | --- |
| desktop/melodex/main_window.py | 7,630 | 315 total / 259 four-space methods | 39 | High structural risk |
| desktop/melodex/metadata.py | 2,405 | 77 | 43 | High responsibility concentration |
| desktop/melodex/library_browser.py | 2,311 | 78 | 0 | Medium-high UI/model concentration |
| desktop/melodex/rich_now_playing.py | 1,406 | 51 | 4 | Medium |
| desktop/melodex/provider_manager.py | 1,305 | 78 | 9 | Medium-high orchestration concentration |
| desktop/melodex/plugin_directory.py | 1,244 | 37 | 2 | Medium |
| desktop/melodex/providers/local_files.py | 1,183 | 40 | 1 | Medium, performance-sensitive |
| desktop/melodex/library_index.py | 1,202 | 23 | 4 | Medium, persistence-sensitive |
| desktop/melodex/capabilities.py | 1,177 | 52 | 6 | Medium-high extension boundary |

Broad exception handlers are review targets, not automatic defects. Many occur at GUI, plugin, network or persistence boundaries where defensive containment can be intentional.

## MainWindow finding

main_window.py is the first architectural priority because it is both large and responsibility-dense.

The class currently coordinates, among other things:

- window and page construction;
- navigation and lazy-page population;
- Home / Discover / Sources / Now Playing surfaces;
- playback and queue actions;
- local-library scanning and scan status;
- search and provider/source coordination;
- plugin setup and health actions;
- Album Wall and Music Map;
- journeys and live journey replanning;
- artwork and metadata actions;
- diagnostics;
- asynchronous UI work and background scheduling.

Several methods are independently large:

| Method | Approx. span |
| --- | ---: |
| _build_ui | 813 lines |
| _start_local_scan | 262 lines |
| _refresh_sources | 253 lines |
| _build_sources | 250 lines |
| _build_music_map | 249 lines |
| __init__ | 136 lines |
| _build_for_you | 130 lines |
| _build_home | 129 lines |

Method-name clusters also expose natural seams: roughly 17 _build_ methods, 16 _refresh_ methods, 17 _play... methods, 20 _music... methods and 20 _journey... methods.

That supports a responsibility-led decomposition in P12c rather than an arbitrary split-by-line-count exercise.

## Important constraint: preserve deliberate lazy imports

main_window.py contains many local imports inside page builders and actions. Some may look untidy in isolation, but the startup campaign deliberately reduced the cold import graph.

P12c must therefore classify local imports before moving them:

1. deliberately lazy for startup or optional dependencies;
2. deliberately local to avoid dependency cycles;
3. accidental/repeated and safe to centralise.

No cleanup stage should hoist imports merely for style if it regresses startup.

## Secondary hotspots

### metadata.py

RichMetadataService currently combines cache/index persistence, local lyrics, community lyrics, embedded artwork, MusicBrainz/Cover Art Archive access, artist resolution, remote JSON helpers and artist-photo discovery.

P12d should separate these by domain boundary only where tests demonstrate behaviour can be preserved. The 43 broad Exception handlers are especially worth classifying by boundary rather than mass-replacing.

### library_browser.py

LibraryBrowser mixes Qt widget/card rendering with filtering, view switching, viewport hydration, artwork lookup progress and catalog/model handling.

The recent large-library work already proved that rendering granularity matters. Any decomposition must preserve viewport-first hydration and the existing responsiveness contract.

### provider_manager.py

ProviderManager currently spans settings, local roots/index coordination, plugin installations, provider ordering, user streams, search/recommend/browse/resolve behaviour and resolution preferences.

This is a likely P12e/P12f boundary candidate, but should not be split before provider/API contracts are explicit.

## Strengths to preserve

Campaign 12 should build around the parts that are already unusually strong for a young project:

- extensive pytest coverage;
- release checks beyond unit tests;
- deterministic responsiveness gates;
- synthetic large-library qualification;
- sustained soak tests;
- startup measurement;
- NAS fault injection/qualification;
- a separate provider SDK with its own package and Ruff configuration;
- explicit responsiveness and large-library engineering documents;
- existing source-neutral API/provider architecture.

The refactor should reduce change risk without sacrificing these behavioural contracts.

## Risk register

| Area | Risk | P12 response |
| --- | --- | --- |
| MainWindow responsibility concentration | High | P12c staged controller/service extraction |
| Metadata responsibility concentration | High | P12d domain separation |
| Desktop static-quality coverage | Medium | P12b incremental Ruff guardrails |
| Type contracts between subsystems | Medium | P12e explicit dataclasses/Protocols where useful |
| Dependency direction | Medium | P12f import graph and boundary enforcement |
| Broad exception handling | Medium | P12i classify by operational boundary |
| Performance-sensitive local imports | High if mechanically cleaned | Preserve/startup-test during P12c |
| Large-library/NAS code during refactor | High regression cost | Existing qualification remains mandatory |
| Open historical campaign branches | Merge-conflict risk | Base structural work on current main; avoid reviving stale branches |

## Campaign order from this baseline

1. P12b — add incremental code-health guardrails without mass formatting.
2. P12c — decompose MainWindow by responsibility, in small behaviour-preserving PRs.
3. P12d — untangle metadata and library-browser responsibility clusters.
4. P12e — make core domain shapes/contracts explicit.
5. P12f — establish dependency direction and remove avoidable cycles.
6. P12g — deduplicate only genuine shared concepts and remove confirmed dead code.
7. P12h — improve test architecture around extracted services/controllers.
8. P12i — classify error boundaries and observability.
9. P12j — concise developer architecture documentation.
10. P12k — human-written-code pass after structural work.
11. P12l — rerun this baseline and compare structure plus runtime regressions.

## Repeatable scanner

scripts/codebase_health.py is intentionally stdlib-only. It scans the desktop package, tests, provider SDK, official providers and scripts, then reports:

- Python file and line counts;
- largest files;
- longest functions;
- broad and bare exception handlers;
- desktop-package import fan-in/fan-out;
- multi-module dependency cycles;
- syntax errors.

The scanner writes JSON to stdout so P12l can compare snapshots mechanically:

    python scripts/codebase_health.py > codebase-health.json

It uses only the Python standard library and is descriptive. P12b may turn selected findings into ratchets, but P12a deliberately adds no new release gate.

## P12a exit decision

Proceed to P12b.

Do not start production-code restructuring from this PR. The evidence is sufficient to prioritise MainWindow first, but P12b should establish lightweight guardrails before P12c begins extracting responsibilities.
