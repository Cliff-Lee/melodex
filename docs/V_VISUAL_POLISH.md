# Campaign V — Visual Polish Before Tester Retest

Campaign V is a bounded cosmetic polish pass for Melodex before the next external tester retry.

Chiasm is a separate experimental fork. Campaign V must not import Chiasm spatial navigation,
3D metaphors, conceptual redesigns or exploratory UX into Melodex.

## Contract

Campaign V changes presentation, not the interaction model.

Prefer:
- subtraction;
- hierarchy;
- spacing;
- consistency;
- familiar controls;
- clean loading/empty states;
- coherent hover, pressed, selected and focus states.

Do not use Campaign V for:
- features;
- navigation redesign;
- architectural refactors;
- provider/plugin redesign;
- visualization research;
- new engineering campaigns unless a concrete visual defect requires a narrow underlying fix.

## Sequence

### V1 — Visual system cleanup

Normalize typography hierarchy, spacing, radii, button/control states, secondary text,
surfaces and artwork framing. Remove high-visibility one-off static styles where the
existing application stylesheet can own them.

Initial V1 cleanup:
- shared static Now Playing hero typography/art/photo treatments;
- shared Lyrics toolbar/view/source presentation;
- consistent muted/status text in Library, Album Wall and Music Map;
- common pressed and disabled button states;
- consistent focus border coverage for plain-text inputs.

Dynamic artwork-derived Now Playing accents remain dynamic. No layout or interaction
behaviour changes are part of V1.

V1 qualified across the full test, visual-performance and packaging matrix.

### V2 — Application shell and navigation

Polish the existing sidebar, selected/hover state, page headers, group spacing, alignment,
dividers and resize appearance without changing navigation architecture.

V2 keeps the page structure unchanged while tightening sidebar geometry, separating the
utility navigation visually, making hover/selected states stable rather than layout-shifting,
and giving page titles/subtitles a quieter, more consistent rhythm.

V2 qualified across the full test, visual-performance and packaging matrix.

### V3 — Main library surfaces

Polish Albums, Artists, Tracks, Search, Playlists and Sources where visually necessary.
Prioritize artwork prominence, card/row proportions, spacing, hierarchy, truncation,
loading/empty states and invisible cached-artwork hydration.

V3 increases album/artist artwork from 160 px to 180 px, gives cards calmer gutters and
proportions, tightens track-row density, normalizes top-control spacing and uses the shared
search-status/empty-state language. Existing cache-first artwork behavior is unchanged, so
known covers remain immediate. Sources is deliberately left structurally unchanged because
its current cards already use the shared application visual system.

V3 qualified across the full test, large-library, visual-performance and packaging matrix.

### V4 — Now Playing and Lyrics

Cosmetic pass only: hierarchy, transport/progress presentation, spacing, metadata balance,
lyrics typography/contrast/current-line hierarchy and integration.

V4 reduces the Now Playing hero from 350 px to 320 px artwork and tones title/artist scale
down slightly so metadata and lyrics breathe. The transport bar gains one clear primary
play/pause control, quieter secondary actions and a purpose-styled seek track. Lyrics tools
lose unnecessary primary-button emphasis; the current line remains dominant while distant
lines recede further. Timing, seeking and lyric-source behavior are unchanged.

### V5 — Album Wall and Music Map

Polish Album Wall without changing its interaction model. Simplify Music Map until it no
longer reads as a graph/debug surface. Remove visual information rather than inventing
spatial concepts.

V5 keeps the existing pan/zoom, selection, routing and layout models intact. Album Wall gains
a softer frameless depth field, calmer sleeve hover/borders, properly elided album/artist text
and quieter secondary controls/instructions. Music Map uses the same restrained depth language,
elides long track/artist labels, removes always-visible BPM/energy debug copy from cards,
softens non-selected borders and sonic edges, and keeps route/current/selected emphasis strong.
No Chiasm navigation, graph-layout redesign or rendering architecture change is included.

### V6 — Whole-app visual QA

Inspect major user-facing screens at realistic window sizes for clipping, wrapping,
margins, icon scale, loading flashes, scrollbars, card consistency, hover/selection states,
placeholder quality and resize defects. Run existing behavioural/performance/regression gates.

## Stop condition

Campaign V is complete when the major screens share a coherent visual language; library
browsing, Now Playing/Lyrics, Album Wall and Music Map look intentionally designed; common
window sizes show no obvious visual defects; and existing functionality/performance gates
remain green.

Do not create V7 merely because more redesign is possible. Record larger ambitions
separately.
