# Source / Privacy Policy — Musical Detours

This plugin uses no remote source and requests no network or filesystem access.

Melodex supplies ephemeral track refs, display metadata, cached Flow values and coarse taste counters. Absolute local paths, provider IDs, database keys, raw audio and absolute listening timestamps are not part of the request.

All scoring is deterministic Python code. The fixture is synthetic and exists only for tests. No audio or listening history leaves the device.

## Runtime boundary

The extension process provides fault isolation, not a complete operating-system sandbox. The plugin itself does not open user files or make network requests; it only uses the profile passed by Melodex and its packaged code.
