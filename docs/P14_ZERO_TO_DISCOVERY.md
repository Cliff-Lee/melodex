# P14 — Zero-to-Discovery: Interesting Music Immediately

**Status: IN PROGRESS**

P14 starts after the P13 player-first work. P13 makes a partially discovered
collection playable; P14 makes that partial collection feel worth exploring.
The user should not need a complete scan, rich tags, listening history, or a
recommendation service to get a useful first session.

## Product contract

From the first playable tracks, Melodex offers a useful next action immediately.
On a cold start, the first queue should reveal some breadth instead of clustering
around one artist or album. As discovery and metadata improve, later choices may
become more personal. None of that work may pause playback or reshuffle the track
currently playing.

The campaign uses only tracks already discovered or in the warm cache. It must
not trigger filesystem probes, tag reads, artwork work, analysis, or provider calls
on the action path.

## Current baseline

- Home already offers **Play something**, plus Comfort, Explore, and Rediscover.
- During first-run scanning, **Play Something** becomes available as soon as a
  provisional playable track exists.
- The P13 provisional queue grows as scan batches arrive.
- Cold-start queue ordering uses a bounded lookahead shuffle that preserves early
  discovery order and avoids adjacent albums when possible.
- The full-library `MindEngine` already uses listening history for later sessions.

P14 focuses on the gap between “a file can play” and “the first few choices feel
like a good introduction to this collection.” It does not replace the P13 playback
fast path or the mature-library session planner.

## Sequence and gates

### P14a — Cold-start breadth policy — COMPLETE

Within the existing bounded lookahead, avoid repeating a known artist among the
last three choices and prefer a different album from the immediately previous
choice. Missing/provisional tags do not block selection or count as repeated
identities. Preserve every discovered candidate and keep early discoveries near
the front.

**Gate:** deterministic tests cover artist breadth, album spacing, early discovery
order, and unknown-tag fallback.

### P14b — First-session choices — IMPLEMENTED; GUI qualification pending

Audit the first-run and partially populated Home states. Make the available action
clear when there are 1–10 tracks, a larger partial pool, a restored cache, or no
listening history. Keep the first decision simple; expose richer tuning only when
the user asks for it.

**Gate:** each state has a useful action, and the first playable action requires no
complete catalog or metadata hydration.

The first-run Play Something action is now promoted above source setup actions as
soon as one playable track is available, with a live ready-track count. Scan
progress is reflected in the first-run status text. On Home, Play something uses
the discovered pool immediately while a scan is active instead of waiting for the
full-library session planner. The full planner remains available once discovery
has finished.

The GUI regression tests are in `desktop/tests/test_p13h_first_run.py`. They could
not run in the current workspace because neither PySide6 nor pytest is installed.

### P14c — Progressive discovery session — IMPLEMENTED; GUI qualification pending

Build an initial session from the current playable pool, then extend it as new
tracks arrive. New entries should preserve the queue position and not interrupt
playback. Apply the same bounded breadth policy to additions.

**Gate:** start from one provisional track, hold the scan open, and verify audio
can start before later batches arrive; then verify later tracks join without
changing the current track or next-track intent.

An explicit discovery shuffle now extends only while its queue snapshot is still
unchanged. Added batches use the bounded artist/album breadth policy with the
queue tail as context. The one-track provisional preview also accepts later tracks
only until the listener replaces it with another queue intent. Scan completion or
failure closes the extension window.

Regression tests cover queue-position preservation, non-autoplaying appends,
extension after listener queue changes, and continuation ordering. GUI execution
remains pending because PySide6 and pytest are unavailable in this workspace.

### P14d — Cold-start quality and control — IMPLEMENTED; GUI qualification pending

Test small, duplicate-heavy, badly tagged, single-artist, and broad collections.
Let the listener move toward familiar or more adventurous choices without making
those controls prerequisites for first play.

**Gate:** recommendation quality is measured separately from discovery speed; all
controls remain responsive during background scanning.

`desktop/tools/qualify_first_session_quality.py` now runs 32 deterministic seeds
over one-track, small mixed, duplicate-heavy, badly tagged, single-artist,
broad/interleaved, and artist-clustered pools. It checks full candidate retention,
early breadth where the discovered pool offers it, and bounded displacement from
discovery order. It reads no files and measures no playback latency.

Initial medians for unique known artists/albums among the first five choices:

| Pool | Artists | Albums |
|---|---:|---:|
| One track | 1 | 1 |
| Small mixed | 4 | 4 |
| Duplicate-heavy | 3 | 2 |
| Badly tagged | 2 | 2 |
| Single artist | 1 | 5 |
| Broad/interleaved | 5 | 5 |
| Artist-clustered | 2 | 4 |

Home now hides session tuning while a cached catalog is still hydrating, then
restores Comfort/Explore/Rediscover once the catalog is ready. The primary play
action remains available during hydration. The optional modes remain off the
first-play path.

Run the profile qualification with:

```bash
python desktop/tools/qualify_first_session_quality.py --seeds 32
```

The CLI gates and its test pass locally. GUI qualification remains pending because
PySide6 and pytest are unavailable in this workspace.

### P14e — Warm-history handoff — IMPLEMENTED; GUI qualification pending

Use local playback signals once available, while retaining a fast fallback for
new installs, deleted history, and offline/cached libraries.

**Gate:** history enrichment cannot delay the first available queue or make a
cached collection disappear.

On a fully hydrated library, **Play something** now samples at most 512 cached
rows across the collection, starts a 40-track-or-smaller breadth-spaced queue,
then builds the balanced history-aware session on the foreground scheduler. When
the plan returns, it replaces only the unplayed tail if the original queue is
still intact. A listener queue edit makes the callback a no-op. The current track
and already-heard prefix are preserved.

GUI tests cover immediate queue availability, tail-only refinement, and honoring
queue edits. They remain unrun here because PySide6 and pytest are unavailable.

### P14f — Journey qualification — IMPLEMENTED; desktop qualification pending

Run first-session journeys on fresh local folders, partial NAS discovery, and
returning caches. Record time-to-first-choice, time-to-queue, time-to-audio, first
five-track artist/album breadth, and queue stability as separate outcomes.

**Gate:** first audio remains inside the P13 contract; users can begin listening
before the complete scan; incomplete metadata degrades gracefully.

`desktop/tools/qualify_first_session_journeys.py` now checks fresh-local,
partial-NAS, and returning-cache queue outcomes against synthetic profiles. It
reports first-five known artist/album breadth, candidate retention, and verifies
that late history refinement is discarded after a listener queue edit. Queue
quality and timing remain separate results.

First-music diagnostics now record `first_queue_ready` after the player queue is
mutated, making time-to-choice, time-to-queue, first-playable readiness, and
play-request-to-audio-output separately reportable. Run the journey gate with:

```bash
python desktop/tools/qualify_first_session_journeys.py
```

Attach a redacted diagnostics export to include actual UI/player measurements:

```bash
python desktop/tools/qualify_first_session_journeys.py --diagnostics diagnostics.json
```

The script does not invent timing results when no desktop run is supplied. Its
queue journeys are synthetic; real TTFA and the P13 latency limits remain pending
desktop qualification with PySide6, the audio backend, and local/NAS fixtures.

## Current implementation

P14a–P14f have implementation slices in place. First-play queue construction
remains in memory and bounded; history planning uses the existing background
scheduler. No file probing or metadata work was added to the play path. Policy,
synthetic quality, and pure queue-handoff gates pass locally. GUI qualification
for P14b–P14f still requires a desktop test environment with PySide6 and pytest.
