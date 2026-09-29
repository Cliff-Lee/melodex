# Source / Privacy Policy — Forgotten Favourites

This plugin has no network source and requests no filesystem access.

Melodex supplies sanitized, request-local track profiles. The plugin receives relative recency in days rather than absolute listening timestamps and never receives the listening-history database or local file paths.

Ranking is deterministic local Python code. Nothing is uploaded.

## Runtime boundary

The current Melodex extension process provides fault isolation, not a complete operating-system sandbox. This reference extension itself performs no network or filesystem operations beyond its packaged code/fixture files; the privacy guarantee here is specifically that Melodex Core does not broker local paths, database keys or absolute listening timestamps in the `library.suggest` request.
