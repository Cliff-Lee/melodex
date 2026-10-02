# Melodex responsiveness contract

The primary requirement is simple:

> Nothing the user does should make Melodex feel frozen.

Slow external work is allowed. A large library import, remote provider, metadata lookup,
or artwork request may take seconds or minutes. During that work the application must
continue to acknowledge input, navigate, scroll, play audio, pause/cancel work, and
remain usable.

## Interaction budget

- Visual acknowledgement: p95 under 100 ms.
- Preferred visual acknowledgement: p95 under 50 ms.
- Navigation shell/page change: under 100 ms.
- Requested content may arrive progressively after the shell has changed.
- Do not show a transient spinner immediately. Acknowledge the action first, then show
  skeleton/progress UI only when the operation is still running after about 200 ms.

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
2. show cached/local state when available;
3. start slow work away from the GUI thread;
4. progressively update the page;
5. show progress UI after roughly 200 ms if the work is still running;
6. allow cancellation where the operation can be long-running.

## Large-library rule

Importing a 500 GB / 12,700-track library is not required to finish quickly. It is
required to remain interactive throughout. While indexing, users should still be able
to navigate, scroll, play/pause music, and cancel or pause the operation.

## Measurement

The Fluid Melodex campaign records two different kinds of performance:

**Interaction acknowledgement latency** measures how quickly the application visibly
reacts to an action.

**Event-loop delay** measures whether foreground work prevented Qt from servicing the
UI.

These are deliberately separate from external task completion time.

The thresholds are informed by established interaction-performance guidance such as
Google's RAIL model, while being applied here as a native-desktop quality target rather
than as a web metric.
