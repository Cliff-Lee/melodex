# Releases, `main`, and Version Numbers

Melodex is developed in public. The repository therefore has two legitimate views of the project:

| View | Meaning |
| --- | --- |
| **GitHub Release** | A tagged snapshot with downloadable binaries |
| **`main` branch** | Current development, which may be ahead of the latest release |

## Which documentation am I reading?

Documentation on the repository's `main` branch describes **current `main` unless a page explicitly says otherwise**.

That means a feature documented on `main` may not yet exist in the latest downloadable release.

If an installed release does not contain something described in current documentation:

1. check the release/tag you installed;
2. read that release's notes;
3. compare it with current `main`;
4. build `main` from source only if you intentionally want development code.

This distinction is normal for an actively developed project, but it should be stated rather than left for users to infer.

The current release target is **v0.7.6**, combining guarded desktop bundle slimming with provider/playback reliability fixes: search-source deduplication, LibriVox and Internet Archive regional CDN redirects, Wikimedia playback identity, and gateway-level live provider verification. During its release, the stable application version is **0.7.6**; after publication, the next development cycle should use **0.7.7.dev0**.

## App version policy

The canonical Melodex **application** version lives in:

```text
VERSION
```

The same value must appear in:

```text
desktop/melodex/__init__.py
desktop/pyproject.toml
desktop/installer.iss
Android versionName
```

Android also has a numeric `versionCode`, derived as:

```text
major × 10000 + minor × 100 + patch
```

Examples:

```text
0.3.0 → 300
0.3.1 → 301
0.4.0 → 400
0.5.0 → 500
1.0.0 → 10000
```

CI checks these values on every pull request/main build.

## Development versions

Between tagged releases, `main` uses a development version such as:

```text
0.7.3.dev0
```

A release tag may not be built from a `.devN` application version.

Before any release tag, set every app-version surface to the exact stable version being released. For example, prepare a future `v0.7.3` release with:

```text
0.7.3
```

across all app-version surfaces.

The repository provides:

```bash
python scripts/set_version.py 0.7.3
python scripts/version_check.py
```

## Tag truthfulness

On a tagged build:

```text
Git tag
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

The release workflows reject a tag/version mismatch before packaging.

## Historical v0.2.0 metadata issue

The published **v0.2.0** release was genuinely tagged and released as v0.2.0, but the source at that tag still contained **0.1.0** in the internal application-version fields listed above.

That was a release-process bug, not a separate v0.1.0 binary release.

For historical v0.2.0 downloads:

- the **GitHub tag/release name v0.2.0** identifies the release;
- some application/package metadata may still report **0.1.0**;
- this mismatch is known and documented rather than hidden.

The version-consistency tooling introduced after v0.2.0 is intended to prevent a recurrence.

## SDK/protocol/plugin versions are separate

Do not confuse the application version with:

- Provider SDK version;
- MPP protocol version;
- capability-contract version;
- individual provider/plugin versions.

For example, an SDK version of `0.6.0` does not imply the Melodex desktop app is version `0.6.0`.

See [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md) for the broader compatibility picture.

## Release artefacts

Tagged release workflows currently produce the standard assets documented in [Install Melodex](INSTALL.md), including:

- macOS Apple Silicon DMG;
- macOS Intel DMG while a compatible GitHub runner is available;
- Windows installer;
- Windows portable ZIP;
- Android APK;
- Android AAB;
- Ubuntu/Debian `.deb` (x86_64);
- Linux AppImage (x86_64);
- source ZIP.

Signing/notarisation can vary between preview releases. Platform installation guides should state the actual signing situation rather than assume every artefact is signed.
