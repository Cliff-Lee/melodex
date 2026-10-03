# Campaign 10 — Elastic Library Engine

Campaign 10 extends the responsiveness work from P8/P9 from the current
12,700-track stress case toward collections containing hundreds of thousands or
even one million files.

The objective is **not** to make every user pay for a million-file design.
Melodex should use the same core architecture at every scale while keeping
optional large-library machinery cheap or inactive for ordinary collections.

## P10 contract

1. Small libraries must not materially regress while huge-library paths improve.
2. User interaction remains the priority: p95 acknowledgement target stays below 100 ms.
3. Playback and navigation never wait for scanning, artwork, analysis or online enrichment.
4. Scan workers, queues and in-flight state must remain bounded.
5. Unchanged files must not reread metadata.
6. Work should scale with the changed portion of a library whenever possible.
7. An unavailable/incomplete NAS must never be interpreted as mass deletion.
8. A million-file library must not imply a million UI widgets.
9. Optional artwork/analysis/enrichment remains independent of the core index.
10. Optimizations must preserve correctness; a fast scanner that misses changes fails.

## Existing foundation

Campaign 10 starts from a stronger base than the original 12,700-FLAC report.
Melodex already has:

- persistent SQLite indexing;
- size + mtime fingerprints;
- unchanged-file metadata reuse;
- zero-row rewrites for unchanged indexed tracks;
- preservation of cached data when NAS roots are unavailable or incomplete;
- a disposable scan process for hard NAS cancellation;
- lazy cached-catalog hydration;
- progressive/virtualized large-library UI rendering;
- bounded priority scheduling and latest-wins cancellation for UI/background work.

P10 therefore does **not** reimplement those features.

## Current scaling risk

The current scanner intentionally builds a complete atomic snapshot before
publishing it. During a scan it holds several collection-wide structures,
including:

- `discovered`;
- `tracks`;
- `index_tracks`;
- `index_records`; and
- sets used to detect removals.

That model has excellent simple correctness properties at 12.7k tracks, but its
working set grows with the complete library. P10 must quantify that growth
before changing it.

## P10a — baseline matrix and contracts

P10a adds a multi-scale benchmark around the current real scanner:

```bash
cd desktop
python tools/profile_library_scale_matrix.py
```

Default profiles:

- 500
- 5,000
- 12,700
- 50,000
- 100,000 tracks

The expensive release qualification sizes are deliberately opt-in:

```bash
python tools/profile_library_scale_matrix.py --release-scale --json
```

which appends:

- 250,000
- 500,000
- 1,000,000

The probe records total scan time, throughput, metadata reads, directories/files
visited, and retained/peak Python memory.

The one-million case is not a normal PR gate yet. P10a exists to measure the
current architecture and prevent us from optimizing by guesswork.

## Regression matrix

Different scales have different jobs:

| Tracks | Role |
| ---: | --- |
| 500 | small-library regression guard |
| 5,000 | normal enthusiast library |
| 12,700 | current MusicHoarder stress case |
| 50,000 | scaling transition |
| 100,000 | large-library engineering profile |
| 250k / 500k / 1m | opt-in release/architecture qualification |

Small-library performance is a first-class gate. Future P10 changes should be
rejected if they buy large-library throughput by materially degrading 500/5k
behavior.

## Planned stages after P10a

- **P10b — streaming discovery:** stop requiring a complete discovery list before downstream work can proceed.
- **P10c — bounded pipeline/backpressure:** explicit bounded buffers between discovery, metadata and persistence.
- **P10d — database writer/batch tuning:** measure transaction size and publication cadence rather than guessing.
- **P10e — progressive catalog publication:** committed batches become searchable/browsable while indexing continues.
- **P10f — directory fingerprints:** safely skip unchanged subtrees where filesystem semantics permit it.
- **P10g — adaptive storage concurrency:** tune SSD/HDD/NAS work without hard-coding another application's worker count.
- **P10h — deletion/offline correctness:** generation/checkpoint semantics for interruption and disappearing shares.
- **P10i — 100k/1m qualification:** memory, throughput, cancellation, restart, delta rescan and NAS-failure stress tests.
- **P10j — permanent scale gates:** lightweight PR profiles plus larger scheduled/release profiles.

The design rule for the whole campaign is:

> Library size may change how long background completion takes; it should not
> fundamentally change how Melodex feels to use.


## P10b — streaming discovery result

P10b removes the collection-wide discovery list from the local scanner.

Before P10b, a scan first accumulated every discovered audio file and its
fingerprint into a `discovered` list. Only after traversal completed did
Melodex read changed metadata and construct the final snapshot structures.

P10b changes that flow to:

```text
walk filesystem
  ↓
fingerprint one audio file
  ↓
reuse cached metadata or read tags immediately
  ↓
append final snapshot row
  ↓
continue walking
```

This removes one complete O(n) copy of per-file discovery state and starts
metadata work before traversal finishes.

The completed scan is still atomic. Melodex does **not** progressively mutate
the live catalog in P10b. If a root reports a traversal error, all rows produced
for that root during the current scan are discarded and its previously indexed
SQLite snapshot is preserved.

Streaming progress now supports an unknown denominator while discovery is
still running. The UI reports tags read so far rather than falsely claiming
metadata is already up to date.

P10b also records:

- `streaming_discovery: true`
- `discovery_buffer_rows: 0`

in scan metrics, making the new invariant testable.

The remaining large-memory structures are the final atomic snapshot itself
(`tracks`, `index_tracks`, and `index_records`). Reducing those safely is
reserved for the bounded-pipeline/database-writer stages rather than combining
multiple architectural changes into one PR.


## P10c — bounded discovery/metadata pipeline

P10c introduces an explicit bounded producer/consumer handoff between
filesystem discovery and metadata processing.

The scanner now runs discovery in a dedicated producer thread and places
discovered audio-file work into a fixed-capacity queue. Metadata processing
consumes from that queue on the scan worker side.

The important invariant is:

```text
pending discovery work <= queue capacity
```

When the queue fills, discovery waits. It cannot continue accumulating an
arbitrarily large backlog in memory.

Current queue capacity is 256 rows. Diagnostics record:

- `bounded_pipeline`
- `pipeline_queue_capacity`
- `pipeline_max_queue_depth`
- `pipeline_backpressure_events`

This stage deliberately keeps the final atomic snapshot model. The bounded
queue controls in-flight discovery work, while `tracks`, `index_tracks`, and
`index_records` still grow with the completed library until P10d/P10e move
persistence/publication further into the pipeline.

Correctness rules are unchanged:

- incomplete roots discard rows produced during the current scan;
- unavailable roots preserve their previous indexed copy;
- cancellation publishes no partial catalog;
- unchanged fingerprints still avoid metadata reads; and
- live UI/catalog replacement occurs only after a successful completed scan.


## P10d — bounded SQLite index writer

P10d bounds the temporary SQLite write/delete parameter buffers without giving
up scan atomicity.

Before P10d, each root accumulated every changed row into one `write_rows`
list and then passed the complete list to SQLite `executemany()`. Very large
changed imports therefore created another collection-scale temporary structure
on top of the scan snapshot.

P10d writes and deletes in fixed-size batches. The default is 250 rows:

```text
scan snapshot
  ↓
250 rows → SQLite
250 rows → SQLite
250 rows → SQLite
...
  ↓
single COMMIT
```

All batches remain inside one `BEGIN IMMEDIATE` transaction. A cancellation
or failure after any batch rolls back the complete transaction, so a partially
written library is never published.

The index result now reports:

- `batch_size`
- `write_batches`
- `delete_batches`
- `max_batch_rows`

The batch size is explicitly tunable for measurement:

```bash
cd desktop
python tools/profile_library_index.py --tracks 12700 --batch-size 250
python tools/profile_library_index.py --tracks 12700 --batch-size 500
```

The default 250-row batch is intentionally conservative until benchmark data
shows a better cross-platform choice. This stage does not perform multiple
database commits: throughput optimization must not weaken rollback semantics.

P10d removes the old all-changed-rows `write_rows` buffer, but the completed
scan snapshot itself is still collection-sized. The next persistence stage can
use this bounded writer as the foundation for progressively feeding SQLite
instead of retaining `tracks`, `index_tracks`, and `index_records`
simultaneously for very large libraries.


## P10e — single-snapshot isolated scanning

P10e removes the largest remaining duplicate structures from the real GUI scan
path without weakening the existing atomic persistence contract.

Previously the isolated scan child built three collection-sized representations:

- `tracks`
- `index_tracks`
- `index_records`

The child only needed one of those sets to persist the scan. After persistence it
loaded the completed catalog from SQLite anyway.

The isolated production path now calls the scanner in persistence-only mode:

```text
bounded discovery queue
  ↓
index_records only
  ↓
batched atomic SQLite transaction
  ↓
release index_records
  ↓
load completed catalog from SQLite
  ↓
send final tracks to GUI
```

This means the scan child no longer simultaneously retains raw persistence rows,
a second raw metadata list, and an override-applied UI list for the full library.

Compatibility callers can still request the in-memory `tracks` result by using
the scanner's default mode. The GUI/disposable-process path explicitly disables
that duplicate copy.

New scan telemetry records:

- `collect_tracks`
- `snapshot_track_copies`

For the production isolated scan path, `snapshot_track_copies` is 1 during the
scan phase.

P10e deliberately does **not** commit partial batches while traversal is still in
progress. The successful scan remains one atomic transaction, so cancellation,
an incomplete NAS root, or a worker crash cannot publish a partial library.

The remaining collection-scale memory is now primarily:

- the persistence record set needed for the atomic commit; and
- the final catalog loaded after that commit.

Those two phases are sequential rather than intentionally retained together.
Future stages can focus on folder/subtree fingerprints, adaptive storage
concurrency and release-scale qualification instead of carrying multiple
full-library Python snapshots.
