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
2. album search followed by clear-search expansion;
3. repeated Album Wall viewport moves;
4. visible artwork application;
5. repeated My Music resize cycles;
6. event-loop and interaction latency collection.

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

Add explicit playback intent such as:

- album;
- playlist;
- journey;
- manual queue;
- radio/provider.

Album playback defaults to disc/track order with no Journey crossfade. Flow transitions
remain available for Journey listening.

### P14f — Album Wall render hot path

Decode/crop/scale artwork outside paint. During active movement, favour immediate
motion over refinement and defer expensive visual work until the viewport settles.

### P14g — Shared artwork service

Centralise decoded/rendered artwork caching, request deduplication, viewport priority,
generation cancellation, memory budgeting and negative caching.

### P14h — My Music filtering/layout

Precompute search keys, compute only the active view, reuse card widgets and diff
layout membership rather than clearing/rebuilding grids during every filter change.

### P14i — Native macOS resize behaviour

Debounce expensive relayout during live resize and remove child geometry feedback that
can force top-level window size/position.

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
2. pan Album Wall continuously for at least two minutes;
3. jump between distant wall regions;
4. return to My Music and scroll rapidly;
5. search for an album and clear the search;
6. double-click the title bar to maximize;
7. resize from every edge/corner and move the window;
8. seek forward/backward repeatedly;
9. press Previous, then let that track finish naturally;
10. double-click an album and let several tracks play.

Export redacted diagnostics immediately after the run. P14 instrumentation must never
include media paths, track/album names, URLs, credentials, or other private collection
content.

## P14a is a baseline, not a victory condition

The first probe may fail current budgets. That is useful: it converts "the app beach
balls" into a measurable regression target. Later P14 stages tighten the same probe and
eventually make it a release gate.
