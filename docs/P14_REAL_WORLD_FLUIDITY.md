# P14 — Real-World Fluidity & Playback Integrity

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

Later P14l3 slices may reduce per-file work inside manifest-proven unchanged directories,
but only after P14l3a qualifies independently.

#### P14l4 — Persistence and catalog hydration

Optimize SQLite publication and the final post-commit catalog load without weakening the
single-transaction publication contract or increasing collection-scale memory duplication.

#### P14l5 — Physical 12.7k/NAS qualification

Run the resulting scanner against a representative physical 12.7k-track library and a NAS
profile. Compare cold import, unchanged rescan and small delta; verify cancellation, root
loss and restart behavior before P14l is considered complete.

### P14m — 30-minute endurance qualification

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

### Residual physical qualification — consolidated and deferred

Offscreen Qt cannot prove audible output, native WindowServer hit-testing, Dock/taskbar
bounds or the behavior of a real NAS/audio device. Those checks are deliberately kept as
one residual physical run rather than duplicated across P14 phases.

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
URLs, credentials or other private collection content.

## P14a is a baseline, not a victory condition

The first probe may fail current budgets. That is useful: it converts "the app beach
balls" into a measurable regression target. Later P14 stages tighten the same probe and
eventually make it a release gate.
