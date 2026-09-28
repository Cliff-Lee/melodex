# Releasing Melodex

Melodex uses separate version namespaces for the application, Provider SDK, local REST API, MPP and capability contracts.

This page is about the **Melodex application release version**.

## Source-development version

The canonical app/source development version is stored in:

```text
VERSION
```

CI requires it to match:

- `desktop/melodex/__init__.py`;
- `desktop/pyproject.toml`;
- `desktop/installer.iss`;
- Android `versionName`.

During normal development it may look like:

```text
0.3.0.dev0
```

## Before creating a release

Suppose the next release is `v0.3.0`.

1. Change `VERSION` from `0.3.0.dev0` to `0.3.0`.
2. Make the same stable version change in the synchronized app metadata files listed above.
3. Increase Android `versionCode` if required.
4. Update [Release status](RELEASE_STATUS.md).
5. Update release notes/changelogs that describe user-visible changes.
6. Run:

```bash
python scripts/docs_check.py
python scripts/ecosystem_check.py
python scripts/api_docs_check.py
python scripts/release_check.py

PYTHONPATH=desktop pytest -q desktop/tests
cd provider-sdk
pytest -q tests
```

7. Commit the release-preparation changes.
8. Tag **that exact commit**:

```bash
git tag v0.3.0
git push origin main --tags
```

## Tag/version guardrail

Release workflows run:

```bash
python scripts/release_version_check.py v0.3.0
```

The build refuses a release tag when:

- `VERSION` is still a development version;
- the tag does not exactly match `v<VERSION>`.

The normal ecosystem consistency check separately verifies the desktop/Android/installer version declarations.

## GitHub release artifacts

Tag workflows build/upload, where supported:

- macOS ARM64 DMG;
- macOS Intel DMG;
- Windows installer;
- Windows portable ZIP;
- Android APK;
- Android AAB;
- source ZIP.

## Signing / notarization

The public workflows do **not** currently guarantee that every release artifact is signed/notarized with a trusted platform publisher identity.

Do not describe an unsigned preview build as signed.

The platform installation guides explain the warnings users may see.

## After a release

After `v0.3.0` is published, normally bump `main` to the next development version, for example:

```text
0.4.0.dev0
```

Update [Release status](RELEASE_STATUS.md) so readers can tell what is in the packaged release versus newer work on `main`.

## Historical note

The v0.2.0 GitHub release was tagged correctly, but its desktop/Android internal package metadata still reported 0.1.0. The current version guardrails were added specifically to prevent that class of mismatch recurring.
