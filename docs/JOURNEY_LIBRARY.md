# Journey Library

Journey Library gives Melodex two different kinds of journey memory:

1. **Recipes** — reusable, portable journey intent;
2. **Runs** — private local records of what actually happened while listening.

They are deliberately separate.

A recipe is something you may choose to share.

A run contains personal listening behavior and stays local.

## Recipes

A Journey Recipe stores:

- recipe name;
- optional description;
- Pathfinder routing mode;
- ordered semantic Journey Designer stages;
- optional exact-track waypoints.

It does **not** store start or destination tracks.

That is intentional. A recipe describes the **shape** of a journey so you can reuse it with new endpoints.

Example:

```text
Balanced
  ↓
Calm
  ↓
Darker
  ↓
Forgotten
  ↓
Energetic
```

You can later choose completely different start and destination tracks and apply the same recipe.

## Exact track waypoints

Recipes can also include exact track waypoints.

They are not saved using a local file path or Music Map ref.

Melodex writes a portable selector using:

1. MusicBrainz recording ID when available;
2. artist;
3. title;
4. album.

When the recipe is loaded, Melodex rebuilds Music Map and tries to match each exact waypoint onto the current library.

If an exact waypoint cannot be found, Melodex reports it by name. Semantic stages still load.

## The .mdxjourney format

Journey Recipes can be exported as:

```text
something.mdxjourney
```

The format is JSON.

Current schema version:

```json
{
  "melodex_journey": 1,
  "name": "Night arc",
  "description": "Start gently and end with energy",
  "routing_mode": "balanced",
  "stages": [
    {
      "type": "constraint",
      "constraint": "calm",
      "label": "Calm"
    },
    {
      "type": "constraint",
      "constraint": "dark",
      "label": "Darker"
    }
  ]
}
```

An exact waypoint looks like:

```json
{
  "type": "track",
  "label": "Specific waypoint",
  "selector": {
    "musicbrainz_recording_id": "...",
    "artist": "Artist",
    "title": "Track",
    "album": "Album"
  }
}
```

## What recipe export does not contain

The export deliberately excludes:

- absolute local file paths;
- Music Map ephemeral refs;
- provider-local playback IDs;
- stream URLs;
- playback headers/cookies;
- listening history;
- Love / Keep / skip counts;
- taste scores;
- rediscovery scores;
- private run history;
- Journey Live decisions.

The recipe may still reveal the semantic journey you designed and any exact songs you deliberately chose as waypoints.

Review a recipe before sharing it, just as you would any other file.

## Saving a recipe

Build or edit Journey Designer stages, then open:

**Journeys → Save current design**

Choose a name and optional description.

The current routing mode and stage sequence are saved locally.

If you loaded a saved recipe and then change its stages or routing mode, Melodex treats the result as a modified/unsaved design rather than falsely attributing future runs to the original recipe.

## Loading a recipe

Choose:

**Journeys → Load into Music Map**

Melodex refreshes Music Map first.

Then:

- routing mode is restored;
- semantic stages are restored;
- exact waypoints are rematched;
- unresolved exact waypoints are reported.

You still choose the start and destination for this run.

## Import and export

Use:

- **Import…**
- **Export…**

to move `.mdxjourney` files between Melodex installations.

Import validates the current recipe schema before saving it to the local Journey Library.

## Runs

Journey Runs are different from recipes.

A run records a specific Journey Live listening session.

Private local run state can include:

- recipe snapshot used for the run;
- original designed route;
- final adapted route;
- start/end status;
- timestamped adaptive events.

Example event sequence:

```text
start
steer: More energy next
manual skip
replan
avoid artist
replan
restore
replan
complete
```

This lets Melodex explain how the final listening path diverged from the design.

## Designed route versus final route

A run keeps portable route snapshots.

The **designed route** is the route present when Journey Live begins.

The **final route** combines the sequence actually reached with the latest adapted remaining plan when the run ends.

Routes are stored using portable track selectors rather than request-local Music Map refs.

That means a historical route can be rematched after Music Map is rebuilt.

## Inspecting a run

Open:

**Journeys → Recent runs → Inspect**

The inspector shows:

- run status;
- designed track order;
- final/adapted track order;
- whether the route changed;
- recorded adaptive decisions.

Examples:

```text
Steer · More energy next
Skip · Artist — Track
Avoid artist · Artist
Replan · manual skip
Restore designed route
```

## Replaying a run

Two replay actions are available:

- **Replay designed**
- **Replay final**

Melodex refreshes Music Map and rematches every historical track selector.

If every track is available:

- the historical route is redrawn;
- historical hop explanations are restored where available;
- playback starts in that historical order.

If one or more tracks are missing, Melodex reports the missing tracks instead of silently substituting different music.

Replay is therefore deterministic with respect to the recorded track identities.

## Journey Live event journal

Journey Live records only explicit adaptive decisions.

Examples include:

- start;
- steer;
- manual skip;
- avoid artist;
- successful replan;
- failed replan;
- restore;
- complete / stop.

Normal automatic track completion does not create an adaptive replan event.

## Privacy

Recipes and Runs have different privacy expectations.

### Recipe

Potentially shareable.

Contains only the portable recipe contract described above.

### Run

Private local state.

Contains personal listening decisions and the route actually taken.

Melodex does not automatically upload Recipes or Runs.

The current UI exports Recipes only.

There is intentionally no public/share action for run history in this first implementation.

## Relationship to playlists

A playlist says:

> Play these tracks in this order.

A Journey Recipe says:

> Make the listening experience follow this shape.

A Journey Run says:

> This is what happened when I actually followed and adapted that journey.

These objects solve different problems, so Melodex keeps them separate.

## Stability

Journey Recipe schema version 1 is implemented but still part of a preview feature surface.

Future schema versions should remain explicit rather than silently changing the meaning of existing `.mdxjourney` files.
