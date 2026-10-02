# Large-library scan benchmark

This benchmark exists because an external tester reported that Melodex 0.7.2
never recovered while adding a Synology NAS library containing approximately
12,700 FLAC files / 500 GB.

Campaign 1 established the measurement baseline. Campaign 2 moves application
library scans off the Qt UI thread while preserving the same path-free metrics,
so before/after behaviour can be compared directly.

## What the probe measures

The local scanner now records path-free metrics for:

- roots checked / unavailable roots
- directories and files visited
- audio files discovered
- metadata reads attempted
- time spent inside metadata extraction
- remaining scan time
- total scan time
- whether the scan ran on Python's main thread

No root, directory or filename is stored in these metrics.

The My Music catalog also records timings for:

- clearing the previous view
- copying the incoming catalog
- building the album model
- building the artist model
- initial Qt layout
- initial artwork/cache requests

These measurements are included in **Export diagnostics** and are filtered
through an explicit allow-list so private paths cannot leak into the export.

## Synthetic 12,700-track probe

The probe exercises the real `LocalFilesProvider.scan()` loop without creating
12,700 audio files or touching a real music collection.

From `desktop/`:

```bash
python tools/profile_library_scan.py
```

The default represents 12,700 FLAC entries with no artificial network delay.

To model latency from a NAS, for example:

```bash
python tools/profile_library_scan.py \
  --tracks 12700 \
  --metadata-delay-ms 2 \
  --directory-delay-ms 5
```

Use smaller values while iterating quickly:

```bash
python tools/profile_library_scan.py \
  --tracks 1000 \
  --metadata-delay-ms 5
```

Machine-readable output:

```bash
python tools/profile_library_scan.py --json
```


## Synthetic My Music UI probe

Scanning is only one possible bottleneck. After a catalog is returned, My Music
also builds album/artist models and Qt widgets. Profile that separately:

```bash
python tools/profile_library_catalog.py --tracks 12700
```

To measure the cost of constructing the current Tracks view:

```bash
python tools/profile_library_catalog.py \
  --tracks 12700 \
  --view tracks
```

The output reports model-building time, initial layout time, the number of real
Qt widgets created, and the additional time required to switch views. This is
intended to expose a second scalability problem independently of NAS I/O.

## Regression tests

```bash
pytest tests/test_library_scan_metrics.py tests/test_diagnostics.py -q
```

Direct `LocalFilesProvider` callers can still request a synchronous scan for
compatibility, but `ProviderManager` no longer scans saved roots during
application construction. The desktop schedules saved-root scans only after the
Qt window has been built, and the filesystem/tag work runs on a worker thread.

The regression suite now includes a deliberately blocked scan plus a Qt timer.
The timer must fire while the scan worker is still blocked, proving that slow
NAS work cannot monopolise the event loop. It also verifies that changing roots
mid-scan discards the stale result and queues a fresh scan.

## Acceptance baseline for the later fix

The permanent stress case is:

> 12,700 FLAC files on network storage must be indexable without making the
> Melodex UI unresponsive.

A future implementation should also remain responsive when metadata reads are
slow, individual files are malformed, a directory is inaccessible, or the
network share becomes unavailable.


## Campaign 2 architecture

Application scans now use a snapshot/apply split:

```text
Qt UI thread
  |
  | configure roots (fast, no filesystem traversal)
  v
worker thread
  |
  | enumerate directories + read Mutagen metadata
  v
scan snapshot { tracks, metrics }
  |
  v
Qt UI thread
  |
  | atomically apply completed snapshot
  v
refresh My Music
```

This matters because the live catalog is not progressively mutated from a
worker thread. Users can keep interacting with the existing catalog while a
rescan is in progress, and a root change during a scan cannot overwrite the
newer configuration with stale results.

Progress, pause and cancel controls are intentionally left to Campaign 3.
Persistent startup indexing is intentionally left to Campaign 4.


## Campaign 2 acceptance checks

- opening Melodex with saved NAS roots must paint the main window before scanning starts
- a deliberately blocked metadata read must not stop Qt timers or navigation
- Add music and Rescan must return control to the UI immediately
- completed worker results are applied only after the scan finishes
- a root change during an active scan must discard the stale snapshot and scan the new roots
- scan metrics from application-initiated scans must report `main_thread: false`


## Campaign 3 — visible, controllable indexing

Long scans must now look like deliberate background work rather than a frozen
application.

The My Music panel has two stages:

1. **Discovering files** — the total is not known yet, so progress is
   indeterminate while Melodex counts audio files.
2. **Reading metadata** — once discovery completes, the panel shows an exact
   `completed / total` count.

The panel also states explicitly:

> Melodex indexes music where it already lives. Audio files are never copied.

Pause and Cancel are cooperative. The scanner checks them between directory,
file and metadata operations. Cancelling never applies a partial catalog: the
previous library remains active.

A network filesystem call that is already blocked inside the operating system
cannot always be interrupted by a Python thread. Hard cancellation of that
pathological case is deliberately reserved for the later NAS-hardening campaign,
where scanning can be isolated in a killable worker process.

### Campaign 3 acceptance checks

- discovery shows a live count without inventing a percentage
- metadata parsing shows an exact count once the denominator is known
- Pause stops new scan work and Resume continues it
- Cancel discards partial results and preserves the previous catalog
- only a filename/basename may appear in progress events, never a full library path
- the panel always explains that Melodex does not copy the user's audio


## Campaign 4 — persistent library index

A successful library scan is now cached in a local SQLite metadata index:

`library-index.sqlite3`

The index contains track metadata and path references only. Melodex does **not**
copy audio files into Application Support.

### Startup behaviour

After a root has completed one successful scan:

```text
Launch Melodex
  ↓
read library-index.sqlite3
  ↓
library is available immediately
  ↓
no automatic NAS traversal
```

This remains true when the NAS is disconnected. Cached albums/tracks can still
be browsed; playback naturally depends on the original file becoming available.

Existing users with configured music roots but no index get one background
migration scan. A successfully scanned empty folder also counts as indexed, so
Melodex does not repeatedly rescan it on every launch.

### Scan commit behaviour

Completed scans use this sequence:

```text
background filesystem scan
  ↓
background SQLite transaction
  ↓
merge cached metadata for any unavailable roots
  ↓
apply the completed catalog on the Qt thread
```

A failed/cancelled scan never replaces the persistent index. If a previously
indexed NAS root is temporarily unavailable, its cached tracks are preserved
rather than being interpreted as deleted.

Melodex metadata corrections remain separate from the raw indexed file tags.
That means a correction can be removed later without having permanently baked
it into the cached file metadata.

### Persistent-index benchmark

The synthetic benchmark writes and reopens the permanent 12,700-track stress
case without touching a real music collection:

```bash
cd desktop
python tools/profile_library_index.py --tracks 12700
```

Use `--json` for machine-readable timings. The important startup number is
`read_seconds`: this is the metadata load that replaces a NAS traversal on
normal launches.

### Campaign 4 acceptance checks

- a previously indexed 12,700-track library opens from SQLite without walking the NAS
- startup works with the indexed NAS completely offline
- indexed roots do not automatically rescan on launch
- pre-index upgrade users receive one background migration scan
- a successfully scanned empty root is considered ready
- SQLite persistence runs off the Qt UI thread
- unavailable roots preserve their previously cached tracks
- metadata corrections apply on top of cached raw tags
- the SQLite index stores metadata/path references, never audio bytes

File size/mtime based incremental rescanning is intentionally Campaign 5. The
schema already reserves nullable `size` and `mtime_ns` columns so that work
can be added without redesigning the cache format.


## Campaign 5 — incremental rescanning

A normal Rescan no longer means reopening every audio file.

For each discovered audio file Melodex compares:

```text
file size + modification time
```

with the fingerprint stored in `library-index.sqlite3`.

If both values match, Melodex reuses the previously indexed raw metadata and
does not reopen the file with Mutagen. Only new or changed files need full tag
reads.

A completed rescan reports four useful outcomes:

- **unchanged** — fingerprint matched; cached tags reused
- **new** — file was not present in the previous index
- **updated** — path existed but its fingerprint changed
- **removed** — cached file was not found during a successful enumeration

Removal has an important safety condition: a file is only considered removed
when its root was positively available. An offline NAS is never treated as an
empty library.

### Upgrade behaviour

Indexes created before Campaign 5 already contain metadata, but their
`size`/`mtime_ns` fields are null. Those files are deliberately refreshed
once so Melodex can establish trustworthy fingerprints. Subsequent unchanged
rescans can then reuse all of their metadata.

### 12,700-track incremental benchmark

From `desktop/`:

```bash
python tools/profile_incremental_rescan.py --tracks 12700
```

The benchmark creates tiny placeholder files, performs a full first scan,
persists the fingerprints, and immediately repeats an unchanged scan. The key
result is:

```text
Rescan metadata reads: 0
Metadata reused:       12,700
Index rows rewritten:  0
```

Use a simulated tag-read cost to make the avoided work more visible:

```bash
python tools/profile_incremental_rescan.py \
  --tracks 12700 \
  --metadata-delay-ms 1
```

### Campaign 5 acceptance checks

- an unchanged fingerprinted 12,700-track library performs zero Mutagen tag reads
- an unchanged rescan rewrites zero track rows in the SQLite index
- changing one file causes exactly one metadata read
- adding one file causes exactly one new metadata read
- files removed from an available root disappear after a successful rescan
- an unavailable root never loses cached tracks
- legacy cache rows without fingerprints are refreshed once, then become reusable
- progress distinguishes files discovered from files whose metadata actually needs reading
- diagnostics report aggregate incremental counts without exposing filenames or paths


## Campaign 6 — disposable NAS scan process

Background threads keep the Qt event loop responsive, but they cannot safely
interrupt every operating-system filesystem call. A network share can strand a
thread inside `stat`, `scandir`, or a metadata read long after the user has
pressed Cancel.

GUI-initiated library scans now run in a dedicated child process:

```text
Melodex GUI
  |
  | JSON request + pause/resume/cancel controls
  v
disposable scan process
  |
  | walk roots + stat files + read changed tags
  | update library-index.sqlite3 transactionally
  v
JSON result
  |
  v
Melodex GUI applies completed catalog
```

Cancel is cooperative first. If the worker does not exit promptly, Melodex
terminates the entire scan process. The GUI, playback state and previously
loaded library remain alive.

This also makes application shutdown deterministic: a live scanner is
terminated before the rest of the desktop services are closed.

### Frozen-build coverage

The existing PyInstaller child-process smoke test now launches the built-in
library scanner as well as an external provider/plugin child. This specifically
checks that macOS and Windows packaged builds can re-enter the Melodex
executable in scan-worker mode before Qt starts.

### Campaign 6 acceptance checks

- a normal scan completes through the isolated child process and persists the index
- progress still reaches the Qt UI while the scan is isolated
- Pause/Resume controls are forwarded without blocking the GUI
- cooperative Cancel keeps the previous live catalog
- a deliberately unresponsive worker is forcibly terminated within a bounded time
- changing roots stops the stale scan and queues the new root set
- closing Melodex terminates a live scan worker
- packaged macOS and Windows builds pass the frozen scan-child smoke test


## Campaign 7 — progressive My Music rendering

Indexing 12,700 tracks is not enough if the GUI then creates thousands of Qt
widgets in one pass. My Music now keeps the complete album/artist/track models
in memory while rendering only a bounded working set.

Initial render windows are:

- 120 album cards
- 120 artist cards
- 300 track rows

Albums and Artists expose **Show more** controls. Tracks add a lightweight
footer row that loads the next batch without rebuilding the rows already on
screen. Search resets the working window and filters the complete model, so a
track outside the first 300 results is still immediately searchable.

Card widgets that fall outside the current filtered render window are destroyed
rather than accumulating invisibly. Artwork/cache work is also limited to the
currently rendered album/artist window.

The existing synthetic UI benchmark exercises this directly:

```bash
cd desktop
python tools/profile_library_catalog.py --tracks 12700
python tools/profile_library_catalog.py --tracks 12700 --view artists
python tools/profile_library_catalog.py --tracks 12700 --view tracks
```

The important distinction is between the full model counts and the widget
counts. A 12,700-track catalog should still report all tracks in the model while
the initial widget counts remain bounded.

### Campaign 7 acceptance checks

- the Albums model may contain thousands of albums while at most 120 cards are created initially
- Artist cards are not created until the user opens Artists, then start at 120
- opening Tracks creates at most 300 `TrackRow` widgets initially
- **Show more** expands only on explicit user request
- searching the full catalog works even when the match was outside the original render window
- changing a search drops no-longer-visible card widgets instead of retaining them indefinitely
- artwork/cache requests are scoped to rendered albums/artists rather than the whole library


## Campaign 10 — permanent large-library acceptance

The original 12,700-FLAC Synology case is now a dedicated CI acceptance gate.

`desktop/tools/verify_large_library_readiness.py` runs four existing probes at
the permanent **12,700-track** scale and fails if any correctness/scalability
invariant regresses:

- initial scan indexes all 12,700 synthetic tracks;
- the persistent SQLite index reloads all 12,700 tracks and remains ready;
- an unchanged rescan performs **zero metadata reads**;
- an unchanged rescan rewrites **zero SQLite track rows**;
- all 12,700 metadata records are reused;
- the My Music model retains all 12,700 tracks;
- Albums initially creates at most **120** cards;
- Tracks initially creates at most **300** rows.

Timing values are recorded in the artifact for trend comparison but are not
hard CI thresholds because hosted-runner performance varies.

The same workflow also reruns the isolated scan-process tests, including forced
termination of a deliberately hung worker.

For the external NAS retest procedure, see
[LARGE_LIBRARY_BETA_RETEST.md](LARGE_LIBRARY_BETA_RETEST.md).
