# Humanize Melodex

This campaign is about making Melodex feel authored rather than generated.

It does **not** remove the underlying power. It changes what the product chooses
to foreground.

## Product position

> Melodex is a local-first music player with unusually deep discovery and
> extensibility.

The normal experience should feel complete before the user discovers plugins,
AI, route planning, diagnostics or developer surfaces.

## What creates an "AI-made" impression

The audit found five recurring signals:

1. too much explanatory copy inside the application;
2. several equally weighted features competing for attention;
3. AI-specific actions presented as first-class product identity;
4. internal/system language leaking into listener-facing surfaces;
5. documentation that encourages users to sample features instead of simply
   listening to music.

## Rules

### Say less

Page subtitles establish context in one sentence. Detailed explanations belong
in tooltips, help, or documentation.

### One obvious action

A normal page should have one clear primary action. Secondary actions should
look secondary.

### Music first

Artwork, album/artist identity, playback and the current listening context take
precedence over system architecture.

### AI is optional

AI integration remains useful, but it should never make Melodex look like an AI
demo with a music player attached.

### Technical language is earned

Provider IDs, routing, manifests, diagnostics, bridge controls and plugin
internals stay behind Power tools or developer documentation.

### Keep the quirks that matter

Album Wall, Flow, Music Map and Journeys can remain distinctive. Humanizing the
product means giving those ideas a consistent voice and hierarchy, not sanding
away everything unusual.

## Campaign stages

### H1 — Voice and hierarchy

- reduce persistent explanatory text;
- simplify Home, Explore, Journeys, Playlists and Sources;
- make ordinary playlist import primary and AI paste secondary;
- simplify onboarding and tester instructions;
- establish this product-language contract.

### H2 — Visual consistency

Audit spacing, typography, button hierarchy, card density, icons, radii and
empty/loading/error states. Remove one-off styling that makes neighbouring
surfaces feel designed by different systems.

### H3 — Feature disclosure

Move experimental/deep controls out of normal first-run paths. Check Album Wall,
Music Map, Journeys, Now Playing and Sources for controls that should appear
only after selection, inside More, or under Power tools.

### H4 — Real-world texture

Replace synthetic/demo-like examples and generic copy with realistic states.
Improve empty, partial-metadata, offline, NAS, broken-artwork and mixed-source
experiences.

### H5 — First-run usability

Run a first-time-user walkthrough against five tasks:

1. add music;
2. play an album;
3. find another artist;
4. understand what is playing;
5. discover one deeper Melodex feature without being prompted.

Record hesitation points and fix those rather than adding more features.

## Non-goals

- no scanner/index/NAS architecture changes;
- no broad visual rewrite;
- no removal of advanced features merely because they are unusual;
- no fake minimalism that makes useful capabilities harder to reach.
