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


## H2 visual grammar

The first H2 pass standardises the visible shell without changing Melodex's
overall dark visual identity.

Rules introduced:

- page titles, subtitles, section headings, panel headings and muted supporting
  copy use shared object styles rather than one-off inline CSS;
- primary, secondary and quiet actions have visibly different weight;
- secondary buttons should not compete with a page's main action;
- common cards and panels use a consistent 12 px corner radius;
- card and empty-state padding is slightly tighter so screens feel designed
  rather than assembled from oversized generic components;
- supporting card copy is deliberately quieter than titles and actions;
- the visual system keeps the player, artwork and current musical context more
  prominent than explanatory chrome.

H2 should continue by removing remaining one-off styling only where doing so
makes adjacent surfaces visibly more coherent. It is not a mandate to flatten
distinctive tools such as Album Wall or Music Map into generic cards.


## H3 progressive disclosure

H3 treats complexity as something the user earns by asking for it.

Rules:

- optional/plugin catalogues should not occupy permanent screen space when one
  clear "Add features…" action can reveal them;
- maintenance controls such as map/wall options should look quieter than
  playback actions;
- route planning should present one obvious next step at a time: choose
  endpoints, find a route, then play or queue it;
- clear/hide/configuration actions should not compete visually with the task
  itself;
- technical and rarely used source controls remain behind global Power tools;
- deeper journey shaping remains behind Journey options rather than expanding
  whenever Music Map opens;
- Now Playing should describe the music, not explain the existence of every tab.

Progressive disclosure is not feature removal. Every existing H3 action remains
reachable.


## H4 real-world states

H4 assumes users have imperfect libraries and imperfect networks.

Rules:

- describe the state before naming the subsystem that produced it;
- avoid provider names such as MusicBrainz in ordinary empty/error copy unless
  provenance is the point of the screen;
- empty states should state what is missing and offer the next useful action;
- a folder with no playable music should not sound like a scanner failure;
- background persistence language should reassure rather than narrate internal
  indexing architecture;
- missing lyrics, artwork and artist information are normal content states, not
  exceptional system failures;
- diagnostics and provenance remain available where they are genuinely useful.

The first H4 pass applies these rules to My Music scanning and rich Now Playing.
