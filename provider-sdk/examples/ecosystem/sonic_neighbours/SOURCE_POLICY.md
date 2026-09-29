# Source / Privacy Policy — Sonic Neighbours

This plugin has no network source and requests no filesystem access.

Input is supplied by Melodex Core as a bounded sanitized snapshot containing:

- ephemeral request-local refs such as `t17`;
- title / artist / album display metadata;
- Flow analysis values;
- coarse taste counters and relative recency.

Melodex does **not** send absolute paths, provider IDs, database keys or absolute listening timestamps to this plugin.

All ranking is deterministic local Python code. No audio, history or metadata leaves the device.

## Runtime boundary

The current Melodex extension process provides fault isolation, not a complete operating-system sandbox. This reference extension itself performs no network or filesystem operations beyond its packaged code/fixture files; the privacy guarantee here is specifically that Melodex Core does not broker local paths, database keys or absolute listening timestamps in the `library.suggest` request.
