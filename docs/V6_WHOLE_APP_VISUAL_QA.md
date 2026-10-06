# V6 — Whole-app visual QA

## Scope

Review Home, My Music, Explore, Album Wall, Now Playing, Lyrics, Flow, and the
visualization surfaces at **1280×800**, **1440×900**, and **1024×768**. Include
empty, populated, loading, error, hover, keyboard-focus, selected, playing, and
reduced-motion states where they apply.

Record a screenshot and pass/fail result for each route/size/state. Log concrete
defects with the route, size, state, and visible symptom. Fix only presentation
defects in Campaign V; reopen interaction or architecture work only for a
reproduced correctness issue.

## Evidence reviewed to start V6

The main-branch `visual-qa-captures` artifact from 2026-10-06 contains twelve
1440×900 captures. They cover the Visuals shell, Profile Pulse, synced and
unsynced Lyric Flow, Constellation, Sonic Weather, Memory Atlas, Musical
Journey, Minimal, reduced-rendering weather, an empty lyric state, and the
internal legacy Album World renderer.

This artifact is useful visualizer evidence, but it does **not** cover Home,
My Music, Explore, Album Wall, the regular Now Playing page, or the full size
and interaction-state matrix. Its green CI check therefore does not close V6.

### Initial observations

- The Visuals shell has a clear dominant canvas and compact controls at 1440×900.
- In synced Lyric Flow, the active line reads clearly, while adjacent lyric
  lines are very faint. Check their contrast at the smaller window sizes and
  against the product's focus/current-line hierarchy.
- Constellation's pinned recognition card is legible in its captured state.
- The legacy Album World capture is marked internal and absent from the public
  selector; keep it out of the user-facing route checklist unless it becomes
  reachable in the app.

## V6 status

**In progress.** Existing automated capture and performance gates pass, but a
whole-app visual review still needs the route/size/state coverage above. Do not
claim V6 complete until the missing core screens and responsive states have
reviewable captures and defects are resolved or explicitly accepted.
