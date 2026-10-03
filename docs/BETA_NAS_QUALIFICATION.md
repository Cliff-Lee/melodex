# Campaign 11c–11d — NAS resilience and beta qualification

Campaign 11 prepares Melodex for external testers with NAS, SMB, NFS and other
network-mounted music libraries. Campaign 10 established the scalable library
engine; Campaign 11 now hardens that engine against real network-storage
failure modes and defines the user-facing acceptance contract.

| Stage | Owns |
| --- | --- |
| 11c | repeatable offline/reconnect/cancellation qualification |
| 11d | bounded transient-I/O retry and fail-safe NAS traversal |

The qualification harness is intentionally small and deterministic. Real SMB/NFS
latency, server firmware and mount behavior still require external beta testing.


## Campaign 11d hardening

The v0.7.9 scanner already isolates filesystem work from the GUI and preserves
unavailable/incomplete roots. P11d adds a conservative network-I/O layer:

- root preflight, directory enumeration and audio-file stat operations get two
  short retries (50 ms then 150 ms) before being treated as failed;
- recovered retries are counted in scan metrics for diagnostics;
- exhausted directory/stat failures mark the root incomplete, so the previous
  committed SQLite catalog remains authoritative instead of publishing a
  partial network view;
- production scandir traversal no longer performs a network `stat()` for
  non-audio sidecars such as cover images, cue sheets and text files;
- cancellation remains bounded because all traversal still runs in the
  disposable scan worker.

The retry budget is intentionally small. Melodex should absorb momentary SMB/NFS
hiccups, not hide a genuinely disconnected or unhealthy share for minutes.

## Automated NAS qualification harness

From `desktop/`:

```bash
python tools/qualify_nas_beta.py
```

The default creates 100 tiny valid WAV files in a temporary synthetic
"NAS" tree. It never touches the user's real library.

Machine-readable output:

```bash
python tools/qualify_nas_beta.py --json
```

A larger local qualification run:

```bash
python tools/qualify_nas_beta.py --tracks 1000
```

This is not intended to impersonate real SMB/NFS latency. It verifies the
failure/recovery contract around the isolated scan worker. Real-network latency
and scale remain external-beta test cases.

## Scenarios

### 1. Initial isolated scan

Pass conditions:

- scan completes in the disposable worker;
- all synthetic tracks are indexed;
- progress includes discovery, metadata and saving;
- no scan error is reported.

### 2. NAS becomes unavailable

After a successful scan, the synthetic root is renamed so the configured path
is unavailable.

Pass conditions:

- the rescan completes without destroying the index;
- previously cached tracks remain available;
- the result explicitly reports at least one unavailable root;
- SQLite persistence reports that unavailable root without replacing it;
- an unavailable root is not treated as an empty/deleted library.

This is the most important data-safety rule for real NAS testers.

### 3. NAS reconnects

The root is restored and scanned again.

Pass conditions:

- the full track count returns;
- the scan reaches persistence normally;
- no manual database repair is needed.

### 4. Network worker hangs

A deliberately unresponsive child worker simulates a filesystem call that never
returns.

Pass conditions:

- Cancel is cooperative first;
- the supervisor hard-terminates the worker if necessary;
- cancellation completes within the configured bound;
- the GUI process would remain independent of the stuck worker.

The default bound is 2.5 seconds:

```bash
python tools/qualify_nas_beta.py --cancel-limit-seconds 2.5
```

## Real NAS beta matrix

The automated harness is only the pre-flight gate. External testers should then
cover the environments we cannot faithfully synthesize in CI:

| Case | Minimum evidence |
| --- | --- |
| SMB share | scan + rescan + playback |
| NFS mount | scan + rescan + playback |
| Synology/QNAP/TrueNAS/Unraid | platform + protocol + library size |
| 50k+ tracks | scan completion + diagnostics |
| 100k+ tracks | scan completion + UI responsiveness |
| temporary disconnect | cached library preserved |
| reconnect | subsequent rescan reconciles correctly |
| slow NAS | navigation/playback remain responsive while indexing |
| malformed tags | scan continues and reports aggregate failures |
| app restart after interruption | previous committed index remains usable |

## Beta acceptance contract

Before actively recruiting r/selfhosted NAS testers, Melodex should satisfy all
of these:

1. **No destructive offline interpretation.** A missing NAS never means "delete
   everything".
2. **Previous committed library remains usable** while a rescan is running,
   cancelled or fails.
3. **Cancel has a bounded escape hatch.** A stuck worker cannot strand the main
   application indefinitely.
4. **Progress is honest.** Discovery does not invent a percentage before a
   denominator exists.
5. **The UI remains usable during indexing.** Navigation and playback are not
   coupled to network traversal.
6. **Diagnostics are easy to export** and contain aggregate scan state without
   paths, filenames or secrets.
7. **Reconnect is recoverable by ordinary rescan**, not database surgery.

## Relationship to Campaign 10

Campaign 10 is now the released v0.7.9 Elastic Library Engine. Campaign 11 runs
on top of that implementation. A NAS-hardening change must preserve the
permanent Campaign 10 scaling gates as well as the Campaign 11 resilience
contract; neither set of tests should be weakened to make the other pass.
