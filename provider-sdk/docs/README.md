# Provider SDK Documentation

This index separates **current implementation guidance**, **design targets**, and **historical migration notes**.

For the ecosystem-wide maturity/trust picture, see [Melodex status, stability and trust](../../docs/developers/00_STATUS_AND_STABILITY.md).

## Start here

- [Provider SDK README](../README.md)
- [Provider developer guide](04_PROVIDER_DEVELOPER_GUIDE.md)
- [Messy provider playbook](10_MESSY_PROVIDER_PLAYBOOK.md)
- [Playback Gateway](11_PLAYBACK_GATEWAY.md)
- [Legal/open reference sources](12_LEGAL_REFERENCE_SOURCES.md)

## Current protocol / compatibility / security guidance

- [Architecture](01_ARCHITECTURE.md) — current concepts plus some historical proposed package-layout context
- [Security and trust](05_SECURITY_AND_TRUST.md)
- [Protocol compatibility](09_PROTOCOL_COMPATIBILITY.md)
- [Release and repository policy](08_RELEASE_AND_REPOSITORY_POLICY.md)
- [LLM integration](06_LLM_INTEGRATION.md)

## Design-target documentation

These pages describe intended cross-platform/user-experience direction. They should not be read as a guarantee that every described flow is currently shipped.

- [Source UX](02_USER_EXPERIENCE.md)
- [Platform matrix](03_PLATFORM_MATRIX.md)

## Historical migration record

- [Melodex v15 migration](07_MELODEX_V15_MIGRATION.md)

That migration document is retained to explain how the source-neutral architecture emerged. It is not the current developer entry point.

## Machine-readable specifications

Outside this folder:

- `../spec/provider_manifest.schema.json`
- `../spec/catalog_item.schema.json`
- `../spec/track.schema.json`
- `../spec/mpp-jsonrpc.md`
- `../spec/openapi.yaml`
- `../spec/extensions/v0.1/`

## If two documents disagree

Prefer, in order:

1. current code/tests and machine-readable schemas;
2. [Status, stability and trust](../../docs/developers/00_STATUS_AND_STABILITY.md);
3. current SDK developer/security/compatibility docs;
4. design-target or historical documents.

Please open a documentation issue when you find a mismatch.
