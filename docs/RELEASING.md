# Releasing Melodex

This is the current application-release process.

For the distinction between app, SDK, protocol and plugin versions, see [Releases, `main`, and version numbers](RELEASES_AND_MAIN.md).

## 1. Choose the release version

While development is in progress, `main` should normally use a development version such as:

```text
0.6.1.dev0
```

Keep the working release summary in `docs/releases/next.md`. Before release, review it against the tested build, move it to `docs/releases/v<version>.md`, and verify the listed downloads against the artifacts CI produced. The release workflow uses that versioned file as the GitHub Release description. The v0.6.0 release notes are at [`docs/releases/v0.6.0.md`](releases/v0.6.0.md).

When the next release is ready, choose its stable version and update every application-version surface with one command. For example:

```bash
python scripts/set_version.py 0.7.0
```

That updates:

```text
VERSION
desktop/melodex/__init__.py
desktop/pyproject.toml
desktop/installer.iss
Android versionName
Android versionCode
```

## 2. Verify version consistency

```bash
python scripts/version_check.py
```

For a release tag, the same check is:

```bash
python scripts/version_check.py --release-tag v0.7.0
```

A release check fails if:

- any app-version surface disagrees with `VERSION`;
- Android `versionCode` does not match the deterministic mapping;
- a tag does not match `VERSION`;
- a `.devN` version is used for a release tag.

## 3. Run repository checks

At minimum:

```bash
python scripts/docs_check.py
python scripts/navigation_check.py
python scripts/terminology_check.py
python scripts/ecosystem_check.py
python scripts/version_check.py
python scripts/release_check.py
```

Desktop tests:

```bash
PYTHONPATH=desktop pytest -q desktop/tests
```

Provider SDK tests:

```bash
python -m pip install -e provider-sdk
pytest -q provider-sdk/tests
```

CI runs these checks again.

## 4. Commit the release version

Example:

```bash
git add .
git commit -m "release: v0.6.0"
git push origin main
```

When a strict release version such as `0.3.0` reaches `main`, the **Release** workflow:

1. runs the release checks and test suites again;
2. verifies the release tag name against all application-version surfaces;
3. creates or verifies the exact `v0.6.0` tag at that commit;
4. creates the GitHub Release and uploads the source archive;
5. dispatches desktop, Android and Linux workflows against that exact commit;
6. attaches their assets to the same GitHub Release after package smoke checks pass.

Ordinary development versions such as `0.6.1.dev0` do **not** create a release.

A manually pushed `v*` tag remains a fallback path, and tag-triggered workflows still validate tag/version agreement before packaging.

Pull request and development-branch Linux builds may package a `.devN` version for installation smoke tests. The `.deb` records that test build as `X.Y.Z~devN`, which sorts below the matching stable release. These packages are CI artifacts only; release-tag builds require the exact strict `X.Y.Z` version and only those tagged builds are attached to a GitHub Release.

## 5. Expected release assets

The current workflows produce:

- `Melodex-macOS-arm64.dmg`;
- `Melodex-macOS-intel.dmg` while a compatible GitHub runner remains available;
- `Melodex-Windows-x64-Setup.exe`;
- `Melodex-Windows-portable.zip`;
- `Melodex-Android.apk`;
- `Melodex-Android.aab`;
- `Melodex-linux-x86_64.deb`;
- `Melodex-linux-x86_64.AppImage`;
- `Melodex-vX.Y.Z-source.zip`.

Code signing/notarisation credentials are optional repository secrets. A preview release may therefore contain unsigned artifacts; platform installation docs must describe the actual signing situation.

## 6. Return `main` to development mode

After the release, choose the next development target.

For example:

```bash
python scripts/set_version.py 0.7.1.dev0

python scripts/version_check.py
git add .
git commit -m "chore: start next development cycle"
git push origin main
```

## Historical note — v0.2.0

The v0.2.0 GitHub release was tagged/published as v0.2.0, but its source still embedded 0.1.0 in several application-version fields.

That historical mismatch is documented in [Releases, `main`, and version numbers](RELEASES_AND_MAIN.md).

The automated version checks above were introduced specifically to prevent the same class of error from recurring.
