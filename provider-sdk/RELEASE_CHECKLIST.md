# Public release checklist

Before making the repository public:

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
- [ ] Tag the first preview release only after the repository URL and documentation are final.
