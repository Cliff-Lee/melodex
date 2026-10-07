# P13a — Time-to-first-music instrumentation

The first-music timeline records content-free event names, elapsed milliseconds and
integer source/play attempt IDs. It never records paths, filenames, tags, URLs, provider
configuration or exception text. The Sources page's **Export redacted diagnostics…**
action includes the timeline under `performance.first_music`.

The timeline measures:

- process start → visible shell and cached library;
- source selection → first directory result, first audio filename discovery, first
  playable track, first visible track and scan completion; and
- play request → decoder-ready status and first advancing playback position.

The scanner streams progress counts and provisional paths to the UI while the worker is
running. The player can queue those paths before the permanent library model is
populated by the full scan result. `source_probe_finished` marks acceptance of the first
provisional path; for an empty source, it marks scan completion. The difference between
`first_audio_file_discovered` and `first_track_visible` exposes discovery-to-player/UI
handoff time.

Qt Multimedia does not expose a hardware loopback signal for the first audible sample.
`first_audio_output` therefore means the first positive playback-position advance while
the player reports `PlayingState`; it is a consistent playback-start proxy, not proof
that speakers produced sound. `decoder_started` means Qt reported `LoadedMedia` or
`BufferedMedia`. `artwork_enrichment_finished` records the first library artwork batch
being applied, not completion of every artwork lookup in the collection.

The exported snapshot is a rolling in-memory trace for the current app session, capped
at 500 events. It is diagnostic evidence, not a benchmark result. P13o will add repeatable
local/NAS journeys and calibrated audio-output fixtures.

## Initial scanner-only baseline

`desktop/tools/qualify_first_music_discovery.py` drives the real scanner against the
existing virtual filesystem used by P10. These timings were captured in the Linux
execution environment on 2026-10-07. They isolate discovery and provider readiness;
they do **not** measure the Qt interface, decoder, audio device or audible output.
These are single-run observations with visible scheduler/cache variance, not CI limits;
repeatable distributions belong in P13o.

| Scenario | First directory | First audio filename | First provider-ready track | Full scan |
|---|---:|---:|---:|---:|
| Empty source | 0.8 ms | — | — | 1.2 ms |
| 1,000 tracks | 1.1 ms | 1.8 ms | 539 ms | 539 ms |
| 12,700 tracks | 6.8 ms | 7.4 ms | 2.42 s | 2.40 s |
| 100,000 tracks | 66.8 ms | 69.2 ms | 18.14 s | 18.07 s |
| 100 tracks, 50 ms simulated stat delay | 51 ms | 1.06 s | 5.10 s | 5.10 s |

This confirms the current architecture’s gap: the scanner finds an audio filename early,
but the local provider exposes its first track only after the full scan returns. Slow
directory enumeration also delays the first filename event. The 50 ms case is a
controlled filesystem simulation, not a physical NAS result.

## P13b first-path fast path

The scanner now emits up to 20 provisional local tracks as soon as it encounters their
audio filenames. The isolated scan worker forwards those paths to the UI process, which
places them in the player queue without committing them to the permanent catalog. The
normal recursive scan and database commit continue in the background. Provisional
tracks use their filenames and “Unknown artist” until normal metadata is available.

The provider-level qualification test holds recursive traversal after the first album
and verifies that the provisional track arrives while the full scan is still running.
This proves the discovery-to-queue handoff boundary; it does not prove decoder startup,
audible output, real NAS behavior, or the 1% UI journey gate. Those still need desktop
runtime and hardware measurements.

## P13c bounded breadth-first discovery

The built-in scandir walker now starts with breadth-first traversal. It switches to the
existing depth-first continuation after finding 20 audio paths, inspecting 512
directories, or reaching a 512-directory frontier limit. An overflow stack preserves
the remaining work, so the traversal still reaches the complete collection. A
regression fixture places the first album deep in one branch and verifies that a
playable album in another branch is surfaced first. This is a local filesystem test;
the delayed-NAS hierarchy benchmark remains part of P13o.

## P13d progressive Tracks view

The scan child now streams metadata in batches: up to 10 tracks in the first batch,
then batches of 50 or a 100 ms flush, whichever happens first. The first provisional
track can populate the Tracks view before tags finish; later metadata updates that row
and inserts new rows through Qt model insert/update notifications. No full model reset
occurs per batch. If My Music has not been opened yet, the window keeps a 1,000-track
preview and transfers it when the page is built. Albums and artists remain unavailable
until their grouping data is complete. The full-catalog apply still performs its normal
single refresh after scanning finishes.

The P13a gate remains open until a diagnostics export captures the actual Qt journey,
including playback-position advance, on local storage and a healthy/slow NAS. In this
environment, pytest and PySide6 are unavailable, so the desktop path and speaker output
cannot be exercised here.

## P13e priority scan around user intent

The active scan worker accepts bounded directory-priority requests over its existing
control pipe. Requests are kept in a 32-entry queue, repeated paths are promoted, and
newer requests run first. The worker accepts only paths inside configured roots, skips
already visited directories, and follows requested subtrees before returning to
background traversal. No extra scanner pool is created.

Artist navigation and playback, track/album playback, and matches from the incremental
library search send relevant local directories to the active scan. The library also
exposes **Shuffle found tracks**: it starts playback from the known playable pool and
uses a bounded 1,000-track starting pool during an active scan, then appends new scan
batches as they arrive. Selecting a different track, artist or album stops extending
that shuffle queue.

Coverage includes the bounded/latest-first control queue, controller routing, and a
traversal test proving a selected subtree is visited before background directories.
GUI timing, million-track foreground responsiveness, and healthy NAS playback still
need validation in a dependency-complete desktop/NAS run.

## P13f NAS/source-opening fast path

Adding a root stores its lexical path in settings and reconciles only the local SQLite
root table; neither step probes the mount or walks its contents. The isolated scan
process performs the root check and traversal after the source has been accepted. New
provisional paths and metadata batches are exposed even when another cached library is
already present, so adding a NAS does not wait for the full catalog replacement.

Root failures and directory `OSError`s remain local to that root/subtree; the scan
continues into other configured roots and sibling directories. Existing per-operation
SMB retry delays are finite, the scan can be cancelled, and the worker process can be
terminated without blocking the UI. Fault tests cover an unavailable root and a delayed
failing subtree while healthy music is still emitted.

Operating-system filesystem calls that never return cannot be interrupted portably by
Python at the individual-call level. In that case the UI stays responsive and the user
can cancel the isolated worker; automatic recovery from a permanently hung mount still
needs a real NAS fault-harness gate. Healthy NAS TTFA and per-operation timeout behavior
remain unqualified here.

## P13g persistent warm cache and resume

Returning users keep indexed track metadata in the local SQLite library index. Home
renders from cheap cached counts and recent listening state before any source refresh.
Cached track rows hydrate on the background scheduler; after the shell is visible, the
isolated scanner reconnects and refreshes the source. A failed refresh keeps the last
known catalog.

Playback checkpoints persist the track and position every five seconds and at window
close. **Continue listening** resumes the saved position after the media reports a
duration. Listening state also records recently played/accessed directories and the
last connection status per configured source. Cached rows are annotated when a source
is unavailable or degraded, and unavailable track rows disable their Play control
until a later successful refresh.

The current local queue is also saved as a bounded snapshot of up to 5,000 local
tracks. Stream URLs and provider credentials are excluded. Returning users get the
queue restored without opening a file; pressing the primary Play action resumes from
its saved queue position before creating a new session.

If a returning user has no listening history yet, **Play something** reads one cached
track row directly from SQLite and starts it before hydrating the full library. This
single-row path does not inspect the file or wait for the collection scan.

Changing configured roots prunes already-loaded rows from removed roots while retaining
tracks under roots that remain selected. If the catalog is still deferred, its SQLite
loader is retargeted to the new root set so opening another source cannot restore stale
tracks from the previous selection.

Smoke coverage verifies checkpoint, recent-directory and source-status persistence
across a database reopen, and availability annotation without a filesystem probe. This
environment has no PySide6/pytest installation, so warm-start GUI timing, actual NAS
offline/reconnect behavior, and decoder resume remain unqualified for P13q.

## P13h one-screen first run

An empty local library now opens to a compact **Your music, immediately** surface with
three actions: choose a music folder, select a mounted NAS music folder, or choose a
few audio files to play directly. Direct file playback uses provisional filename-based
tracks and does not add them to the permanent library. Once local tracks are available,
the normal Home dashboard returns. The Qt interaction and visual layout tests are
written, but cannot run in this environment without PySide6 and pytest.

## P13i drag and drop

The main window accepts local file URLs. Audio files are queued immediately as
provisional tracks and stay outside the permanent catalog. Other dropped paths are
accepted as music roots without a synchronous `stat` or directory probe, then scanned
by the existing isolated background scan process. Dropping both files and folders
starts playback first and scans folders in the background. The screen advertises this
on the empty first-run surface. Drop-event integration tests are written but await the
desktop test runtime.

## P13o time-to-first-music benchmark

`desktop/tools/qualify_time_to_first_music.py` runs synthetic local-size profiles and
a configurable per-operation NAS latency sweep. It reports first directory, first
audio filename, catalog commit and full scan separately. The result explicitly marks
TTFA as unmeasured because a scanner-only process cannot prove decoder or device
output. `desktop/tools/qualify_nas_faults.py` remains the isolated-worker harness for
slow/inaccessible subtrees, cancellation and disconnect behavior. The application's
diagnostics export records play-request to first playback-position advance; that is a
useful proxy but not hardware loopback. No full P13o run was attempted here because
100k track and high-latency profiles can take substantial time. The 10/1,000-track CI
smoke matrix passed again after the queue and first-play policy changes: first audio
filename was discovered in 1.3 ms and 1.6 ms respectively; the 1,000-track full scan
took 160 ms. The 1 ms and 5 ms simulated stat profiles found the first filename in
13.3 ms and 59.5 ms. These are scanner-only results, not playback or physical-NAS times.

## P13k playback-path database work

Play, skip and completion history writes now enter the bounded background scheduler.
The play-history write begins only after `FlowPlayer` emits its playback-start
acknowledgement, so selecting or queuing a provisional track does not create a history
write before the user presses Play. Checkpoint changes are captured in memory on the
track-change signal, then persisted in the background after playback starts and on the
five-second timer. Window close keeps a final synchronous checkpoint save. History IDs
are attached to the current playback session when the background insert completes; a
track that completes before that insert is marked complete after the ID arrives.

## P13l shell before optional sources

The desktop window constructs `ProviderManager` in deferred optional-plugin mode. Its
constructor now builds the local provider, cached index access, resolver and player
without extracting bundled packages or walking installed provider/extension folders.
After Home is built and the player is ready, the existing bounded background scheduler
loads bundled and installed integrations; the UI thread then registers that snapshot
and refreshes plugin/source labels. Opening Sources can start the load sooner, and
package install/restore and source-priority actions wait until discovery finishes so
they cannot race package inspection or overwrite priorities for providers not yet
registered. A failed optional integration load leaves the core shell and local playback
available.

The default `ProviderManager` mode remains eager for non-GUI callers that expect a
complete provider list immediately. A regression test ensures deferred construction
does not call bundled or installed-plugin discovery. `compileall` and whitespace
validation pass. Pytest and the Qt desktop runtime are unavailable here, so cold launch
timing with a deliberately broken provider and unreachable NAS remains to be qualified
on the desktop runtime.

## P13m perceived-speed status

Scan progress stays in a compact background activity panel with a useful stage, elapsed
time, pause/resume and cancel controls. Discovery reports tracks found; tag reading
reports completed work when a total is known; save has its own label. Once a provisional
track appears, Home reports that music is ready while the background panel continues to
show indexing. The app does not use a full-screen loading state or a scan percentage as
a proxy for playback readiness. Pure status-format tests cover discovery, metadata,
save, pause and completion copy.

## P13n first-run random play

The one-screen first-run actions remain unchanged until audio is discovered. As soon as
a provisional playable track enters the progressive catalog, a contextual **Play
Something** action appears. It shuffles only currently playable discoveries, starts
playback immediately and appends later discoveries while the scan is active. Once the
permanent library is available, the regular Home action takes over. A Qt interaction
test covers the action; it awaits the desktop runtime.

First-play discovery uses a light shuffle over a five-track lookahead window. That keeps
the breadth-first discovery order near the front while reducing long runs from the same
album; it does not sort alphabetically or globally randomize the filesystem result.

## P13p CI regression gates

The existing Fluid Melodex CI gate now includes progressive discovery, scan-status,
warm-cache, first-run/drag-drop, timeline and deferred-plugin tests. The test workflow
also runs 10- and 1,000-track synthetic first-audio discovery with a 1,000 ms ceiling
and saves the JSON result as an artifact. The 12.7k startup baseline now fails CI if
warm shell, cached-library shell, or actual cache hydration/visibility reaches 1 s.
The cache-visible stopwatch ends only after the SQLite snapshot is applied to the local
provider, not when a nonzero cached row count is noticed. This is a Qt offscreen startup
contract; it does not stand in for sub-500 ms local track visibility, decoder/audio
latency, or NAS TTFA contracts. Those still require device and NAS-backed qualification.
P13 is not fully qualified until those journey measurements exist on the desktop runtime.

## P13q journey qualification status

Real-device evidence can be checked from the app's **Export redacted diagnostics…**
JSON with `desktop/tools/check_first_music_qualification.py`. It evaluates the latest
source/play attempt, or the supplied `--source-id` and `--play-id`, against the local,
NAS, warm-start or offline-cache contract. For example:

```bash
python desktop/tools/check_first_music_qualification.py diagnostics.json \
  --journey nas --enforce
```

Run the app, select the source, start playback before indexing finishes, wait for the
first playback-position advance, then export diagnostics. The report omits library
paths and track names. Its audio timing remains a playback-position proxy; listen to the
speakers during the journey to confirm audible output.

| Journey | Evidence available | Status |
|---|---|---|
| New user, local folder | Qt journey test asserts a provisional track is queued and `play_requested` is recorded before `background_scan_finished`; diagnostics checker enforces local timing limits | Code path and checker implemented; Qt journey pending CI/device |
| New user, NAS | Isolated scan fault suite passes baseline, cached browse, slow metadata cancellation, mid-scan disconnect and transient recovery at 40 tracks; diagnostics checker enforces NAS timing | Fault harness passed; healthy-NAS TTFA and real mounted share pending |
| Returning NAS user | Cached library index, playback checkpoint and local queue persist; offline catalog hydration is asynchronous | State smoke tests passed; GUI reopen/reconnect journey pending |
| Broken NAS | Cached browse stayed stable during slow rescan; mid-scan disconnect preserved all 40 cached tracks | Harness passed; full application GUI status pending |
| Audible playback | Timeline records decoder start and first playback-position advance | No audio/device journey run in this environment |

This workspace passed `compileall`, `git diff --check`, the P13o small synthetic
scanner gate and the 40-track NAS fault qualification. The focused Qt tests could not
run because pytest and PySide6 are absent from the active runtime. The CI workflow now
contains those tests, but no CI result is available in this session. TTFA, warm GUI
launch limits, mounted-NAS timing and the install-to-audible-playback journeys remain
the final P13 completion gates.
