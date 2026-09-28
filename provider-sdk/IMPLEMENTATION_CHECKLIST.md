# Implementation Checklist

This checklist reflects the **current public repository**, not an original design plan.

For the authoritative maturity/security summary, see [Status, stability and trust](../docs/developers/00_STATUS_AND_STABILITY.md).

## Provider-neutral desktop core

- [x] Normalized provider models.
- [x] `ProviderManager` in Melodex Core.
- [x] Local Files through the provider abstraction.
- [x] Generic playback gateway/resource handling.
- [x] Source-neutral player/provider resolution path.
- [x] Universal multi-source resolver.
- [x] Provider source status/priority UI.
- [ ] Full provider health/diagnostic UI.

## Desktop provider SDK/runtime

- [x] Manifest schema and validation CLI.
- [x] `.mdxprovider` package format and pack command.
- [x] Desktop `.mdxprovider` installer.
- [x] Out-of-process JSON-RPC provider transport.
- [x] Package traversal/symlink hardening.
- [x] `init / validate / doctor / pack`.
- [x] Source-policy scaffold/documentation.
- [x] Offline fixture/unit testing patterns.
- [ ] Full protocol conformance runner beyond smoke tests.
- [ ] OS-level permission sandbox.
- [ ] Rich provider logs/health dashboard.

## Capability-extension ecosystem

- [x] Experimental v0.1 identity contract.
- [x] Experimental v0.1 metadata contract.
- [x] Experimental v0.1 artwork contract.
- [x] Experimental v0.1 lyrics contract.
- [x] Capability Broker in desktop Core.
- [x] `.mdxplugin` installer/runtime.
- [x] `melodex-extension init / validate / doctor / pack`.
- [x] Progressive enrichment and provenance model.
- [x] Reference MusicBrainz/Wikimedia examples.
- [ ] Stable compatibility commitment for enrichment contracts.

## Registry / community distribution

- [x] Canonical registry schema.
- [x] Desktop Plugin Directory.
- [x] HTTPS package download.
- [x] SHA-256 + byte-size verification.
- [x] Compatibility metadata.
- [x] Registry status vocabulary/governance.
- [x] `melodex-registry validate / summary / verify-packages`.
- [x] Installable legal/open reference packages.
- [x] Installation provenance/update-awareness work.
- [ ] Publisher cryptographic signatures.
- [ ] Verified-publisher keyring/revocation.
- [ ] Automatic updates (intentionally not enabled today).

## Bridge / mobile

- [x] Authenticated desktop local/LAN control bridge.
- [x] Android Bridge client path.
- [ ] QR/fingerprint pairing workflow.
- [ ] Per-device token revocation UI.
- [ ] Standalone/Docker Bridge packaging.
- [ ] iOS application.

## Public-release hygiene

- [x] Source-neutral public Core.
- [x] Secret/private-source release check.
- [x] Rights/source-policy documentation.
- [x] Registry package integrity tests.
- [x] Public contribution/security templates.
- [ ] Signed/notarized coverage for every future binary/release platform.
