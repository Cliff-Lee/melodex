# Melodex Journey Recipe Registry

This directory is the canonical public registry for the **Journey Recipe Gallery**.

Journey Recipes are data, not executable plugins.

The Gallery therefore has a deliberately smaller trust surface than the Plugin Directory:

- every Recipe must validate against the current `.mdxjourney` schema;
- every registry entry includes a SHA-256 of canonical Recipe JSON;
- Melodex checks the hash again before adding the Recipe to a user's local Journey Library;
- blocked entries are hidden and cannot be added;
- the app has a bundled starter fallback when the online registry is unavailable.

## Contributing a Recipe

The easiest path is:

1. build a journey in Melodex;
2. save it in **Journeys**;
3. export it as `.mdxjourney`;
4. open the exported JSON and review what you are sharing;
5. add a registry entry in `journey-recipes/registry.json`;
6. run the registry checker and desktop tests;
7. open a pull request.

A Recipe intended for broad use should normally use semantic stages rather than exact-track waypoints, because exact tracks may not exist in another user's library.

## Required registry metadata

Each entry currently includes:

```text
id
name
version
author
description
tags
license
status
compatibility
source
sha256
recipe
```

Supported status values:

- `example`
- `community`
- `reviewed`
- `deprecated`
- `blocked`

These are registry metadata labels, not cryptographic publisher identity.

## IDs

Use a stable reverse-domain-style ID where practical:

```text
org.example.recipe.my-journey
```

Do not reuse another author's ID.

Changing the Recipe while keeping the same ID should increase its registry `version`.

## License

The registry entry must state the license for the Recipe definition itself.

The initial project examples use `CC0-1.0`.

A Recipe license does **not** grant rights to any music named in an exact-track waypoint.

## Hashing

The SHA-256 is calculated over the canonical validated Recipe JSON:

- UTF-8;
- sorted keys;
- no extra whitespace;
- `ensure_ascii=false`.

From the repository root:

```bash
PYTHONPATH=desktop python - <<'PY'
import json
from pathlib import Path
from melodex.journey_registry import recipe_sha256

data = json.loads(Path("my-recipe.mdxjourney").read_text("utf-8"))
print(recipe_sha256(data))
PY
```

## Validation

Run:

```bash
python scripts/journey_registry_check.py
PYTHONPATH=desktop pytest -q desktop/tests/test_journey_registry.py
```

Normal repository CI runs the same registry consistency check.

## Privacy review

Before publishing, verify that the Recipe does not contain information you did not intend to share.

The schema excludes Melodex-private fields such as:

- local file paths;
- playback URLs;
- provider-local IDs;
- taste scores;
- listening history;
- Journey Live run history.

However, a Recipe can intentionally reveal:

- its name and description;
- its semantic journey shape;
- its author field;
- exact artist/title/album selections when exact waypoints are used.

## No code execution

A Journey Recipe cannot declare Python/native entrypoints, permissions, network hosts, shell commands or plugin capabilities.

If a contribution requires executable behavior, it belongs in the provider/plugin ecosystem instead of the Journey Recipe Gallery.
