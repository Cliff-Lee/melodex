# Large-library scan benchmark

This benchmark exists because an external tester reported that Melodex 0.7.2
never recovered while adding a Synology NAS library containing approximately
12,700 FLAC files / 500 GB.

The purpose of this first campaign is **measurement and reproduction**, not to
change scan behaviour yet. The current implementation is intentionally still
synchronous so the next campaign can be measured against a known baseline.

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

The tests deliberately capture the current architecture: constructing a local
provider with saved roots performs the scan on the calling thread. In the
desktop application that caller is currently the UI/main thread.

Campaign 2 should change that behaviour. At that point the regression test
should be replaced with a test that proves slow scan work cannot block the Qt
event loop.

## Acceptance baseline for the later fix

The permanent stress case is:

> 12,700 FLAC files on network storage must be indexable without making the
> Melodex UI unresponsive.

A future implementation should also remain responsive when metadata reads are
slow, individual files are malformed, a directory is inaccessible, or the
network share becomes unavailable.
