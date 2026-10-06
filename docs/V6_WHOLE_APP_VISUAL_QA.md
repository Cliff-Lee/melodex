# V6 — Whole-app visual QA

## Review scope

Reviewed the primary screens at **1024×768**, **1280×800**, and **1440×900**:
Home, My Music, Explore, Journeys, Playlists, Now Playing, Visuals, Album Wall,
and Music Map. Also reviewed the twelve deterministic visualization captures
at each size, covering Profile Pulse, synced and untimed Lyric Flow,
Constellation, Sonic Weather, Memory Atlas, Musical Journey, Minimal, empty
lyrics, reduced rendering, and the internal legacy renderer.

The app-route captures use the empty library/player state. The visualization
captures include populated fixtures where needed. These are rendering checks
for clipping, overlap, missing controls, illegible text, and visibly broken
rendering; they do not claim every interaction state was captured.

## Capture matrix

| Window size | App routes | Visualization scenes | Review |
| --- | --- | --- | --- |
| 1024×768 | [Contact sheet](campaign-v-v6/main-1024x768.jpg) | [Contact sheet](campaign-v-v6/visuals-1024x768.jpg) | Pass after fixes |
| 1280×800 | [Contact sheet](campaign-v-v6/main-1280x800.jpg) | [Contact sheet](campaign-v-v6/visuals-1280x800.jpg) | Pass after fixes |
| 1440×900 | [Contact sheet](campaign-v-v6/main-1440x900.jpg) | [Contact sheet](campaign-v-v6/visuals-1440x900.jpg) | Pass after fixes |

## Defects fixed

1. At 1024×768, the Now Playing cover art overlapped the lyrics tabs. The hero
   art now scales down to the available short viewport; absent artist-photo
   and credit controls are hidden so they do not reserve overlapping space.
2. Previous and Next transport controls rendered as missing-font boxes on
   Linux. Transport controls now use drawn icons and retain accessible names.

The untimed Lyric Flow capture fixture was also corrected to use the canonical
`full_text` frame field. The prior fixture supplied a current line while
claiming lyrics were untimed, which exercised an invalid combination and
created a clipped screenshot; the app's untimed renderer was not changed.

No further clipping, overlap, missing controls, illegible text, or visibly
broken rendering was found in the reviewed matrix. No aesthetic changes,
spacing refinements, new animation work, or new UI components were made for V6.

## Automated closure gates

Manual visual review is complete. Campaign V remains open until the closure
PR's regression, visual, cross-platform, and package checks finish green.
