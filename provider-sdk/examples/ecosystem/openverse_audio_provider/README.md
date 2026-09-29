# Openverse Audio Example

A Melodex MPP 1.0 provider that searches Openverse's openly licensed audio index and resolves the media URL returned by Openverse.

Try searches such as `ambient`, `field recording`, `classical`, or `jazz`.

The provider preserves the upstream landing page, source/provider, licence URL, attribution string, tags and genres in track metadata. It deliberately does **not** advertise offline capability: Melodex should not infer download rights from an index result alone.

For deterministic testing:

```bash
MELODEX_EXAMPLE_FIXTURES=1 melodex-provider doctor .
```

Openverse warns that licence metadata can be inaccurate; users should verify the source licence before reuse.
