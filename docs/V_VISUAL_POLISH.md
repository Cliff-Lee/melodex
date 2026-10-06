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

### V2 — Application shell and navigation

Polish the existing sidebar, selected/hover state, page headers, group spacing, alignment,
dividers and resize appearance without changing navigation architecture.

### V3 — Main library surfaces

Polish Albums, Artists, Tracks, Search, Playlists and Sources where visually necessary.
Prioritize artwork prominence, card/row proportions, spacing, hierarchy, truncation,
loading/empty states and invisible cached-artwork hydration.

### V4 — Now Playing and Lyrics

Cosmetic pass only: hierarchy, transport/progress presentation, spacing, metadata balance,
lyrics typography/contrast/current-line hierarchy and integration.

### V5 — Album Wall and Music Map

Polish Album Wall without changing its interaction model. Simplify Music Map until it no
longer reads as a graph/debug surface. Remove visual information rather than inventing
spatial concepts.

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
