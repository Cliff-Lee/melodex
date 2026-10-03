# Visual performance contract

Campaign 13 visuals are deliberately designed to be opportunistic UI work. Audio
playback and ordinary navigation have priority over decorative rendering.

## Default budgets

| Quality | Target cadence | Detail cap | Particle cap | Glow cap | Lyric artwork cache |
| --- | ---: | ---: | ---: | ---: | ---: |
| Auto | 15 fps | 48 | 24 | 8 | 960 px |
| Auto reduced | 12 fps | 32 | 16 | 4 | 640 px |
| Eco | 10 fps | 32 | 12 | 4 | 480 px |
| High | 30 fps | 48 | 32 | 12 | 1280 px |
| Battery | static | 24 | 8 | 2 | 360 px |

"px" is the maximum long edge of the cached, intentionally soft Lyric Flow
artwork backdrop. It is not the screen resolution.

The caps apply to procedural work, not to semantic data. For example,
Constellation may still contain 24 meaningful nodes, while atmospheric motes or
glow passes stay bounded.

## Auto quality governor

Auto measures QPainter work after each frame.

- A single slow frame does nothing.
- Three consecutive paints above the Auto paint budget reduce the scene.
- Reduced Auto lowers detail, particles, glow count, artwork-cache size and
  animation cadence together.
- Recovery requires 72 consecutive inexpensive paints.
- Explicit Eco, High and Battery choices never auto-switch underneath the user.

This hysteresis avoids oscillating quality when resizing, opening a hover card or
encountering one expensive text-layout frame.

The governor is renderer-only. It does not pause, resample or otherwise touch
audio playback.

## Rendering rules

Campaign 13 scenes should prefer:

- cached deterministic geometry;
- small bounded particle sets;
- a handful of radial glows rather than arbitrary blur effects;
- low-resolution artwork for atmospheric backgrounds;
- cached Flow/profile data rather than live analysis;
- layout work only when inputs change;
- no animation timer when paused, hidden, minimized or in Battery mode.

Track Sigil geometry remains deterministic and cheap. Constellation artwork is
loaded only for interacted nodes. Memory Atlas is static unless the user
interacts with it.

## Probe

A repeatable offscreen paint probe is available:

```bash
python scripts/visual_performance_probe.py --width 1280 --height 720 --frames 60
```

Useful variants:

```bash
python scripts/visual_performance_probe.py --quality eco
python scripts/visual_performance_probe.py --quality high --width 1920 --height 1080
python scripts/visual_performance_probe.py --width 2560 --height 1440 --output /tmp/visuals.json
```

It reports mean, median, p95 and peak paint time for the public built-in scenes.
The probe does not decode or play audio; it isolates visual rendering cost.

Absolute CI timing is intentionally not a release gate because virtualized
runner graphics vary too much. CI instead gates the deterministic resource
bounds and quality-governor behavior. Real paint timings can be compared on the
same machine before and after visual changes.

## Regression expectations

A visual change should not:

- remove the hard particle or glow bounds;
- allocate a full-screen artwork cache when a soft bounded cache is sufficient;
- add a separate audio-analysis loop;
- keep a visual animation timer alive when the scene is not visible;
- perform network I/O from paint or pointer-move handlers;
- make an Auto reduction change the meaning of a visualization.

Quality reduction may simplify atmosphere, never semantics.
