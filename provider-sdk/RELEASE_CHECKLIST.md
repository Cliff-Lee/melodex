# Provider SDK release checklist

Before publishing a Provider SDK / registry release:

- [ ] Run `python scripts/release_check.py`.
- [ ] Run `pytest` and `ruff check .`.
- [ ] Confirm there are no passwords, cookies, tokens, private keys, or signed playback URLs.
- [ ] Confirm example domains are reserved/test domains or clearly authorized services.
- [ ] Confirm the repository contains no DRM/access-control circumvention code.
- [ ] Confirm provider-specific integrations are not silently bundled into the generic SDK.
- [ ] Confirm third-party code, if added later, has compatible licensing and attribution.
- [ ] Confirm the chosen repository license is intentional. This package currently uses MIT.
- [ ] Confirm screenshots/assets, if added, are owned or licensed for redistribution.
- [ ] Check that `.github/workflows/ci.yml` passes on Linux, macOS, and Windows.
- [ ] Enable GitHub Private vulnerability reporting if desired.
- [ ] Confirm `CHANGELOG.md`, SDK version strings, registry schema/docs and compatibility notes are current.
- [ ] Run `melodex-registry validate registry/registry.json`.
- [ ] Run `melodex-registry verify-packages registry/registry.json --packages registry/packages`.
- [ ] Run `melodex-registry validate-reviews registry/registry.json --reviews registry/reviews` and confirm each current version/hash has a matching latest review event.
- [ ] Run `python ../scripts/docs_check.py` and `python ../scripts/ecosystem_check.py` from the repository checkout.
- [ ] Tag the release only after CI is green.
