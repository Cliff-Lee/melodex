# P16 — The Living Queue

## Purpose

P15 makes a musical route visible and editable before playback. P16 makes that
route remain steerable while it plays: the listener can protect choices they
care about, change the upcoming music, and still let Melodex adapt the route.

The queue is the live expression of the journey. Automatic replanning must
never silently discard a user's protected choices.

## Campaign stages

1. **P16a — Queue contract and state model.** Keep playback state separate from
   track metadata; define what the playing, generated, inserted, pinned, and
   locked entries mean. A route refresh preserves the current track and all
   protected upcoming choices.
2. **P16b — Direct queue editing.** Let the listener pin, remove, insert, and
   reorder upcoming tracks and albums through a clear queue surface.
3. **P16c — Adaptive steering.** Apply route choices such as more familiar,
   more surprising, more like this, or toward an artist/region without
   replacing protected entries.
4. **P16d — Safe automation.** Lock upcoming tracks, preserve protected
   choices during replanning, and provide undo for automatic changes.
5. **P16e — Explain each choice.** Show concise reasons for selected and
   adapted tracks, including which user direction shaped them.
6. **P16f — Integrate and qualify.** Test complete playback journeys, route
   changes, queue edits, recovery, and regressions with real libraries.

## P16a contract

- The currently playing track cannot be removed or reordered by queue editing.
- Pinning and locking apply to upcoming tracks.
- A manually inserted track is protected from automatic route replacement.
- Pins and locks remain in their relative order during a replan.
- New generated tracks fill the unprotected spaces around those choices.
- Current and protected tracks are not duplicated in the generated tail.
- Queue intent is stored separately from track/provider metadata.
- A failed route build leaves the existing queue untouched.

## P16b progress

The **Up next** panel now has Keep, Remove, Move earlier, and Move later
controls, with matching row context-menu actions. Existing library and album
queue actions remain the way to add music; tracks appended to an existing queue
are treated as user choices during later route changes. Player queue edits
preserve the active track and playback position. Journey Live replans pass
through the Living Queue model so pinned, locked, and manually added tracks
survive automatic changes.

The focused interaction gate is complete when the UI test runtime confirms the
panel actions and a real playback journey confirms that editing the tail does
not interrupt the active track. This checkout has no pytest/PySide6 runtime, so
the UI integration still needs the normal desktop CI/device run.

## P16c progress

The Up Next panel now exposes the familiar/surprising and musical-character
directions already supported by Journey Live, so listeners can steer without
returning to Music Map. A selected track can request a reachable, similar
waypoint; Melodex keeps that selected track and plans the remaining route around
it. The row menu also supports **Head toward this artist** and **Explore this
map area**. These become one-shot route stages, and the existing destination is
still retained. If a requested direction cannot be routed, the current queue
stays intact.

The pure route tests cover similarity, artist, and map-area stages. The Qt panel
test cases are added; executing them still requires the normal desktop CI/device
run.

## P16d progress

Up Next now offers **Lock next 3**, per-track Lock/Unlock actions, and
**Undo route change**. Undo restores the generated tail from before the latest
automatic replacement while retaining the current track and any choices that
are still pinned, locked, or manually added. The model tests cover protected
choices and undo after playback advances. Qt interaction checks still need the
desktop test runtime.

## P16e progress

Journey Live now sends each adapted track's stage or connection reason to Up
Next. Selecting a track shows its concise reason below the queue, and the row
tooltip retains the explanation alongside any protection status. The route
details view continues to show stage fit and reason. Qt presentation checks
still need the desktop test runtime.

## Completion gates

Each stage must pass its focused checks before the next stage starts. P16 is
complete when a listener can edit an active journey, steer it, understand why
the next tracks were chosen, and recover from automated changes without losing
protected choices or interrupting the current track.

## P16f qualification status

Focused tests now cover route-stage scoring, Living Queue signal wiring, queue
intent and replan behavior, undo after playback advances, and the Qt queue
controls for locks, undo, and track explanations. A combinatorial queue test
checks every pin/lock pattern across four upcoming tracks. The pure route,
wiring, and queue tests pass locally (37 focused cases), including undo of
intentional repeated tracks in the prior queue. Player contract tests now also
assert that remove/move operations leave the active deck position unchanged.
The Qt desktop suite
and player contract tests are configured in `.github/workflows/test.yml`
with an offscreen Qt platform, but cannot be run in this checkout because it
does not have pytest or PySide6 installed. P16f remains open until that desktop
suite and an active playback journey are qualified.

### Active playback qualification checklist

1. Start a Journey Live route and confirm audio is playing.
2. Keep one upcoming track and lock the next three; confirm their row markers.
3. Steer toward a similar track, an artist, and a map area in separate replans.
   Confirm the current track and position do not change and protected tracks
   remain in order.
4. Select adapted tracks and confirm Up Next shows their route explanation.
5. Undo a route change; confirm the prior generated tracks return while locked
   and kept tracks remain.
6. Advance playback, replan, and undo again; then manually reorder the queue
   and confirm the stale undo action is cleared.
7. Try an unroutable steering request and confirm the existing queue remains
   unchanged.

The P12 structural ratchet is also already over its line-count cap on the base
commit (`main_window.py`: 4,827 lines against 3,780). P16 moves its signal
connections into `living_queue_wiring.py`, leaving `main_window.py` at 4,826
lines; the existing P12 overage remains a separate codebase issue.
The broader MainWindow refactor is deferred and is not a P16 completion gate.
