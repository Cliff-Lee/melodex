# Melodex UX Redesign

This document defines the product-level UX direction for Melodex. It is deliberately about behaviour and information architecture before visual polish.

## Product promise

**Melodex should initially feel like a beautiful music player. Only gradually should the listener discover that it is also a programmable, extensible music system.**

The normal interface exposes intentions. Technical architecture remains available through contextual details and Power tools.

## Behavioural profiles

### Listener

Goal: hear something good with almost no setup.

Primary tasks:
- resume listening;
- play something familiar;
- ask Melodex to choose;
- skip, keep or love a track.

The Listener should not need to understand Flow, providers, analysis, routing or plugins.

### Collector

Goal: browse and rediscover a personal collection.

Primary tasks:
- browse albums visually;
- find an artist, album or track;
- play complete albums in order;
- inspect editions and metadata;
- rediscover forgotten records.

Artwork and stable spatial organisation are central.

### Explorer

Goal: move beyond the obvious.

Primary tasks:
- find similar music;
- deliberately move toward stranger or older music;
- explore Album Wall and Music Map;
- build a listening journey.

Advanced exploration is revealed from simple entry points rather than exposed all at once.

### Tinkerer

Goal: control the system itself.

Primary tasks:
- configure source priority;
- install providers and capability extensions;
- tune Flow/routing;
- inspect diagnostics and metadata;
- use APIs, bridges and local AI.

The Tinkerer gets the same application with **Power tools** enabled rather than a separate product.

## Design principles

The redesign synthesises several established UX traditions.

### Norman — conceptual model, affordance and feedback

The conceptual model is:

> Melodex is my music world. Sources tell it where music can come from; My Music is what I own; Explore lets me look around; Journeys decide where listening goes.

Controls should describe results, not internal mechanisms. Every long-running operation must explain what is happening, whether it is local/networked, and when it is complete.

### Nielsen — visibility, consistency and error prevention

- consistent actions and terminology across screens;
- visible loading/analysis/search state;
- human-readable failures first, diagnostics second;
- destructive actions behind explicit confirmation;
- no silent network work for expensive metadata operations.

### Cooper / Goodwin — goal-directed design

Navigation follows listener goals rather than software modules.

Normal navigation:
1. Home
2. My Music
3. Explore
4. Journeys
5. Playlists
6. Sources & plugins

Now Playing is reached from the persistent player. Search, Album Wall, Music Map, Moments, Ask Melodex and other capabilities remain available contextually.

### Krug — do not make the user think

Every page should have an obvious next action. Avoid rows of equal-weight buttons. Prefer one primary action, a small number of secondary actions and a More/Advanced path.

### Wroblewski — progressive disclosure

Three layers:

1. **Immediate** — common actions.
2. **Contextual** — actions revealed by selecting something.
3. **Power** — advanced controls explicitly enabled by the user.

### Laurel — interface as experience

Listening is the experience. Artwork, lyrics and subtle visual identity should dominate Now Playing and browsing surfaces. Technical panels recede until requested.

### Weinschenk — recognition, attention and decision load

- artwork before filenames;
- a few meaningful choices before numerical settings;
- stable visual position where possible;
- strong hierarchy and generous empty space;
- no permanent instructions when a contextual tooltip is enough.

### Young / Hall — mental models and research

Use listener language: “Play something”, “Explore”, “Plan a route”, “Find album details”.

Test behaviour, not preference. A useful usability session gives a first-time user tasks such as:
- play a local album;
- find something similar;
- create a 30-minute session;
- add a new source;
- find an old favourite.

Observe hesitation and errors.

## Information architecture

### Sidebar

Normal mode:

- Home
- My Music
- Explore
- Journeys
- Playlists

Then separated near the bottom:

- Sources & plugins
- Power tools toggle

Not permanent sidebar destinations:
- Now Playing — open from the persistent player;
- Play for me — a Home experience;
- Discover — inside Explore;
- Album Wall / Music Map — inside Explore;
- Moments — inside My Music / Now Playing;
- Ask Melodex — contextual/global;
- technical provider controls — Power tools.

### Home

Answers only:

1. **What can I play now?**
2. **What was I doing?**
3. **Where can I explore next?**

### My Music

Default: visual Albums grid.

Secondary views: Artists, Tracks.

File paths, source IDs and technical metadata stay out of the primary view.

### Explore

Simple entry points:
- Search everything;
- Album Wall;
- Music Map.

The advanced Music Map controls remain available once the user enters that tool.

### Sources & plugins

Normal mode presents source cards, status and simple actions.

Power tools reveals:
- provider priority;
- plugin install/remove;
- bridge;
- diagnostics;
- configuration and health detail.

## Interaction rules

### Primary actions

Each page should have at most one visually dominant primary action.

### Tooltips

Tooltips explain purpose and consequence, not merely repeat the label.

Example:

**Analyse my library**

> Analyses tempo, dynamics and other sonic characteristics on this computer so Flow and maps can make better choices. Your audio is not uploaded.

### Empty states

Empty areas teach the next useful action.

Bad:
> empty list

Good:
> You have not saved a journey yet. A journey is a listening route that changes gradually rather than shuffling randomly. **Design a journey**

### Network transparency

When an action may make network requests, its tooltip or confirmation should say so.

### Spatial stability

Album Wall positions should remain stable for a given lens and analysis state. Avoid feed-like reordering that destroys spatial memory.

## First implementation milestone

The first implementation establishes the system rather than redesigning every advanced tool at once:

- simplified navigation;
- persistent Power tools preference;
- active navigation state;
- visual My Music album browser;
- Home built around listening intentions;
- Explore hub;
- artwork in the persistent player;
- rich, explanatory tooltips;
- Now Playing defaults to artwork/details before visualisation;
- friendlier Sources surface with advanced controls hidden;
- clearer empty states;
- reusable visual components.

Subsequent milestones can redesign Music Map, Journeys, Playlists and source configuration in more depth using the same interaction grammar.
