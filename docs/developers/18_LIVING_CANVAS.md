# Living Canvas and visualizers

## Product design

Melodex treats a recording as a place that can be revisited. A track keeps a stable visual identity, while its cached musical features, cover palette, playback position, lyrics and nearby listening context shape the view around it. The visualizer is useful during playback and still tells a story when audio analysis or artwork is unavailable.

The Now Playing **Living Canvas** is one surface with selectable modes:

| Mode | What it shows | Data source |
| --- | --- | --- |
| Living | A gently moving membrane and particles shaped by energy, brightness and rhythm | Stable track profile; cached Flow features when present |
| Fingerprint | A quiet, repeatable song sigil | Normalized artist, title and duration; cached features refine it |
| Journey | The track's cached energy contour with a seekable position marker | Existing Flow cache and player position |
| Constellation | The current track among nearby tracks and recent listening | Queue and local history, capped at 24 neighbours |
| Lyrics | A large, calm lyric line with nearby lines | Existing local synced lyrics; untimed text is paced gently and labelled as untimed |
| Album World | A deterministic terrain or orbit scene in the cover's colour palette | Track fingerprint, cached Flow and a palette sampled once from artwork |
| Sonic Weather | A compact description and scene for the track's motion, density, brightness and warmth | Cached Flow, with explicit identity-only fallback |
| Visual Memory | A local atlas grouped into listening sessions and periods | Existing local listening history; no new tracking is added |
| Minimal | Cover-derived colour, identity and progress with no continuous animation | Track metadata and player state |

The same track returns to the same underlying fingerprint. Playback position and phase may animate its world, but do not change the identity seed. Journey remains a navigation control, not a decorative waveform. The constellation uses tracks Melodex already knows from the queue and local history; it does not perform online recommendations. Visual Memory is local-only and reads the existing listening history.

## Shared data boundary

The built-in canvas composes small values: a privacy-safe profile, current position and duration, a bounded colour palette, a current lyric frame where available, a capped neighbour list, and aggregated listening-memory marks. No display model contains filesystem paths, network handles, provider credentials or audio samples. Lyric text is passed only to the built-in Lyrics mode and is never exposed to `.mdxviz` recipes.

Track identity is generated from normalized artist, title and a coarse duration bucket. Flow analysis is read only from `FlowEngine.cached_analysis_for` on a worker thread. Visualizer code never calls `analysis_for`, decodes media, reads samples, performs FFT work, or blocks the audio player. A missing cache produces an identity scene and a clear message; Melodex does not analyse media just to animate it.

Album colours are sampled once from a 24 × 24 image when the artwork stage loads; only the small palette is retained by the view. If artwork is missing, the stable fingerprint supplies a restrained fallback palette. Local history is read only when Constellation or Visual Memory is selected, on a worker thread, and is capped before it reaches the renderer. The renderer receives sanitized neighbour labels or aggregated memory marks, never history records.

## Rendering and performance budget

- QPainter uses bounded geometry: at most 64 contour points, 32 plugin layers, 24 constellation neighbours and 128 Visual Memory marks.
- Normal quality is capped at 15 frames per second. Eco uses fewer marks and a lower frame rate; High is an explicit opt-in capped at 30 fps; Battery pauses continuous animation and keeps a static identity view.
- Static modes repaint only on track, position, palette or selection changes. The timer runs only for a visible, playing animated mode; it stops on pause, hidden tab, minimized window, natural end, or Battery mode.
- Frame state is prepared outside `paintEvent`; painting performs no disk, database, network or audio work.
- The player, decoder and audio thread never wait for visual work. Seeking continues through the existing player API.
- Every scene has an identity-only fallback. Metadata lookup and artwork download are never required for playback or rendering.

## Visualizer extension format: `.mdxviz` v1

An `.mdxviz` file is a UTF-8 JSON scene recipe. It contains a versioned manifest and a short list of supported primitives (`contour`, `orbit`, `terrain`, `rings` and `glyphs`). Primitive parameters use bounded numbers and named snapshot features; they cannot contain expressions, scripts, HTML, executable code, external assets or URLs. Melodex validates the file, limits it to 64 KiB and 32 layers, and renders it with the same QPainter budget as built-in modes.

This makes personal visualizers installable from a local file while keeping the audio path isolated and the renderer predictable. The first format is intentionally declarative: plugins cannot access lyrics, local paths, history, the network or playback controls. A future format can add capabilities only through a new reviewed API version.

See the format, starter recipe and author guide in [Visualizer plugins](../visualizers/README.md).

## Privacy and control

Visual Memory uses the listening history already stored on the device. It does not upload plays, artists, lyrics, audio features or fingerprints. Constellation neighbours come from the current queue and local listening history. Installing an `.mdxviz` file copies its bounded JSON recipe into Melodex's local visualizer directory; the file is data, not executable code.

Users can choose Minimal or Battery mode at any time. Hiding the Canvas stops animation. The normal player controls and keyboard-accessible Journey slider remain available independently of the selected scene.
