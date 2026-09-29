# Musical Detours

**Musical Detours** finds a local track that keeps one recognizable part of the current song while changing the rest. Follow the same pulse into a different harmonic colour, or keep the energy and move into a new texture.

This is deliberately different from **More like current**: it looks for a clear musical pivot, not the nearest sonic copy.

## How it works

The plugin compares locally supplied Flow features for tempo, energy, key, timbre, rhythmic density and mixability. A candidate must:

- share one strong feature with the current track;
- differ clearly in at least two other features;
- not be an explicit dislike.

Each result explains the shared feature and the two strongest contrasts. The shortlist limits repeated anchor types so it can show different kinds of detours.

## Try it

1. Add **Musical Detours** from **Sources → Explore plugins…**.
2. Analyse your local music from **Play for me → Analyse my library**.
3. Play a local track and select **Find a detour**.
4. Double-click a result to play it, or select it and add it to the queue.

Flow analysis is required for the seed and comparison tracks. Unanalysed candidates are skipped; the plugin does not guess from artist names or metadata alone.

## Privacy

The plugin has no network permission and requests no filesystem access. Melodex sends a bounded profile with ephemeral refs, display metadata, cached Flow features and coarse taste counters. It does not send audio, file paths, database keys or absolute listening timestamps. The plugin returns refs and explanations; Melodex maps them back to local tracks.

The extension process provides fault isolation, not a complete operating-system sandbox.
