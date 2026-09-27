# Releasing Melodex

## Release checklist

1. Update `VERSION` and desktop package/installer versions.
2. Run `python scripts/release_check.py`.
3. Run desktop tests.
4. Run Provider SDK tests.
5. Build/test the packaged macOS app, including an external Python `.mdxprovider`.
6. Confirm LLM/control redaction tests pass.
7. Trigger release-candidate builds from `release/v0.2.0`.
8. Test or inspect platform artifacts.
9. Update documentation/manuals and release notes.
10. Merge the release branch when ready.
11. Tag the release:

```bash
git tag v0.2.0
git push origin main --tags
```

## Expected v0.2 artifacts

- `Melodex-macOS-arm64.dmg`
- `Melodex-macOS-intel.dmg`
- `Melodex-Windows-x64-Setup.exe`
- `Melodex-Windows-portable.zip`
- `Melodex-Linux-x86_64.AppImage`
- `Melodex-Android.apk`
- Android AAB
- source ZIP
- User Manual PDF
- Power User Manual PDF

GitHub Actions builds native artifacts on native runners. Unsigned preview artifacts may trigger OS warnings.
