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
rendering; they do not claim every interaction state was captured. The linked
matrix is the original V6 baseline and predates the final feedback follow-up
below.

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
broken rendering was found in the original reviewed matrix. No aesthetic
changes, spacing refinements, new animation work, or new UI components were
made during that V6 baseline pass.

## Final feedback follow-up

The final scoped follow-up responds to these concrete product requests:

- Reduce Album Wall clutter while keeping already-loaded covers immediately
  available through pans and data refreshes.
- Confirm album activation keeps disc and track order.
- Expand Profile Pulse contours to use more of the scene plane.
- Remove Sonic Weather and Minimal from the visualizer choices.
- Present Music Map as an album-cover map with hover details, zoom controls,
  and a less dense overview for large collections.
- Put Now Playing photo attribution on hover instead of over the photo.

The follow-up capture matrix and automated regression/package gates still need
to run against the resulting code before this final pass can close. The original
matrix images above do not validate these later changes.

## Automated closure gates

The original V6 closure gates passed on PR #240. The Campaign V feedback
follow-up is a separate release candidate; its changed screens are being
recaptured at all three window sizes and its regression/package gates must pass
before this follow-up closes.
