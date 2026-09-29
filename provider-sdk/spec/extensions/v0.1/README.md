# Experimental Extension Contracts v0.1

These schemas are additive and intentionally separate from the current
Provider SDK / MPP manifest.

Capability methods:

```text
identity.resolve
metadata.enrich
artwork.lookup
lyrics.lookup
```

Optional extension-level method:

```text
extension.health
```

An extension declares active health separately from its capability contracts:

```json
{
  "health": {
    "contract_version": "0.1",
    "method": "extension.health"
  }
}
```

This deliberately keeps health out of capability ranking/filtering. Extensions that omit the declaration remain valid and Melodex falls back to a process-start check.

A health response must report whether it actually checked an upstream service using `upstream_checked`. This lets Melodex distinguish a real connectivity check from an extension-local self-check.

Shared entity/provenance/cache types are in `common.schema.json`.
