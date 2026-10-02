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
