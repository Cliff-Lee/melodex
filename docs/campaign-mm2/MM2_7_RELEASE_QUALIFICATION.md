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

**Visual evidence reviewed, 2026-10-10:** the older MM2-5a
`37cf13d` 1024x768 cluster screenshot showed tiny labels and ▶ targets.
The newer `893c407` CI run produced all five MM2 screenshots at **1024x768,
1280x800 and 1440x900**. Native-resolution inspection confirmed that
the MM2-7a fixed-size cluster covers, counts, labels and ▶ controls are
legible and spatially separated in the supplied synthetic fixtures. A→B
preview/progress lines render above the map without obscuring top controls.
**The screenshots do not test a complete populated application shell,
real audio, very small viewports, the full selection/Quick Journey panel,
or third-party artwork.** Those acceptance items remain open. Screenshots
from `893c407` cannot be substituted for sign-off on later HEAD commits.

## 2b. Measured automated evidence from previous commit

**Reference only; not latest-HEAD qualification:** the GitHub `Tests`
workflow at `893c407` (run #38025742601) reported:

| Item | Outcome |
|---|---|
| Python 3.11 | 599 passed, 242 skipped; terminology check failed |
| Python 3.12 | 599 passed, 242 skipped; terminology check failed |
| Fluid release gates | Passed |
| Code-health guardrails | Passed |
| NAS, 12.7k scale/soak, startup and elastic-library jobs | Passed |
| Visual QA captures at 3 sizes | Passed |
| Route snapshot p50 / p95 at 700 mapped tracks | **23.122 / 25.444 ms** |
| Route snapshot p95 budget | **100 ms** — passed |
| Separate background Pathfinder calculation in synthetic fixture | **1419.348 ms** |
| Linux packages at this commit | Passed |
| Desktop build at this commit | Later cancelled; not qualified |

The two failed Python jobs originated in
`scripts/terminology_check.py` misreading the accurate warning in the
**newer main-branch** `docs/INSTALL_MACOS.md`: *plugins are not fully
sandboxed*. The checker was repaired in draft branch commits
`c5560af`, `67d60da`, and `00fa26e`, with regression tests verifying
that genuinely affirmative claims are still rejected. **The corrected
latest-head workflow must still finish.**

## 2c. MM2-7d frozen-executable GUI contract

The test/build workflows now execute `scripts/mm2_packaged_gui_probe.py`
against actual frozen executables, not merely source or Qt test widgets.
The probe runs only when explicitly requested by a private
`MELODEX_MM2_PACKAGE_PROBE` environment variable. It uses an isolated
temporary profile, blocks the local control bridge, supplies synthetic
mapped tracks and **does not start audio**.

For macOS arm64/Intel, Windows x64, installed Ubuntu DEB and AppImage, and
Debian 12, the probe must confirm:

- [ ] Open Music Map within the packaged GUI
- [ ] Cluster a dense synthetic map and retain legible ▶ play controls
- [ ] Select A without playback, then genuinely click B on the canvas
- [ ] Show compact Journey controls without shrinking the map
- [ ] Calculate A→B via the real asynchronous Pathfinder scheduler
- [ ] Enable Play/Queue only after a valid preview, without invoking either
- [ ] Render route geometry and a synthetic visible playback-step highlight
- [ ] Cancel without leaving stale route state or triggering player signals
- [ ] Save JSON evidence and a full-window screenshot as CI artifacts
- [ ] Exit the frozen process with code 0 and without the Qt
      `shared QObject was deleted directly` warning

These steps are an **automated packaged GUI simulation**, not evidence of
audible playback, usable NAS permissions, full-real-library performance,
input-device accessibility or packaging distribution signing.

CI evidence artifacts are named `MM2-packaged-GUI-<platform>` for desktop
and `MM2-packaged-GUI-Linux-<ubuntu-version>` for installed Linux builds.
The interactive driver can also be run on a test machine:

```bash
python3 scripts/mm2_packaged_gui_probe.py /path/to/Melodex --output mm2-package.json
```

For an AppImage add `--appimage`. It creates `mm2-package.json` and
`mm2-package.png`, with a temporary isolated profile and no audio.

### MM2-7d full-window visual finding

An actual macOS Apple Silicon frozen-executable probe screenshot (not merely
a standalone widget capture) showed the hovered **destination track card**
expanding across the route. This is a genuine clutter defect at 1024x768.
The subsequent implementation keeps node hover cards compact while both
Journey endpoints are set or a valid route is displayed. The compact route
anchors retain their highlight and z-order. On clearing a route, the
ordinary hover-details interaction is restored.

The new regression test
`test_mm2_route_preview_collapses_hover_card_without_losing_track_identity`
and the packaged probe's `route anchor hover stays compact` check guard
against recurrence. **The corrected latest package screenshot must be
re-inspected before considering visual acceptance cleared.**

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
