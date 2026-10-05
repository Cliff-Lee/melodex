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

Record only non-sensitive structural diagnostics (disc number/track number counts and
ordering validity), and test ordinary, multi-disc, missing-number and malformed-tag
albums.

### P14k — Visible audio settings

Expose transition/normalization state so users can see whether Melodex is applying
audio behaviour. Do not imply ReplayGain or normalization when it is not enabled.

### P14l — Scan optimization

Only after interaction stability is green, revisit the approximately 13-minute first
scan. Preserve correctness and NAS safety while targeting much faster unchanged and
small-delta rescans.

### P14m — 30-minute endurance qualification

Run continuous playback while panning, searching, clearing search, resizing, navigating,
seeking, changing tracks and allowing natural ends.

Release target:

- zero beach balls;
- zero unintended audio glitches;
- zero playback/UI state divergence;
- no foreground stall above 500 ms;
- rolling p99 event-loop gap below 100 ms;
- bounded artwork/background queues;
- stable memory;
- reliable seeking;
- album playback preserves album semantics;
- window size and position remain under user control.

## Manual Mac qualification

The automated probe cannot verify the two most important native-only symptoms. On a
physical Mac, use the current packaged build and a representative large library:

1. start a local FLAC and keep it playing;
3. pan Album Wall continuously for at least two minutes;
4. jump between distant wall regions;
5. return to My Music and scroll rapidly;
6. search for an album and clear the search;
7. double-click the title bar to maximize;
8. resize from every edge/corner and move the window;
8. seek forward/backward repeatedly;
9. press Previous, then let that track finish naturally;
10. double-click an album and let several tracks play.

Export redacted diagnostics immediately after the run. P14 instrumentation must never
include media paths, track/album names, URLs, credentials, or other private collection
content.

## Manual UX qualification for instant, stable browsing

Use a current packaged build from the PR's desktop workflow and a local library with familiar
albums and lyrics. A NAS is not required for these UI checks. Keep the existing Melodex
profile and library; do not clear or re-import anything. Record the OS, build, screen
resolution, and a short screen recording if a failure appears.

1. In My Music, note the current Albums scroll position, search for an album you recognize,
   then clear the search. Confirm the result appears promptly, clearing does not freeze the
   window, the previous scroll position returns, and its familiar cover is already visible.
   Repeat once each in Artists and Tracks, including rapid edits and clearing.

2. Start playback, then resize the window smaller and larger from each available edge.
   Confirm the whole window, including the bottom controls, stays above the taskbar or dock.
3. Move the window near each screen edge, maximize it, restore it, and close/reopen Melodex.
   Confirm the window remains visible and its last useful size and position return.
4. Open Album Wall and scroll down several screens with the mouse wheel or trackpad.
   Drag the canvas down and sideways, pause, then continue. Confirm it stays at the chosen
   albums instead of jumping back to the top.
5. Leave Album Wall for My Music or Home and return. Confirm familiar covers are already
   visible as soon as the wall returns. Scroll away and back to check covers do not flash
   blank while the known artwork is being reused.
6. Open a track whose lyrics have loaded, move to another track, then return. Confirm the
   lyrics appear immediately on return. Allow a first-time lookup to finish before judging
   the revisit.
7. Open Music Map, resize the window, pan in several directions, and use the search and
   Connections controls. Confirm the labeled cards remain readable and the view does not
   jump after a refresh.
8. Keep playback running while repeating the navigation and resize steps. Check for audio
   interruption, a frozen window, clipped controls, or a delayed response to clicks.

For each step record Pass or Fail and the observed behavior. A failure report should include
the build and OS plus the recording; redact collection names, paths and other private
metadata from diagnostics. On macOS, include a live resize from every corner and edge,
because native live-resize behavior is not fully represented by automated checks.

## P14a is a baseline, not a victory condition

The first probe may fail current budgets. That is useful: it converts "the app beach
balls" into a measurable regression target. Later P14 stages tighten the same probe and
eventually make it a release gate.
