# Openverse Audio Example

A Melodex MPP 1.0 provider that searches Openverse's openly licensed audio index and resolves media for playback.

Version 0.1.2 follows the upstream media redirect before handing the resource to Melodex. Openverse indexes audio hosted across many independent sites, and some of those URLs redirect to a CDN host; resolving that final URL inside the provider keeps playback compatible with Melodex's guarded playback gateway.

Try searches such as `ambient`, `field recording`, `classical`, or `jazz`.

The provider preserves the upstream landing page, source/provider, licence URL, attribution string, tags and genres in track metadata. It deliberately does **not** advertise offline capability: Melodex should not infer download rights from an index result alone.

For deterministic testing:

```bash
MELODEX_EXAMPLE_FIXTURES=1 melodex-provider doctor .
```

Openverse warns that licence metadata can be inaccurate; users should verify the source licence before reuse.
