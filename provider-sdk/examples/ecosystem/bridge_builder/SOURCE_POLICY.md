# Source / Privacy Policy — Bridge Builder

This plugin has no network source and requests no filesystem access.

Melodex supplies only ephemeral refs, display metadata, Flow analysis values and coarse taste counters. Absolute paths and database identifiers stay inside Melodex Core.

All scoring is local deterministic Python code. No audio or listening history leaves the device.

## Runtime boundary

The current Melodex extension process provides fault isolation, not a complete operating-system sandbox. This reference extension itself performs no network or filesystem operations beyond its packaged code/fixture files; the privacy guarantee here is specifically that Melodex Core does not broker local paths, database keys or absolute listening timestamps in the `library.suggest` request.
