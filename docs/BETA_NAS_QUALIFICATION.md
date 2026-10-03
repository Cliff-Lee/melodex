# Campaign 11c — NAS / network beta qualification

Campaign 11c prepares Melodex for external testers with NAS, SMB, NFS and other
network-mounted music libraries.

It deliberately does **not** tune scanner internals. Campaign 10 owns the
elastic scanner engine and may still be changing queueing, indexing,
fingerprinting and metadata concurrency. Campaign 11c defines the user-facing
contract that the finished engine must satisfy.

## Why this campaign can run beside Campaign 10

The two campaigns have different ownership:

| Campaign | Owns |
| --- | --- |
| 10 | scanner/index implementation and scaling |
| 11c | repeatable stress scenarios, recovery behavior and beta acceptance |

That separation lets scanner work continue on one branch while beta-readiness
qualification evolves independently.

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
- the result marks at least one incomplete root;
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

When Campaign 10's scanner branch is ready, run this qualification harness
against that head before recruitment. If Campaign 10 changes implementation but
11c still passes, the user-facing resilience contract has remained intact.

If a Campaign 10 change breaks a 11c scenario, fix the scanner branch rather
than weakening the qualification rule unless the product behavior itself has
been intentionally redesigned.
