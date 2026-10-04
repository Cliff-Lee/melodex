# Chiasm

**Move through your music.**

Chiasm is an experimental spatial music experience derived from Melodex.

## Product idea

Your music collection is a place rather than a catalogue.

The primary experience is a calm spatial field in which the user can move, focus, listen, follow relationships, hand control to Autopilot, open lyrics without losing context, and later retrace the route they took.

## Design doctrine

- The collection is the interface.
- Direct manipulation before permanent controls.
- Movement replaces page navigation.
- Detail follows attention.
- Motion must communicate state.
- Preserve stable geography and spatial memory.
- Use ordinary 2D/2.5D engineering, not a heavyweight 3D engine.
- Responsiveness beats visual richness.
- Administrative workflows may remain conventional.
- The world should mostly rest; movement follows user intent or Autopilot.
- Spatial UX must remain usable on ordinary computers.

## Internal vocabulary

- **Field** — the collection space.
- **Arc** — the active or Autopilot route.
- **Horizon** — peripheral and unresolved musical possibilities.
- **Trace** — exploration history.

## First prototype

Do not begin by rebuilding Melodex.

Start with a deliberately isolated prototype:

1. 50 album covers.
2. Full-window spatial field.
3. Drag to pan.
4. Pointer-centred zoom.
5. Hover for glance.
6. Click for focus.
7. Double-click for play/mock play.
8. Escape to release focus.
9. Almost no permanent UI.
10. No 3D camera, particles, physics, lyrics, provider work, or multiple lenses.

### First acceptance test

The prototype should already feel enjoyable to explore for five minutes before any additional visual or product complexity is added.

## Relationship to Melodex

Melodex remains the stable existing application.

Chiasm should initially reuse proven Melodex library, playback, caching and provider foundations while experimenting with a radically different interaction model.

No production Melodex behavior should be changed merely to satisfy the Chiasm prototype.
