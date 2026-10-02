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
