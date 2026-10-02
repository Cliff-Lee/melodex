# Large-library performance campaign

Fluid Melodex P8 tests how the desktop application behaves when collection size becomes
large enough that background work, model building and widget creation can compete with
foreground interaction.

The governing rule is:

> Background work is allowed to be slow. Foreground work always wins.

P8 starts with measurement before changing scheduling behaviour.

## Synthetic profiles

The probe uses deterministic metadata-only catalogs. No audio files are created or opened.

| Profile | Tracks | Typical synthetic albums | Typical synthetic artists |
| --- | ---: | ---: | ---: |
| Small | 1,000 | 100 | 25 |
| Real tester scale | 12,700 | 1,270 | 318 |
| Stress | 50,000 | 5,000 | 1,250 |
| Extreme | 100,000 | 10,000 | 2,500 |

The defaults use 10 tracks per album and 4 albums per artist.

Run the full model-only probe:

    python scripts/large_library_probe.py

Run the real 12,700-track scenario with the actual Qt library browser:

    QT_QPA_PLATFORM=offscreen PYTHONPATH=desktop \
      python scripts/large_library_probe.py --tracks 12700 --gui

Run all four profiles through the actual browser when deliberately stress-testing a desktop machine:

    QT_QPA_PLATFORM=offscreen PYTHONPATH=desktop \
      python scripts/large_library_probe.py \
        --tracks 1000 12700 50000 100000 \
        --gui \
        --output large-library-full.json

CI runs the 1,000 and 12,700 GUI profiles and uploads large-library-baseline.json
as an artifact. The 50k and 100k GUI profiles are deliberate/manual stress runs so
ordinary pull requests do not become excessively slow.

## What P8a measures

The catalog baseline separates:

- synthetic-catalog construction;
- album model construction;
- album indexing;
- artist model construction;
- initial layout;
- artwork request scheduling;
- album filtering;
- artist filtering;
- whole-track filtering/sorting;
- view switching;
- number of heavyweight Qt widgets rendered;
- Python peak allocation during the model probe; and
- explicit album/track truncation.

A real Melodex diagnostics export also includes the most recent library catalog,
filter and view timings without media paths or search text. Only the search-query
length is recorded.

## Current hypotheses to test

P8a intentionally records rather than hides several likely scaling constraints:

1. My Music currently builds its album representation through
   build_album_wall(..., max_albums=4000). Collections above that album count can
   be sampled/truncated. P8a reports the exact number of albums and tracks excluded.
2. _apply_filter() currently prepares and sorts the full visible track list even
   when the user is browsing Albums or Artists.
3. initial catalog setup performs multiple layout/filter passes.
4. the current progressive card batches (120 albums, 120 artists, 300 tracks) bound
   widget count, but are not yet viewport-aware.
5. cached artwork requests are bounded to rendered items, but prioritisation should
   eventually follow the viewport rather than collection order.

P8a should establish which costs dominate before P8b changes architecture.

## First CI baseline

The first Ubuntu 22.04 offscreen Qt run is a directional baseline, not a
cross-machine benchmark.

For the 12,700-track profile (1,270 albums / 318 artists):

- LibraryBrowser catalog setup: about **0.31 s**.
- album model: about **0.12 s**.
- artist model: about **0.04 s**.
- initial layout: about **0.14 s**.
- switching to Artists: about **0.16 s** total.
- switching to Tracks: about **0.70 s** total.
- full 12,700-track filter/sort during the Tracks switch: about **0.017 s**.
- creating/layout of the first 300 TrackRow widgets: about **0.687 s**.
- no albums or tracks were truncated at this realistic 12,700-track shape.

The important finding is that the first Tracks view is dominated by heavyweight Qt row
creation rather than sorting the 12,700-track metadata. The 1,000-track profile showed
a similarly large fixed cost for creating 300 TrackRow widgets, reinforcing that this is
primarily a rendering-granularity problem.

Therefore P8b should begin with viewport-sized/virtualized Track rendering before
spending effort micro-optimising metadata sorting.

## P8b first result — virtualized Tracks

P8b replaced the Tracks QListWidget population path with a lightweight full
QAbstractListModel plus viewport-bounded rich-row hydration.

On the same 12,700-track CI profile:

- previous Tracks switch: about **0.705 s**;
- new shell + full 12,700-row model: about **0.017 s**;
- visible rich-row hydration: about **0.020 s**;
- rich TrackRow widgets created: **15**, rather than 300;
- approximate time to rich visible content: **0.037 s**.

This is roughly an **18× reduction** in the measured first-view cost. It also moves the
visible Tracks path from well above the 500 ms serious-stall threshold to inside the
preferred 50 ms interaction target on this directional CI run.

The full model still contains all 12,700 tracks, so the scrollbar represents the whole
collection immediately. Scrolling moves the hydration window and removes rich rows that
leave the buffered viewport rather than accumulating widgets indefinitely.

The Fluid Melodex release gate now includes this bounded-window regression.

## P8b2 result — viewport-first artwork

Automatic cached album artwork and artist-photo hydration now use the same foreground
priority rule as Tracks rendering.

On the 12,700-track CI profile, both Albums and Artists produced this initial split:

- **18 cards currently visible**;
- **12 cards in the next viewport**;
- **90 rendered cards currently distant**; and
- only **12 cached-image requests launched immediately**.

Previously the cache path could submit all 120 rendered cards in collection order.

The foreground batch is now capped at 12 and drains visible work before near work.
Distant hydration happens only after foreground work is exhausted, in idle batches
capped at 4 items.

Scrolling increments a generation token. Any previously scheduled idle callback from
the old viewport becomes stale and cannot launch distant work ahead of the new visible
region.

Cached artwork/photo lookup is also limited to one in-flight batch per kind. A cache
worker failure releases the guard and makes the failed keys eligible for a deferred
retry rather than blocking future viewport work.

The online **Find missing artwork / Get artist photos** operation remains separate. It
is an explicit user-requested long operation with its own bounded queue, progress and
pause/cancel behaviour.

## P8c result — bounded shared background work

Desktop async work now runs through one shared priority scheduler instead of creating an
unbounded daemon thread for every request.

The scheduler has five lanes:

- **foreground** — direct user actions such as search, play, resolver choices and prompts;
- **visible** — work needed to finish the page or current-track presentation;
- **prefetch** — speculative next-track work;
- **background** — long analysis, enrichment and online artwork recovery; and
- **idle** — work that can wait without affecting the current interaction.

The desktop pool is capped at **4 workers** and reserves **1 worker slot for foreground
work** whenever lower-priority jobs are active. Background, prefetch and idle lanes are
individually capped so a large analysis/enrichment/artwork burst cannot occupy the
whole pool. Cached viewport artwork remains in the visible lane, while explicit online
artwork recovery and library analysis use the background lane.

The scheduler also exports redacted diagnostics for active/pending counts by lane,
submitted/completed/failed totals, and peak concurrency. Static task names are not
included in diagnostics.

The Fluid Melodex gate now verifies that:

- visible work overtakes queued idle work;
- prefetch/background/idle work leaves a foreground slot available;
- background work is serialized rather than spawning freely; and
- scheduler diagnostics expose only bounded lane counts.

## P8d result — stale work stops mattering

P8c bounded the amount of background work. P8d now prevents superseded work from
remaining relevant after the user has moved on.

Replaceable async operations use a **latest-wins scope**. When a newer request with the
same scope is submitted:

- an older queued job is removed before it starts;
- an older job that is already running may finish safely, but its result/error is
  discarded instead of updating newer UI state; and
- diagnostics count both queued cancellations and stale completions that were dropped.

This is applied to the most interaction-sensitive paths, including:

- repeated Search requests;
- Album Wall and Music Map page-model builds;
- Play for Me, Flow planning, journey building and live journey replanning;
- local-intelligence suggestion refreshes;
- next-track prefetch;
- current-track artwork and taste-state hydration; and
- Now Playing visual analysis/context generation.

Navigation away from Album Wall, Music Map or Now Playing explicitly invalidates the
relevant pending page work. Track changes invalidate old current-track work immediately,
even when the new track can use prefetched data and therefore does not need to submit a
replacement job. Queue changes likewise invalidate old next-track prefetch before the
new debounce period begins.

Now Playing visual analysis and visual-context loading also use the shared P8c scheduler
instead of creating their own daemon threads.

The Fluid gate verifies both sides of the contract: queued work is genuinely cancelled,
and already-running stale work cannot apply its completion to the current UI.

## P8 campaign sequence

### P8a — Synthetic baseline

Create reproducible 1k / 12.7k / 50k / 100k profiles, expose truncation, and measure
catalog/filter/view costs.

### P8b — Viewport-first rendering

Replace fixed collection-order hydration with viewport priority. Visible cards and
their artwork should be first, then roughly one viewport ahead, then distant items.

### P8c — Bounded background scheduler

Introduce shared foreground/visible/prefetch/background/idle priorities and bounded
concurrency so artwork, metadata, analysis and enrichment cannot overwhelm the
application simultaneously.

### P8d — Cancellation and stale-work elimination

When users scroll, filter, navigate, change tracks, or replace a queue, obsolete work
should be cancelled or deprioritised rather than finishing in the background.

### P8e — Soak tests

Exercise large synthetic libraries alongside playback, scans, scrolling, searches,
page switches and queue changes. Watch for event-loop stalls, growing work queues,
runaway memory, stale jobs and performance degradation over time.

## Success criterion

A 12,700-track library does not need to finish every background operation as quickly as
a 500-track library. It should, however, remain comparably responsive to user input.

Large-library work must continue to obey the Fluid Melodex release contract:
interaction acknowledgement remains immediate, the UI stays usable, and slow work does
not monopolise the foreground.
