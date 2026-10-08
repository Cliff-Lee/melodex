# Melodex responsiveness contract

The primary requirement is simple:

> Nothing the user does should make Melodex feel frozen or make the user wonder whether Melodex noticed what they did.

Slow external work is allowed. A large library import, remote provider, metadata lookup,
or artwork request may take seconds or minutes. During that work the application must
continue to acknowledge input, navigate, scroll, play audio, pause/cancel work, and
remain usable.

> Incomplete library allowed. Silent player not.

No operation needed only for complete library knowledge may sit on the critical path
between the user selecting accessible music and Melodex playing it.

Responsiveness is both an engineering property and an end-user experience. Fluid
Melodex therefore measures four different things:

1. **Response** — how quickly Melodex visibly acknowledges the action.
2. **Usability** — how quickly the destination shell becomes usable.
3. **Perceived progress** — whether useful content continues to appear without blank
   states or unexplained waiting.
4. **Completion** — when the entire underlying operation actually finishes.

The first three are often more important to perceived quality than total completion
time.

## End-user responsiveness timeline

The preferred interaction pattern is:

- **0–50 ms:** immediate visual acknowledgement.
- **50–150 ms:** destination shell visible and interactive.
- **150–300 ms:** cached or primary content visible.
- **300 ms onward:** secondary content arrives progressively.
- **Long operations:** persistent meaningful progress, pause/cancel when possible, and
  the rest of Melodex remains usable.

These are quality targets rather than permission to block until the upper bound.

## Interaction budget

- Visual acknowledgement: p95 under 100 ms.
- Preferred visual acknowledgement: p95 under 50 ms.
- Navigation shell/page change: under 100 ms where practical and never coupled to slow
  content loading.
- Requested content may arrive progressively after the shell has changed.
- Do not show a transient spinner immediately. Acknowledge the action first, then show
  skeleton/progress UI only when the operation is still running after about 200 ms.
- Interaction-complete and work-complete are separate events.

This avoids both frozen-feeling interactions and distracting spinner flashes for work
that finishes quickly.

## Main-thread budget

- Normal foreground work should stay under 50 ms.
- A task that blocks the UI for 50 ms or more is tracked as a long task.
- Rolling p99 event-loop gap should stay under 100 ms.
- 250 ms is the absolute CI budget for a single foreground stall.
- Repeated stalls over 250 ms are a CI failure.
- Any foreground stall over 500 ms is a serious defect.
- Any foreground stall over 1 second is a release blocker.

## Perceived-performance rules

### Acknowledge first

Every click must produce an immediate, meaningful consequence: selected navigation
state, button state, row highlight, heading change, optimistic state change, or another
clear acknowledgement.

The application must never wait for remote data, artwork, metadata, provider state, or
database work before showing that acknowledgement.

### Render the shell before the data

Pages such as Artists, Albums, Sources, Search, and Now Playing should render their
title, navigation state, controls, layout, cached counts, and other cheap structure
first. Expensive content should populate afterward.

Navigation and data loading are separate phases.

### Never blank useful content during refresh

When existing content is still valid enough to show, retain it while refreshing.
Subtly mark it as updating if necessary, then replace it when fresh data arrives.

Prefer:

> existing content → updating → refreshed content

over:

> blank panel → spinner → content

### Skeletons only when they help

Do not flash a skeleton or spinner for operations that complete quickly.

- under roughly 200 ms: acknowledgement only;
- roughly 200–800 ms: content-shaped skeleton may be appropriate;
- longer work: persistent progress or staged status should explain what is happening.

Skeletons should resemble the content they replace rather than use a generic busy
indicator.

### Progressive reveal

Deliver the first useful information before secondary enrichment.

For an album or artist experience, an appropriate order is usually:

1. title, identity and cached artwork;
2. playable track/release content;
3. richer metadata and biography;
4. credits;
5. recommendations and other enrichment.

Secondary enrichment must not delay primary use.

### Prioritize the viewport

For large collections, create and hydrate what the user can currently see before
off-screen content.

If 500 albums are present, the first visible cards and their artwork matter more than
album 437. Scrolling should schedule newly visible content ahead of distant content.

### Cache first, refresh quietly

Album covers, lyrics, artist photos, biographies, plugin states, waveform data,
provider results, and similar enrichment should normally use a stale-while-revalidate
pattern:

1. show the last known useful result immediately;
2. refresh away from the GUI thread;
3. update in place only when fresher data is available.

A cache hit should never be delayed by a network refresh.

### Prefetch likely next actions

Where navigation is predictable, Melodex may quietly prepare the likely next view when
it is cheap to do so.

Examples include:

- Artist → Releases;
- Release → Album;
- Album → Track details;
- selected library item → Now Playing/context.

Prefetching must never compete with foreground interaction, playback, or visible
artwork for critical resources.

### Optimistic UI

For actions with a high probability of success and a safe rollback, update the UI
immediately and complete persistence in the background.

Good candidates include:

- favourite/heart state;
- add-to-playlist;
- queue edits;
- simple preference toggles.

If persistence fails, restore the previous state and explain the failure without
blocking the user.

### Continuous visible progress

For long-running work, meaningful changing information is better than a stationary
spinner.

A large import might show:

- files discovered;
- files indexed;
- metadata reused/read;
- artwork cached;
- current stage;
- elapsed time;
- pause/cancel controls;
- explicit confirmation that Melodex remains usable.

Progress should be real when it can be measured. When it cannot, show truthful stages
such as Discovering files, Reading tags, Building library, Finding artwork, and
Finishing up. Never fake precise percentages.

### Motion communicates causality

Short transitions can help the eye understand that the requested action occurred.

- ordinary state/navigation transitions: roughly 100–180 ms;
- avoid decorative 400–600 ms transitions on normal navigation;
- spatial experiences such as Album Wall may use richer motion because motion is part
  of the feature.

Where useful, preserve visual continuity between the selected object and its
destination rather than replacing the entire interface abruptly.

## Architectural rule

The Qt main thread may update UI state. It must not wait for:

- network requests;
- provider processes;
- Keychain/credential access;
- slow filesystem or NAS operations;
- metadata extraction;
- expensive image processing;
- large database operations; or
- substantial computation.

The preferred pattern is:

1. acknowledge the action immediately;
2. render the destination shell;
3. show cached/local state when available;
4. start slow work away from the GUI thread;
5. progressively update visible primary content;
6. show skeleton/progress UI after roughly 200 ms if the work is still running;
7. load secondary/off-screen content later;
8. allow cancellation where the operation can be long-running.

## Large-library rule

Importing a 500 GB / 12,700-track library is not required to finish quickly. It is
required to remain interactive throughout.

The interaction should feel complete once the folder is accepted and a live import
view is visible. During indexing, users should still be able to:

- navigate elsewhere;
- scroll existing library content;
- play, pause and skip music;
- inspect progress;
- pause or cancel the operation;
- close and later resume safely where supported.

The import experience must distinguish interaction completion from indexing completion.

## Measurement

Fluid Melodex records separate measurements for:

- **interaction acknowledgement latency** — click/input to visible acknowledgement;
- **shell latency** — click/input to usable destination structure;
- **primary-content latency** — time until the first useful cached or live content is
  available;
- **event-loop delay** — whether foreground work prevented Qt from servicing the UI;
- **task completion time** — the full duration of the underlying operation.

Task completion is not a substitute for the other measures.

Additional UX regressions to test include:

- page goes blank during refresh;
- spinner/skeleton flashes for work under about 200 ms;
- foreground interaction waits for secondary content;
- off-screen items are hydrated before visible ones;
- cached content waits on network refresh;
- progress stops changing with no explanation;
- long operation cannot be paused/cancelled where cancellation is feasible;
- optimistic action blocks while persistence completes.

The thresholds are informed by established interaction-performance guidance such as
Google's RAIL model, while being applied here as a native-desktop quality target rather
than as a web metric.

## Fluid Melodex campaign sequence

### P0 — Measure responsiveness

Instrument event-loop gaps and interaction acknowledgement. Export redacted
responsiveness metrics so intermittent freezes become measurable defects.

### P1 — Eliminate foreground blocking in Sources

Torture-test slow Keychain/config/provider paths and ensure Sources renders immediately
from cached state while validation happens in the background.

### P2 — Instant navigation shells

Separate page navigation from page population across Home, My Music, Discover, Album
Wall, Music Map, Sources, Playlists, Journeys and Now Playing.

Success means the navigation state and destination shell appear immediately even when
the destination's content is intentionally delayed.

### P3 — Stale-while-revalidate and progressive content

Remove destructive refresh patterns that clear useful content. Introduce cache-first
rendering, delayed skeletons, progressive primary/secondary content, and viewport-first
hydration.

### P4 — Long-operation experience

Apply the contract to library import, scans, artwork recovery, analysis and other bulk
jobs. Provide truthful progress/stages, cancellation or pause where practical, and
continue normal Melodex use throughout.

### P5 — Predictive and optimistic interaction

Add safe optimistic UI for common actions and low-priority prefetching for predictable
navigation paths. Validate that prediction work never hurts foreground responsiveness.

### P6 — Motion and continuity polish

Audit transitions, remove sluggish animation, and add short causal transitions where
they improve orientation. Spatial features may retain richer motion where it is part of
the experience.

### P7 — Release gates

Representative responsiveness and perceived-performance scenarios are release gates,
not advisory checks.

The dedicated **Fluid Melodex release gates** CI job installs a real Qt runtime and
executes the controlled scenarios from P0–P6, including:

- slow Keychain/config work while Sources remains interactive;
- shell-first navigation and stale-navigation cancellation;
- stale-while-revalidate Search behaviour and delayed loading UI;
- reuse of unchanged My Music rendering;
- persistent/cancellable large-library progress;
- optimistic Love/Keep acknowledgement and rollback;
- local-only next-track prefetch that yields to foreground bulk work; and
- short non-blocking/reduced-motion behaviour.

The gate also evaluates controlled responsiveness summaries against these hard budgets:

- interaction acknowledgement p95 **≤100 ms**;
- interaction acknowledgement p95 **≤50 ms preferred**;
- event-loop p99 gap **≤100 ms**;
- no foreground stall over the **250 ms CI budget**;
- no **>500 ms serious** foreground stalls; and
- no **>1 s release blockers**.

The preferred 50 ms interaction target is advisory; the 100 ms p95 limit is blocking.

CI deliberately avoids making release decisions from uncontrolled shared-runner
microbenchmarks. Timing budgets are evaluated deterministically and the GUI scenarios
test the architecture: slow work must be outside the foreground interaction path,
useful content must not be destroyed unnecessarily, and long work must remain
interruptible.

Both normal main-branch releases and manual-tag releases run the same
`scripts/fluid_ci_gate.py` runner before a release can proceed.
`scripts/release_readiness.py` also verifies that those workflow hooks remain present.

For a real desktop session, export Melodex diagnostics and evaluate them with:

```bash
python scripts/fluid_gate_check.py /path/to/melodex-diagnostics.json
```

This uses the same hard budget against the recorded interaction/event-loop summary.
A feature is not finished if it completes correctly but makes the application feel
frozen, blank, uncertain, or unnecessarily busy.
