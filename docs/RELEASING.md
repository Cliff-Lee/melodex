# Releasing Melodex

Melodex develops on `main` using a development app version such as:

```text
0.3.0.dev0
```

A tagged release must use the exact non-development version represented by the tag.

See [Releases, `main`, and version numbers](RELEASES_AND_MAIN.md).

## 1. Choose the release version

For a release such as `v0.3.0`, change the application version from:

```text
0.3.0.dev0
```

to:

```text
0.3.0
```

Keep these synchronized:

```text
VERSION
desktop/melodex/__init__.py
desktop/pyproject.toml
android/app/build.gradle.kts versionName
```

Increment Android `versionCode` when publishing a new Android build.

## 2. Run the full checks

From the repository root:

```bash
python scripts/docs_check.py
python scripts/ecosystem_check.py
python scripts/version_check.py
python scripts/release_check.py

PYTHONPATH=desktop pytest -q desktop/tests
pytest -q provider-sdk/tests
```

For the planned tag, also test:

```bash
python scripts/version_check.py --release-tag v0.3.0
```

Replace the example version with the actual release tag.

## 3. Update release-facing documentation

Before tagging, review:

- README / installation guidance;
- [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md);
- Provider SDK changelog when SDK behavior changed;
- API changelog when public API/tool behavior changed;
- release notes for user-visible changes;
- third-party notices/licensing when dependencies or reference services changed.

Do not promise that unreleased `main` features existed in an older binary release.

## 4. Commit and merge the release version

The release commit should be on `main` before tagging.

## 5. Tag

Example:

```bash
git tag v0.3.0
git push origin main
git push origin v0.3.0
```

The GitHub workflows run the version checks again. A tag whose version does not match the application version should fail.

## 6. Expected release artifacts

Current tagged workflows can attach:

- `Melodex-macOS-arm64.dmg`;
- `Melodex-macOS-intel.dmg` while a suitable GitHub runner remains available;
- `Melodex-Windows-x64-Setup.exe`;
- `Melodex-Windows-portable.zip`;
- `Melodex-Android.apk`;
- `Melodex-Android.aab`;
- source ZIP.

Preview artifacts may be unsigned/unnotarized unless the required platform signing credentials are configured. Installation documentation must continue to state that accurately.

## 7. After the release

Move `main` to the next development version, for example:

```text
0.4.0.dev0
```

and synchronize the same version files again.

That makes it obvious that subsequent `main` documentation/code is development after the tagged release.
