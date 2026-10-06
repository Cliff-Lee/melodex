# P14 — Real-World Fluidity & Playback Integrity

**Status: P14m COMPLETE; post-geometry P14l5 requalification in progress. Campaign P closure pending.**

P14m fixed and qualified the reproduced top-level window geometry defects. The final Campaign P
closure now depends only on rerunning the bounded P14l5a–P14l5d qualification on the post-P14m
production code. Non-blocking optimization remains post-P.

P14 converts the first detailed large-library external beta report into a permanent
engineering qualification campaign.

## Why P14 exists

An external macOS tester with roughly 12,700 tracks reported that the initial scan
completed in about 13 minutes, but several interaction paths still felt unstable:

- two-finger Album Wall panning caused repeated beach balls and occasional audio glitches;
- returning to My Music and scrolling could lag;
- clearing an album search could beach-ball;
- cached/visible Album Wall artwork arrived too slowly while panning;
- live window resizing after title-bar maximize behaved erratically on macOS;
- FLAC seeking snapped back unless the target was clicked repeatedly;
- after Previous followed by natural track completion, audible playback and transport
  presentation could disagree;
- double-clicking an album did not appear to preserve normal album listening semantics;
- Flow-style crossfades were audible while playing a single album.

The campaign treats these as correctness and architecture defects, not cosmetic polish.

## Core contract

> Nothing the user does visually may disturb the music. Nothing happening musically
> may make the interface lie.

Continuous interaction paths must not perform slow filesystem access, metadata work,
network access, expensive image processing, large database operations, or substantial
layout reconstruction on the Qt main thread.

## P14 sequence

### P14a — Reproduction and instrumentation

Build a repeatable baseline before changing behaviour.

The automated probe exercises:

1. a synthetic 12,700-track My Music catalog;
3. album search followed by clear-search expansion;
4. repeated Album Wall viewport moves;
5. visible artwork application;
6. repeated My Music resize cycles;
7. event-loop and interaction latency collection.

Run:

```bash
python scripts/real_world_fluidity_probe.py
```

To turn the current budgets into a blocking local check:

```bash
python scripts/real_world_fluidity_probe.py --enforce
```

The offscreen probe is intentionally not presented as a replacement for a physical
Mac test. It cannot reproduce macOS WindowServer behaviour or audible glitches.

### P14b — Seeking correctness

Introduce explicit scrub ownership:

`idle -> scrubbing -> committing -> idle`

Player position updates must never overwrite the slider while the user owns it. Seek
requests are committed once and reconciled against backend confirmation.

P14b also makes the whole slider groove a direct seek target rather than relying on
platform-default QSlider page-step behaviour. Click, drag, keyboard and wheel gestures
all enter the same ownership path. After commit, stale position ticks are suppressed
until the backend reports the requested location (within tolerance) or a bounded
timeout releases ownership. A track change cancels any pending seek.

Qualification covers FLAC, MP3, M4A/AAC and WAV, forward/backward seeking, pause,
rapid repeated seeks and near-EOF seeking.

### P14c — Authoritative playback state

Unify natural EOF, Next, Previous, queue jumps and crossfade completion behind one
track-transition commit path. QMediaPlayer `EndOfMedia` is handled explicitly on
both decks, so a started incoming deck cannot keep playing after the outgoing deck
ends while Melodex remains stuck on the old queue index.

Queue-position changes are committed before `trackChanged` is published. Delayed
`EndOfMedia` events from an old deck are ignored, and manual queue changes cancel
any in-flight crossfade before loading another track.

Required invariant outside an intentional crossfade:

`audible track == active deck == queue[index] == transport current track`

During an intentional crossfade there are two audible decks, but there is still one
explicit outgoing index and one validated incoming target. When the transition commits,
the incoming deck, queue index and transport update atomically through the same path.

### P14d — Remove work from the 100 ms playback tick

Transition planning is calculated once per relevant track pair, on the shared bounded
`prefetch` scheduler lane. The result is published back to the player with a generation
token; stale results from a superseded queue pair are discarded.

The 100 ms timer now reads only an in-memory transition duration. It never calls the
Flow transition planner and therefore performs no filesystem stat, NAS access, SQLite
query, metadata lookup, network request or audio analysis. If the plan is not ready by
the time a transition is needed, playback uses the bounded 4.5 s fallback rather than
blocking the audio/UI path.

Queue replacement, manual track changes and relevant metadata updates invalidate and
re-prime the pair plan. Diagnostics count requests, completed/stale/failed plans and
scheduler rejection without recording track names or paths.

### P14e — Playback intent

Playback queues now carry one explicit intent:

- `album`;
- `playlist`;
- `journey`;
- `manual_queue`;
- `provider`.

Only `journey` enables Flow transition planning/crossfading. Album, playlist, manual
queue and provider playback advance naturally at end-of-media and never submit Flow
transition-planning work.

Album Wall and My Music album playback explicitly create `album` queues; saved/imported
and AI-created playlists use `playlist`; Music Map/Play for Me/Refine with Flow use
`journey`; direct library/history/intelligence playback uses `manual_queue`; online
search-result playback uses `provider`.

Unknown external-control intent values are normalised to `manual_queue`. The current
intent and whether Journey transitions are enabled are included in redacted diagnostics,
but media metadata is not.

This separates "play this recording/collection normally" from "Melodex should actively
DJ this route." A single album therefore preserves disc/track order without an unexpected
Flow crossfade between its tracks.

### P14f — Album Wall render hot path

Album tiles now prepare each cover once when artwork arrives. Smooth resize/crop is
performed at that boundary; `paint()` only blits the already-prepared 164×164 pixmap.
Repainting or panning therefore creates no temporary scaled pixmaps.

Viewport traffic is coalesced to at most one notification per event-loop turn. During
active pan/zoom/resize motion the view temporarily disables antialiasing and smooth
pixmap filtering, then restores full-quality rendering after 90 ms of quiet.

Visible-art discovery is also spatial rather than O(all albums): the scene index is
queried for the viewport plus overscan and only those tile candidates are considered.
Artwork lookup is deferred until motion settles, so continuous trackpad movement does
not compete with painting for the UI thread.

Artwork decode itself still occurs at the application boundary in this phase. P14g moves
that work into the shared decoded-artwork service with cache/deduplication/generation
control; P14f's contract is specifically that continuous motion and `paint()` are cheap.

### P14g — Shared artwork service

Artwork decode/resize/crop is now a shared worker-side service backed by `QImage`.
Album Wall, My Music album cards, track rows and artist cards request UI-sized prepared
images from the same cache. `QPixmap` creation remains on the Qt thread, but storage
stat/decode and smooth scaling do not.

The cache is bounded by bytes (64 MiB by default), LRU-evicted, keyed by path/target
size/mtime/file size, and keeps a short negative cache for missing or undecodable files.
Concurrent requests for the same image are de-duplicated so one worker decodes while
others wait for that result. A non-blocking memory peek lets rebuilt cards reuse an
already-prepared image without touching the filesystem.

Every viewport artwork batch carries a generation token. Search/view/scroll/model changes
advance that generation; results from superseded viewports are discarded rather than
painting stale covers. Explicit online artwork recovery still completes its metadata/cache
work, but stale visual delivery is ignored safely.

Redacted diagnostics expose only aggregate cache counts, memory use, deduplicated waits,
failures and evictions. Paths, titles and artwork URLs are never exported.

### P14h — My Music filtering/layout

Precompute search keys, compute only the active view, reuse card widgets and diff
layout membership rather than clearing/rebuilding grids during every filter change.

### P14i — Native macOS resize behaviour

During a live resize, Album Wall keeps motion rendering cheap and waits 180 ms after the
latest geometry event before scanning/requesting visible artwork. Pan and zoom retain the
shorter 90 ms settle. The zoom remains unchanged, and resize handling does not resize or
move the top-level window. Offscreen regression coverage stresses repeated geometry changes
and confirms visible-art work runs once after resize settles.

The physical Mac check below remains necessary for WindowServer, taskbar/dock bounds and
native edge/corner hit-testing.

### P14j — Album-order qualification

Use one stable disc/track key across Album Wall and My Music. Accept common `3/12` tag
values, keep unknown numbers after known tracks, and make malformed values safe. Album
playback diagnostics contain only track counts, numbered-tag counts, malformed-tag counts,
duplicate positions and an ordering-valid flag; they never include media metadata.

Regression cases cover ordinary single-disc records, multi-disc records, missing numbers,
malformed values and duplicate disc/track positions.

### P14k — Visible audio settings

The persistent player and Now Playing view show the effective transition behavior:
Journey crossfade is labeled planned or active with its duration, while album,
playlist, provider and manual queue playback show crossfade off. Both surfaces
explicitly show normalization off because Melodex currently applies no normalization
processor. State updates follow playback intent and transition-plan/crossfade events;
they do not run from the 100 ms playback tick.

The visible state is derived from the player's effective runtime state and contains no
track metadata. Regression coverage checks album, Journey planned/active, and playlist
semantics, including explicit normalization-off reporting.

### P14l — Scan optimization

P14l is split into narrow, independently qualified stages so a speed improvement cannot
hide a correctness or NAS-safety regression.

#### P14l1 — Bounded metadata concurrency

Cold imports keep the permanent maximum at eight outstanding metadata jobs. Scans still
start with two workers. Fast local storage may scale to eight metadata workers once stat
samples establish low latency; medium-latency local storage uses four. A likely network
or NAS path remains at two workers until enough fast samples arrive, and even then caps
at four workers. High-latency storage stays at two.

Unchanged rescans still perform zero metadata reads, small-delta rescans still schedule
work only for changed/new files, discovery remains bounded at 256 rows, and incomplete
or unavailable NAS roots retain the existing atomic publication and deletion-safety rules.

#### P14l2 — End-to-end scan phase timing

The isolated production scan child reports four non-overlapping numeric timings:
`bootstrap_cache`, `scan`, `persistence`, and `hydration`, plus total child elapsed
time. These timings contain no media names or paths.

This stage is observational only: it changes no traversal, metadata, SQLite or hydration
policy. P14l3/P14l4 may optimize a phase only after these measurements identify it as
material.

#### P14l3 — Unchanged and small-delta traversal

P14l3 is itself split into small traversal changes.

**P14l3a — canonical cache fast path.** `LocalLibraryIndex.load_scan_cache()` and
`load_directory_manifests()` explicitly return canonical absolute-path keys. Index-backed
production scans now preserve those keys instead of normalising every cached track and
directory a second time before traversal. Defensive/non-index callers retain the old
normalisation behavior by default.

The scan reports only aggregate `cache_keys_canonical` and
`cache_key_normalizations` diagnostics. No paths are exported. This stage changes no
fingerprint, directory-manifest, metadata-read, deletion, cancellation or NAS-root safety
rule.

P14l3a qualified independently across the full release matrix.

**P14l3b — deferred directory materialization.** A directory with a persisted manifest
still stats every audio file and recomputes the same sorted name/size/mtime fingerprint.
While that proof is being built, the producer now buffers only the minimal
`(name, size, mtime)` tuple. Full paths, canonical track keys and queue work dictionaries
are created only if the directory manifest misses.

A matching unchanged directory therefore performs the filesystem correctness proof but
creates zero per-track work items. Changed directories fall back to ordinary file-level
reuse/metadata decisions, and the existing 5,000-file direct-directory cap still forces
streaming materialization before an oversized buffer can grow without bound.

Aggregate diagnostics report full file-work items materialized and materializations avoided.
No media names or paths are exported.

P14l3b qualified independently across the full release matrix.

**P14l3c — cached-root normalization memo.** The deletion-safety sweep still checks every
cached track that was not observed in the completed scan, but repeated tracks from the same
indexed root now share one lexical root normalization. This preserves the exact root
availability/deletion decision while reducing another collection-sized path-normalization
loop to one normalization per distinct cached root.

Diagnostics report only the aggregate number of cached-root normalizations.

P14l3c qualified independently across the full release matrix.

#### P14l4 — Persistence and catalog hydration

P14l4 is split so read-side hydration and write-side publication remain independently
qualified.

**P14l4a — streaming final hydration.** The final post-commit catalog query keeps the same
SQLite ordering and JSON parsing semantics, but consumes the cursor row-by-row instead of
calling `fetchall()` before building the track list. The final catalog is necessarily
collection-sized; the temporary second collection-sized SQLite row list is not.

A regression uses a cursor whose `fetchall()` raises, proving hydration stays streaming
while malformed metadata rows retain the existing skip behavior. This stage changes no
database schema, publication transaction, scan semantics or catalog ordering.

P14l4a qualified independently across the full release matrix.

**P14l4b1 — streaming existing fingerprints.** The publication transaction's
`SELECT relative_path, size, mtime_ns` comparison now consumes its SQLite cursor directly
rather than creating a temporary `fetchall()` row list before building the required
fingerprint dictionary. The dictionary remains collection-sized because later reuse/delete
decisions need random access; only the duplicate SQLite row container is removed.

A regression wraps the real SQLite connection and makes `fetchall()` fail specifically for
this query while requiring an unchanged eight-track publication to reuse all eight rows.

P14l4b1 qualified independently across the full release matrix.

**P14l4b2a — dictionary-key delete view.** The delete comparison no longer first copies the
entire existing-track dictionary into `set(existing)`. It performs the same set difference
starting from the dictionary's set-like `keys()` view instead. The resulting
`removed_paths` set, `incoming_paths` set and `preserved_existing_paths` set are unchanged
in this slice.

The existing batched-deletion qualification remains the behavioral guard: 600 removals must
still be emitted in three bounded batches with the same final catalog.

P14l4b2a qualified independently across the full release matrix.

**P14l4b2b — one-pass preserved/delete classification.** Publication no longer builds a
collection-sized `preserved_existing_paths` set. One pass over the existing fingerprint
dictionary increments a preserved-row counter when the row's directory is preserved and,
otherwise, adds the path to `removed_paths` only when it is absent from `incoming_paths`.

The `incoming_paths` and `removed_paths` sets remain unchanged in this slice. A focused
qualification persists three rows, preserves two by directory, and requires exactly two
reused rows plus one deletion.

P14l4b2b qualified independently across the full release matrix.

**P14l4b2d — bounded delete candidates.** Publication no longer builds the remaining
collection-sized `removed_paths` set. Existing rows are classified exactly as before, but
deletion candidates now flow directly into the existing bounded delete batch and are flushed
at `batch_size`.

The atomic transaction, cancellation rollback, preserved-directory logic and incoming-path
membership test are unchanged. The `max_removed_path_rows` diagnostic now measures peak
live delete candidates rather than total removals, so a 600-row deletion with batch size 250
must peak at 250 rather than 600.

**P14l4b2c — publication allocation telemetry.** Before changing `incoming_paths`, the
persistence result now reports only three aggregate row-count maxima across roots:
`max_existing_fingerprint_rows`, `max_incoming_path_rows`, and
`max_removed_path_rows`. These reveal the shape of the remaining collection-sized
containers without exporting paths or metadata.

The existing 601-track batch tests qualify both ends of the workload: an unchanged
publication reports 601 existing + 601 incoming + 0 removed rows, while a 600-track deletion
reports 601 existing + 1 incoming + 600 removed rows. This stage is observational only.

**P14l4b2e — incoming-path decision: defer.** The largest existing scale contract is the
1,000,000-track Elastic Library qualification. `incoming_paths` reuses the relative-path
string objects already held by the grouped persistence rows, so its incremental cost is the
set table rather than another million path strings.

A direct allocation measurement using the qualification's deterministic one-million-track
path shape measured approximately:

- 12,700 tracks: 0.50 MiB live / 0.63 MiB transient peak;
- 100,000 tracks: 4.0 MiB live / 6.0 MiB transient peak;
- 250,000 tracks: 8.0 MiB live / 12.0 MiB transient peak;
- 500,000 tracks: 16.0 MiB live / 24.0 MiB transient peak;
- 1,000,000 tracks: 32.0 MiB live / 48.0 MiB transient peak.

The existing clean one-million-track qualification recorded roughly 1,720 MiB post-persist
process RSS. The `incoming_paths` transient peak is therefore only about 2.8% of that
process peak, remains linear with collection size, and does not violate the existing bounded
queue/worker or linear-memory scaling contract. Replacing it now would likely trade one
membership structure for another while adding persistence complexity.

Decision: do not implement P14l4b2e in Campaign P. Record it in the post-P performance
backlog and reconsider only if later profiling shows persistence-memory pressure on a real
workload.

#### P14l5 — Final 12.7k/NAS qualification

**P14l5a — local 12.7k timing: GREEN (post-P14m rerun).** The final P14m8c
12,700-track elastic-library artifact passed on the post-geometry production/test code.
Cold scan time was 3.150 s with 0.314 s persistence; traced Python peak was 15.192 MiB,
process peak RSS was 126.863 MiB and the database was 8.234 MiB. The run performed exactly
12,700 metadata reads, held the discovery queue at 256/256, held metadata in-flight at 8,
and persisted in 51 write batches. Every bounded-queue, bounded-concurrency, linear-memory
and timing scale gate passed.

**P14l5b — small-delta timing: GREEN.** On the same 12,700-track qualification, the standard
delta of 50 changed + 50 added + 10 deleted tracks completed in 2.445 s with exactly 100
metadata reads, 100 row writes and 10 deletions. Traced Python peak was 7.275 MiB and the
existing delta-vs-cold scaling gate passed.

**P14l5c — NAS qualification: GREEN.** The NAS fault suite passed all cases. Cached browsing
remained stable during a slow rescan; high-latency storage adapted to two metadata workers;
transient I/O faults recovered after bounded retries; a mid-scan disconnect marked the root
incomplete and preserved all 40 cached tracks with zero deletions; and blocked metadata work
could be cancelled safely.

**P14l5d — cancellation/restart qualification: GREEN.** Cancellation published no partial
catalog. The interrupted 12,700-track scenario staged 256 rows; restart reused all 256 staged
rows and completed in 2.513 s. The separate blocked-I/O NAS case hard-cancelled in 0.152 s,
well inside its 2.5 s limit.

### P14m — Window Geometry Containment

**Core invariant:** the user/window manager owns top-level window geometry. Feature pages
adapt to the viewport and must never enlarge `MainWindow` through navigation, hydration or
layout minimum propagation.

P14m1 identified the ownership mechanism rather than adding a page-name resize hack. Qt's
stock `QStackedWidget` exports child-page minimum-size requirements; a lazily built page can
therefore raise the containing window's effective minimum under a native window manager.
Music Map also carried a hard 340 px canvas minimum. No feature code was found calling
top-level `resize()` or `adjustSize()`.

P14m2 introduces a viewport-owned page stack whose minimum-size hint is independent of
feature-page minima and removes Music Map's hard canvas minimum. Large map scene coordinates
remain scene coordinates only; the graphics view pans/zooms inside whatever viewport it is
given.

P14m3–P14m7 qualify major page transitions, Albums/Artists/Tracks, Lyrics, dynamic map
hydration, expanded route/journey tools, small normal windows, maximize/restore, stale
restored geometry and native macOS/Windows geometry behavior. Restored normal geometry is
contained once at startup against current `availableGeometry`; there is no continuous clamp,
recentering loop or resize-event intervention.

**P14m8a — native geometry probe review: GREEN.** The merged geometry contract held on
macOS ARM, macOS Intel, Windows x64 and Linux/X11. Music Map build/hydration/tool expansion
and navigation retained the user-selected normal geometry on every target; the feature stack
reported a 0×0 minimum-size hint and every final window remained inside the platform work
area.

**P14m8b1 — small-window Music Map tools: GREEN.** The Windows 1024×720 runner exposed
crushed optional route/journey controls once top-level growth was correctly prevented.
Those controls now reflow and use an internally scrollable tool region rather than enlarging
MainWindow. The full functional, desktop, Linux and package-smoke matrix is green.

**P14m8b2 — native state/work-area review: GREEN.** No code change was required. Native
artifacts confirm exact normal-geometry restoration after maximize on both macOS targets,
Windows and Linux; macOS remains clear of the menu bar/Dock, Windows remains above the
taskbar at the 737×518 small-window qualification size, and Linux remains inside the X11
1440×900 work area. No continuous clamp or window-manager override is needed.

**P14m8b3 — practical vertical resizeability: GREEN.** A second reproduced geometry defect
showed that a normal window could technically fit inside `availableGeometry` while consuming
its entire usable height, leaving the lower resize edge impractical to reach. Fresh/default
geometry already used a centered 90%-height policy; the vulnerable path was legacy or invalid
restored normal geometry. Recovery now leaves a one-time 24 px work-area inset, while geometry
saved by current Melodex is marked trusted so a user who deliberately chooses full-height
normal geometry is preserved. This is restore-time only: there is no live resize clamp or
maximum-height rule.

Native qualification confirms the application-generated normal window leaves vertical margin
and can then shrink vertically on every target: macOS ARM/Intel 620→520, Linux 620→520 and
Windows 518→445 on its 1024×720 work area. Major page navigation, Music Map transitions and
maximize/restore do not raise the top-level geometry or block subsequent vertical resizing.

**P14m8c — final merged-state geometry matrix: GREEN.** The final checkpoint branched
from the fully merged post-P14m8b3 `main` state and changed no production or test code.
The complete correctness, responsiveness, visual, startup, large-library, native desktop
geometry and Linux package/smoke matrix passed. Native artifacts again reported every
geometry assertion true on macOS ARM, macOS Intel, Windows x64 and Linux/X11: feature-stack
minimum 0×0, page navigation stable, Music Map build/hydration/tools stable, practical
vertical shrinking preserved, maximize/restore exact, and final geometry inside the current
usable work area.

Windows again qualified the constrained case at a 1024×720 work area: the application-generated
normal window was 962×648, the normal test window shrank from 737×518 to 737×445, and
maximize/restore returned exactly to 737×518. macOS ARM/Intel and Linux shrank 900×620 to
900×520 and restored exactly.

**P14m: COMPLETE.** The reproduced Music Map enlargement and full-height normal-window
resizeability defects are fixed and protected by automated/native regression coverage. No
P14m9 is planned; exotic window-manager certification remains out of scope.

### P14 endurance qualification — completed

P14m turns the short mixed-workload soak into a duration-based qualification. The same
12,700-track process remains alive while Melodex repeatedly navigates Albums/Artists/Tracks,
scrolls distant regions, applies and clears searches, resizes through several geometries,
and submits competing foreground/prefetch/background work. Retained-memory measurement
then runs after the latency phase so `tracemalloc` cannot distort the responsiveness gate.

The manual `P14 Endurance Qualification` workflow defaults to 30 minutes and a strict
100 ms rolling p99 event-loop budget. It also runs the P14 seek/playback-state/intent/
transition regression contracts and the Album Wall real-world probe. Pull-request CI keeps
the shorter 80-cycle soak with the existing 250 ms shared-runner ceiling.

Run the full local endurance gate with:

```bash
python scripts/fluid_soak_probe.py \
  --tracks 12700 \
  --duration-minutes 30 \
  --p99-gap-limit-ms 100 \
  --assert-contract \
  --output p14-endurance.json
```

Automated release targets are:

- no foreground stall above 500 ms and no 1 s blocker;
- rolling p99 event-loop gap below 100 ms in the strict endurance run;
- bounded background queue/worker counts;
- bounded album/artist/track presentation objects;
- stable retained Python memory;
- repeated search-clear and resize geometry remain stable;
- seek ownership, authoritative EOF/transition state and album playback semantics remain
  covered by deterministic playback regression tests.

### Post-P manual beta validation — non-blocking

Offscreen Qt cannot prove audible output, native WindowServer hit-testing, Dock/taskbar
bounds or the behavior of every real NAS/audio device. These checks remain useful during
normal beta testing, but they are **not** a Campaign P completion gate after l5a–l5d and
the full automated release matrix are green.

On a current packaged macOS build with a representative local/NAS collection:

1. play a local FLAC continuously while panning Album Wall, navigating My Music, rapidly
   searching/clearing, and leaving/returning to views whose covers and lyrics are cached;
2. maximize/restore, move the window near every screen edge, and live-resize from every
   edge/corner; confirm the bottom controls remain visible and the window never snaps back;
3. seek forward/backward repeatedly, use Previous/Next, allow a track to end naturally,
   and let several tracks of one album play in order with album crossfade off;
4. revisit cached artwork and lyrics, then exercise Music Map pan/search/Connections and
   confirm no view jumps or blank-cache flashes;
5. keep playback running throughout and fail the run for any beach ball, audible glitch,
   playback/UI divergence, clipped window, stale transport state or delayed input response.

Record Pass/Fail plus build/OS and a short screen recording for any failure. Export redacted
diagnostics after the run; P14 diagnostics must never contain media paths, track/album names,
URLs, credentials or other private collection content. Any issue found here is ordinary
post-P bug/backlog work unless it exposes a regression in an existing release gate.

## P14a is a baseline, not a victory condition

The first probe may fail current budgets. That is useful: it converts "the app beach
balls" into a measurable regression target. Later P14 stages tighten the same probe and
eventually make it a release gate.
