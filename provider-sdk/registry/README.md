# Melodex Plugin Registry

This directory contains the canonical registry format and first-party reference packages.

## Files

```text
registry.json
plugin-registry.schema.json
packages/
```

`example-registry.json` is retained as a schema/example fixture and currently mirrors the canonical registry.

## Validate

Install the SDK in development mode:

```bash
python -m pip install -e '.[dev]'
```

Then:

```bash
melodex-registry validate registry/registry.json
melodex-registry summary registry/registry.json
```

Verify the first-party packages:

```bash
melodex-registry verify-packages \
  registry/registry.json \
  --packages registry/packages
```

## Community packages

Community authors normally host package files in their own repository/release infrastructure.

A registry entry points to that HTTPS package and records its SHA-256.

The `packages/` folder exists primarily for small first-party/reference examples used to bootstrap and test the ecosystem.

## Do not edit hashes by hand

Build/publish the exact package first, calculate its SHA-256 and byte size, then update the registry entry.

A registry PR whose hash does not match a repository-hosted reference package should fail tests.

See [Registry governance](../../docs/developers/17_REGISTRY_GOVERNANCE.md).
