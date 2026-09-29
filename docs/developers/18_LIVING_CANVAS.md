# Living Canvas

## Design

Living Canvas treats each track as a repeatable visual place. Its first built-in view combines a deterministic contour with a seekable energy journey. Track identity supplies a stable seed; cached Flow features shape the contour and journey; the existing cover-art accent colours the scene when artwork is available.

The view is intentionally track-aware rather than a literal real-time spectrum display. It does not inspect decoded audio samples or run an FFT during playback.

## Data flow

- **Identity:** normalized artist, title and duration produce a stable fingerprint. Local paths and database keys are excluded.
- **Flow:** Now Playing requests only `FlowEngine.cached_analysis_for`, on a worker thread. It never calls `analysis_for` from the visualizer, because that method may decode and analyse an uncached file.
- **Artwork:** the existing 24 × 24 cover sampling pass supplies one accent colour. Missing artwork uses a deterministic colour from the fingerprint.
- **Playback:** the player sends position, duration and play/pause state through its existing signals. The energy contour is drawn as a seek slider and delegates seeking back to the player.
- **Fallback:** if Flow has no cached record, the deterministic identity scene still appears. The journey contour reports that Flow analysis is unavailable instead of inventing track structure.

## Performance budget

- QPainter draws a fixed 48-point contour, three outlines and 14 small points; it creates no frame-sized image.
- A 67 ms timer gives a 15 fps ceiling. The timer runs only while the Living Canvas tab is visible and playback is active.
- Pausing playback, hiding the tab or minimizing the window stops the timer. Seeking updates the scene from the player's existing 100 ms position signal.
- The audio output and decoder do not call or wait for the renderer.
- Flow cache lookup runs in a daemon worker, and the result is applied only if it still belongs to the current track.

## Scope and future extension

This release adds a built-in renderer, not a public `.mdxviz` package API. The profile model is kept free of Qt and local paths so it can be tested independently and can inform a future renderer contract. A public visualizer extension format should be designed after this data boundary and performance behavior have proved stable.
