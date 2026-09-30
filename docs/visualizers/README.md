# Build a `.mdxviz` visualizer

Melodex visualizers are small JSON scene recipes. They let authors create distinct, reactive scenes without shipping code that can access a user's library, files, lyrics, network or player controls.

## Try the example

1. Open **Now Playing → Living Canvas**.
2. Select **Add visualizer…** and choose [`orbit-garden.mdxviz`](examples/orbit-garden.mdxviz).
3. Choose **Orbit Garden** in the visualizer selector.
4. Play a local track with cached Flow analysis to see the scene respond to its profile. Without cached analysis, the same scene uses the track's stable identity and fallback palette.

The button copies the validated JSON file into Melodex's local visualizer directory. It does not execute code or load external assets. Select an installed visualizer to show **Remove**, then choose it to uninstall the recipe.

## File format

An `.mdxviz` is a UTF-8 JSON file up to 64 KiB:

```json
{
  "format": "mdxviz",
  "api_version": 1,
  "manifest": {
    "id": "org.example.orbit-garden",
    "name": "Orbit Garden",
    "author": "Example",
    "description": "A small palette-driven world."
  },
  "scene": {
    "layers": [
      {"type": "rings", "count": 3, "gain": 0.18, "feature": "energy", "palette": 0, "speed": 0.05},
      {"type": "orbit", "count": 12, "gain": 0.3, "feature": "rhythm", "palette": 1, "speed": 0.08}
    ]
  }
}
```

The complete starter recipe is [`examples/orbit-garden.mdxviz`](examples/orbit-garden.mdxviz).

### Manifest

- `id`: unique lowercase identifier using letters, digits, `.`, `_` or `-`;
- `name`: display name;
- `author`: attribution text;
- `description`: short plain-text description.

### Scene layers

Every layer has a supported `type` and may set:

| Field | Meaning | Range |
| --- | --- | --- |
| `count` | Number of bounded marks, rings or traces | 1–24, with a lower cap for terrain and contours |
| `gain` | Scene response to the selected feature | 0–0.5 |
| `feature` | `energy`, `brightness`, `rhythm`, `progress` or `tempo` | Named value |
| `palette` | Index into the cover-derived palette | 0–5 |
| `speed` | Slow animation rate multiplier | 0–0.25 |

Supported layer types are `contour`, `orbit`, `terrain`, `rings` and `glyphs`. Melodex caps files at 32 layers, 128 marks, about 4,096 scene points, and 64 installed recipes. The renderer is capped at 30 fps even in High quality. Unknown fields are rejected, so recipes cannot add scripts, expressions, HTML, external URLs or assets.

## Data and permissions

Recipes receive only normalized visual features and a bounded palette. They cannot access lyrics, artist or track history, filesystem paths, audio samples, credentials, network resources, or playback controls. Flow values are read from Melodex's existing cache; `.mdxviz` cannot request analysis of an uncached track. The renderer uses the app's bounded QPainter scene and does not create an extension process.

## Compatibility

`api_version` is a breaking-contract version. Melodex 0.4 implements version 1. A recipe with another version or unsupported fields remains uninstalled and produces a validation message. The example file is the recommended base for a new recipe.
