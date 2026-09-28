# Changelog

All notable changes to the public Melodex Provider SDK are documented here.

The SDK package is still 0.x. MPP `protocol_version: "1.0"` is a preview wire-contract identifier, not yet a frozen 1.0 compatibility commitment.

## [0.5.0] - 2026-09-28

### Added / changed

- Provider scaffolds now create `SOURCE_POLICY.md` by default.
- `melodex-provider doctor` checks README, licence and source-policy documentation before runtime smoke tests.
- Developer onboarding now has a 5-minute fast path plus a separate status/stability/trust reference.
- Documentation is being checked in CI for broken internal links and stale navigation.
- SDK/security documentation now distinguishes current enforcement from design targets.

## [0.4.0] - 2026-09-28

### Added

- `melodex-registry validate`, `summary` and `verify-packages`.
- Canonical plugin-registry schema.
- Hash/size metadata for installable registry packages.
- Installable Radio Browser, LibriVox, MusicBrainz and Wikimedia reference packages.
- Registry publishing/governance documentation.

## [0.3.0] - 2026-09-28

### Added

- Experimental v0.1 capability-extension contracts for identity, metadata, artwork and lyrics.
- `melodex-extension init`, `validate`, `doctor` and `pack`.
- `.mdxplugin` package tooling.
- MusicBrainz and Wikimedia enrichment examples with fixtures/provenance.

## [0.2.0] - 2026-09-27

### Added

- Provider `doctor` runtime smoke checks.
- Web/session helper support for authorized sources with cookies, redirects, retries and structured responses.
- Vendored pure-Python dependency support.
- Expanded provider examples/tests and messy-source documentation.

## [0.1.0] - 2026-09-26

### Added

- Initial source-neutral Melodex Provider Protocol preview.
- OpenAPI HTTP mapping for provider health, metadata, search, catalog lookup and playback resolution.
- JSON-RPC-over-stdio local-process mapping.
- Provider manifest and normalized catalog schemas.
- Python reference models.
- `melodex-provider init`, `validate` and `pack`.
- Fictional demo provider.
- Cross-platform architecture/design documentation.
- Initial security/trust and clean-release documentation.
