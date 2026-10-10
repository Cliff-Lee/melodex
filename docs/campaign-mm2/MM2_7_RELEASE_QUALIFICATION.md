# Music Map 2.0 — MM2-7 release qualification

**Release decision: HOLD.** Branch: `campaign/mm2-map-first-experience`, draft PR #261.
This checklist deliberately distinguishes coded functionality, CI results, screenshot
inspection, and real packaged playback. **Do not infer one from another.**

## 1. Required automated gates

- [ ] Latest branch HEAD: `Tests` workflow completely green (all Python
  versions, code health, Fluid subgroups, large-library, NAS, visual captures).
- [ ] Latest branch HEAD: `Build desktop` workflow completely green for
  macOS Apple Silicon, macOS Intel and Windows.
- [ ] Latest branch HEAD: `Build Linux packages` completely green, including
  all supported distro smoke stages.
- [ ] No Qt `QObject: shared QObject was deleted directly` or abnormal process
  exit. This failure has been intermittent; one isolated green run does not
  prove the lifetime bug permanently fixed.
- [ ] `desktop/melodex/main_window.py` is within its inherited **4,827-line**
  structural ratchet; do not increase/disable the guardrail.
- [ ] `mm2-route-latency-700.json` reports snapshot preparation
  **p95 <= 100 ms** (synthetic benchmark). Background Pathfinder duration must
  be recorded separately, not misrepresented as click acknowledgement.
- [ ] `desktop/tests/test_spatial_browsing_ux.py` passes, including MM2
  map navigation, region listening, quick route, async cancellation,
  single-player Play/Queue handoff, and legible click targets.
- [ ] All `visual-qa-captures-*` artifacts exist for 1024x768, 1280x800,
  1440x900. Require the MM2 `13-music-map.png`,
  `13b-music-map-view.png`, `13c-music-map-clusters.png`,
  `13d-music-map-route-preview.png`, and
  `13e-music-map-route-progress.png` captures **on the latest HEAD**.

The PR workflows intentionally cancel superseded PR runs. Only the HEAD run
counts; canceled older checks are neither pass nor fail of the latest code.

## 2. Visual usability inspection

Inspect each latest screenshot at **native resolution**, not only a reduced
montage. Fail if text is unreadable, controls overlap, or the map shrinks when
opening View, Regions, More, a selected-track card, or Journey tools.

- [ ] Overview region cover, numerical count, visible landmark and separate
  ▶ control are legible and directly clickable at Fit.
- [ ] Region tiles do not overlap at 1024x768, including an intentionally
  narrow-window case. Map points should remain visible at reasonable zoom.
- [ ] Selection and contextual Play/Queue/Play from here/Plan a journey do not
  obscure navigation; Escape dismisses only the topmost context.
- [ ] A→B path is visible above background links, with start, destination
  and intermediate stops clear. Progress is distinguishable without needing
  an exact color perception.
- [ ] Long artist/track names elide cleanly; full text remains discoverable
  via accessible name or hover.
- [ ] Default overview does not become an empty-looking canvas with unreadably
  tiny album art; balance density against decluttering.

**Evidence already inspected:** a CI visual capture from the older MM2-5a
commit `37cf13d`, 1024x768 (`13c-music-map-clusters.png`) showed excessively
small cluster labels and ▶ targets at Fit. MM2-7a sets those cluster graphics
to ignore the map view transform so their on-screen size stays readable and
adds a viewport geometry regression check. **That fix is not yet confirmed
visually on the latest HEAD; this item stays open.** Screenshots from earlier
commits are not substituted for latest-head sign-off.

## 3. Packaged hardware smoke tests

Use actual packaged applications, not just running Python from a checkout.
This is the minimum manual acceptance matrix:

| Platform | Install/open | Map + zoom | Music from local folder | NAS | Route Play/Queue |
|---|---|---|---|---|---|
| macOS Apple Silicon | [ ] | [ ] | [ ] | [ ] | [ ] |
| macOS Intel | [ ] | [ ] | [ ] | [ ] | [ ] |
| Ubuntu 22.04/24.04 | [ ] | [ ] | [ ] | [ ] | [ ] |
| Windows x64 | [ ] | [ ] | [ ] | [ ] | [ ] |

Where hardware is unavailable, state the untested platform explicitly;
do not mark it as completed from packaging success.

For each available system:
1. Clean launch. Load a small local music directory, then the large/NAS
   library if present. Confirm a single track starts playing immediately
   through direct Play.
2. Open Music Map, pan/zoom/Fit, search, Back/Forward, Regions, ▶ region
   session, Surprise me, and Play from here. Assert no selection/navigation
   changes playback without an explicit Play action.
3. Plan a journey: click start, click destination, preview, edit destination
   while pending, cancel, retry. Assert no stale preview or frozen UI.
4. Play then Queue a route and verify actual audio, ordering, and that route
   progress follows the currently playing track; leaving the route clears
   progress. Verify player continues after changing pages/minimising.
5. Resize to 1024x768 and smaller: click targets remain usable; options and
   Journey never permanently expand/reflow the graph viewport.
6. Trigger inaccessible NAS/unplug, missing local file and empty library.
   Verify useful error messages, no unrelated fallback playback, and no crash.
7. Leave playback and map open for a meaningful soak; confirm exit/shutdown
   is clean and no QObject lifetime warnings appear.

Record platform + OS + packaged artifact SHA, elapsed time-to-first-play,
playback failures, screenshot evidence, and any observed UI-thread stalls.

## 4. Decision record

- **Current result:** NO-GO — latest-head CI and packaged manual smoke are
  incomplete; intermittent Qt shutdown risk needs continued monitoring.
- **Allowed next action:** repair failing checks on draft PR, re-run HEAD,
  inspect captured images, test actual packaged builds.
- **Forbidden until fully qualified:** merge to `main`, release tag,
  Homebrew/WinGet/Ubuntu store update, or installer announcement.
