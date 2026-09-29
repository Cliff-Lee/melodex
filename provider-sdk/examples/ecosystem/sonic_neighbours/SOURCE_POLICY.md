# Source / Privacy Policy — Sonic Neighbours

This plugin has no network source and requests no filesystem access.

Input is supplied by Melodex Core as a bounded sanitized snapshot containing:

- ephemeral request-local refs such as `t17`;
- title / artist / album display metadata;
- Flow analysis values;
- coarse taste counters and relative recency.

Melodex does **not** send absolute paths, provider IDs, database keys or absolute listening timestamps to this plugin.

All ranking is deterministic local Python code. No audio, history or metadata leaves the device.
