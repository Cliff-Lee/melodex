# P24 — Predictive Playback

**Status: release candidate v0.7.27. Automated qualification will be recorded in the campaign PR; slow-NAS transition timing remains an owner check.**

## Goal

Reduce avoidable waits between queued tracks, especially when a source lives on a NAS or needs network resolution. P24 prepares only the immediate next queue item before the current track ends, then reuses that prepared source for the transition.

## Listening contract

- Playback stays invisible: no new buttons, settings, or listening modes.
- The queue remains authoritative. Melodex prepares exactly the item at the next queue position.
- Resolution runs on the existing bounded background prefetch lane. The active deck keeps playing while work runs.
- Read-ahead starts within 15 seconds of the current track ending. A Journey transition can start earlier to cover its planned fade, up to 30 seconds ahead.
- The inactive media deck stays muted while it prepares the source. Playback starts only when the listener advances, the track ends, or an existing Journey crossfade begins.
- An edit that changes the upcoming item, seek, pause, or stop invalidates the prepared source. A late background result is discarded.
- A failed or rejected prefetch never interrupts the current track. Manual next and natural end fall back to the existing load and recovery path.
- P24 does not download whole tracks, persist stream URLs, add a cloud service, or change provider permissions. Native iPhone support remains deferred.

## Acceptance

- At most one next source is being resolved or loaded at a time.
- Resolver work is submitted at prefetch priority; source installation and playback control stay on the Qt playback thread.
- Manual next, natural end, and Journey crossfade reuse a matching prepared source without resolving it a second time.
- Changing the upcoming item discards in-flight results, clears the loaded candidate, and removes its temporary gateway registration.
- Scheduler rejection, resolution failure, and inactive-deck playback failure preserve the current track and use the existing fallback path.
- Runtime diagnostics count requests, ready sources, ready and late uses, stale results, failures, cancellations, and preparation time. They contain no track names, paths, URLs, or credentials.
- Automated tests cover scheduling, stale-result rejection, manual next, natural end, Journey crossfade, and scheduler rejection.
- The existing P22 stall and recovery counters remain the way to compare real NAS behavior. A physical slow-NAS timing comparison can be recorded after release.

## Implementation

P24 extends FlowPlayer's existing dual-deck architecture. It resolves the next item on BackgroundScheduler's single-worker prefetch lane, installs the source on the inactive deck, and records readiness from Qt's LoadedMedia or BufferedMedia status. The current source stays active until the existing transition path takes ownership of the prepared deck.

The implementation adds no UI surface and does not replace P13's artwork prefetch or P22's active-track recovery.
