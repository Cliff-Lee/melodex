# Sonic Neighbours

A fully local `library.suggest` plugin for “more like this” discovery.

It never reads audio files itself. Melodex supplies sanitized Flow features for the seed and candidate tracks, and the plugin ranks nearby tracks by:

- energy;
- tempo compatibility;
- tonal compatibility;
- spectral/timbral proximity;
- onset density;
- mixability.

The response contains only ephemeral track refs, scores and short reasons. Melodex maps those refs back to the user's library.
