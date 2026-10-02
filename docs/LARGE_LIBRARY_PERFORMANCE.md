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

## P8c result — bounded background scheduler

P8c replaces Melodex's ad-hoc desktop worker creation with one shared priority scheduler.

The scheduler has **4 total worker slots** with one slot reserved for
foreground/visible work. Low-priority background, prefetch and idle tasks can therefore
occupy at most three slots at once.

Priority order:

1. foreground;
2. visible;
3. background;
4. prefetch;
5. idle.

Lane limits further bound resource contention:

- default: 4;
- disk/cache: 2;
- network: 2;
- analysis: 1;
- prefetch: 1;
- idle: 1.

The reserve is based on active low-priority jobs rather than total active jobs. If a
foreground job is already running, background work may still use otherwise free
capacity without counting the reserve twice.

P8c routes the generic async path, viewport artwork/photo cache reads, current-track
artwork, cached visual analysis/context, next-track prefetch and explicit online
artwork/photo recovery through this scheduler. The previous nested online artwork/photo
ThreadPoolExecutor paths and direct visual-analysis/context daemon threads are removed.

Library scanning remains process-isolated and independent.

The scheduler is observable through redacted diagnostics:

- active and pending job counts;
- active/pending jobs by lane and priority;
- submitted/completed/cancelled totals;
- queue high-water mark;
- maximum observed concurrency;
- configured lane limits and foreground reserve.

Task labels and user content are deliberately excluded from diagnostics.

The Fluid Melodex release gate verifies priority ordering, total worker bounds, lane
bounds, foreground-reserved capacity, cross-lane progress and MainWindow integration.

## P8d result — cancellation and stale-work elimination

P8d adds **latest-wins** cancellation to the bounded scheduler introduced in P8c.

Logical background jobs may carry a stable key such as `discover-search` or
`next-track-prefetch`. Replacing or explicitly invalidating that key:

- cancels older queued work before it starts;
- removes cancelled tasks from the scheduler heap immediately;
- marks already-running work stale without attempting unsafe thread termination;
- suppresses both late values and late errors from stale running work; and
- delivers only the newest logical result to Qt.

A synthetic burst of 50 rapid same-key submissions is required to keep both the
runnable pending count and physical queue high-water mark bounded to one replacement
slot while another worker is deliberately blocked.

P8d applies latest-wins semantics to:

- Discover search;
- next-track prefetch;
- current-track artwork;
- current-track cached analysis;
- Now Playing visual-context loads;
- Album Wall model rebuilds;
- Music Map model rebuilds;
- viewport album-artwork cache hydration; and
- viewport artist-photo cache hydration.

Existing UI sequence/generation checks remain in place as a second safety layer.

### Viewport and catalog invalidation

If the user scrolls while automatic cached artwork is in flight, the old logical batch
is invalidated immediately. Its in-flight keys are released so the new viewport can
request visible work straight away. If the old worker later finishes, its result is
suppressed.

Replacing the My Music catalog also invalidates any in-flight cached artwork work before
the browser swaps to the new model.

### Navigation invalidation

The existing P2 navigation generation already drops delayed page-population callbacks.
P8d extends that to safe background model work:

- leaving Album Wall invalidates an unfinished Album Wall model build;
- leaving Music Map invalidates an unfinished Music Map model build; and
- leaving Now Playing invalidates unfinished visual-context work.

### Prefetch invalidation

Scheduling a new next-track prefetch invalidates the old prefetch key immediately,
before the replacement's delay timer fires. A queue/track change therefore stops stale
speculative work from occupying the prefetch lane unnecessarily.

### Diagnostics

Redacted scheduler diagnostics now also expose:

- invalidation count;
- stale queued tasks actually cancelled; and
- stale running results/errors suppressed.

Logical task keys, track names, search text and paths are not exported.

The Fluid Melodex release gate verifies queue replacement, stale-result suppression,
stale-error suppression, bounded queue storage, real MainWindow callback suppression,
search latest-wins behavior, viewport artwork invalidation, catalog replacement,
prefetch invalidation and navigation cancellation.

## P8e result — sustained soak testing

P8e adds a deterministic endurance harness at `scripts/fluid_soak.py` and a dedicated
**Fluid Melodex soak (12.7k)** CI job. The soak uses a 12,700-track synthetic library
and repeatedly mixes real Qt view changes, scrolling, filtering, TrackRow hydration,
viewport-artwork invalidation and P8c/P8d scheduler churn.

The first version of the harness exposed an instrumentation problem rather than a
product leak: continuous `tracemalloc` plus manually pumping Qt without draining
`DeferredDelete` events produced artificial multi-gigabyte RSS growth. The harness was
corrected to drain deferred Qt deletions and to use lightweight retained-memory signals
(RSS, GC-tracked objects and allocated Python blocks).

With that corrected, the soak showed stable memory and scheduler behaviour but exposed
one real foreground defect: clearing a narrow My Music search back to the full library
was rebuilding too much synchronously.

Before the fix, 12,700-track clear-search p95 timings were approximately:

- Albums: **220 ms**;
- Artists: **228 ms**;
- Tracks: **224 ms**.

The root cause was twofold:

1. query changes relaid out hidden library views that the user could not see; and
2. narrow filters destroyed the normal first-page AlbumCard/ArtistCard widgets, so
   clearing the filter had to recreate up to 120 rich cards.

P8e now keeps a bounded hidden cache of the normal first-page album/artist cards while
a filter is active, reuses those exact widgets when the filter is cleared, and only
lays out the currently visible library view.

On the final 12,700-track soak:

- **240 cycles** completed in **22.6 s**;
- retained RSS grew only **6.0 MiB**;
- GC-tracked object growth was **38**;
- allocated Python blocks grew by **3,026**;
- cycle-time first-to-last-quarter median ratio was **1.027×**;
- scheduler queue high-water was **5**;
- **2,016** stale queued jobs were cancelled during deliberate churn;
- event-loop CI violations (≥250 ms): **0**;
- serious stalls (≥500 ms): **0**;
- release blockers (≥1 s): **0**;
- interaction p95: **57.6 ms**;
- interactions over 100 ms: **0**;
- event-loop p99 gap: **119.2 ms**;
- maximum event-loop gap: **126.7 ms**.

Clear-search p95 after the fix:

- Albums: **58.4 ms**;
- Artists: **54.3 ms**;
- Tracks: **16.2 ms**.

Other final p95 interaction timings included approximately 59 ms for Albums/Artists view
switches, 17 ms for Tracks, 23 ms or less for setting a narrow filter, and sub-millisecond
scroll acknowledgement.

The soak gate now enforces the existing Fluid Melodex interaction contract directly:
interaction p95 must stay below **100 ms**, with **zero interactions over 100 ms** in
this deterministic endurance scenario, in addition to its memory, backlog and
event-loop stability budgets.

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
