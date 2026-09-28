# Releasing Melodex

This is the current application-release process.

For the distinction between app, SDK, protocol and plugin versions, see [Releases, `main`, and version numbers](RELEASES_AND_MAIN.md).

## 1. Choose the release version

While development is in progress, `main` should normally use a development version such as:

```text
0.3.0.dev0
```

When ready to release `0.3.0`, update every application-version surface with one command:

```bash
python scripts/set_version.py 0.3.0
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
python scripts/version_check.py --release-tag v0.3.0
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
git commit -m "release: v0.3.0"
git push origin main
```

Wait for the `main` checks/builds to finish successfully.

## 5. Tag the exact release commit

```bash
git tag v0.3.0
git push origin v0.3.0
```

The tag-triggered workflows verify:

```text
tag
==
VERSION
==
desktop package version
==
Python app version
==
Windows installer version
==
Android versionName
```

before release packaging proceeds.

## 6. Expected release assets

The current workflows produce:

- `Melodex-macOS-arm64.dmg`;
- `Melodex-macOS-intel.dmg` while a compatible GitHub runner remains available;
- `Melodex-Windows-x64-Setup.exe`;
- `Melodex-Windows-portable.zip`;
- `Melodex-Android.apk`;
- `Melodex-Android.aab`;
- `Melodex-vX.Y.Z-source.zip`.

Code signing/notarisation credentials are optional repository secrets. A preview release may therefore contain unsigned artifacts; platform installation docs must describe the actual signing situation.

## 7. Return `main` to development mode

After the release, choose the next development target.

For example:

```bash
python scripts/set_version.py 0.3.1.dev0
# or
python scripts/set_version.py 0.4.0.dev0

python scripts/version_check.py
git add .
git commit -m "chore: start next development cycle"
git push origin main
```

## Historical note — v0.2.0

The v0.2.0 GitHub release was tagged/published as v0.2.0, but its source still embedded 0.1.0 in several application-version fields.

That historical mismatch is documented in [Releases, `main`, and version numbers](RELEASES_AND_MAIN.md).

The automated version checks above were introduced specifically to prevent the same class of error from recurring.
