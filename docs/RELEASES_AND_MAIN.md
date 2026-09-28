# Releases, `main`, and Version Numbers

Melodex is developed in public. That means there are two legitimate views of the project:

| View | What it represents |
| --- | --- |
| **GitHub Release** | A tagged snapshot with downloadable binaries |
| **`main` branch** | The current development state, which may contain features added after the latest release |

## Which documentation am I reading?

Documentation in the repository's `main` branch describes **current `main` unless a page explicitly says otherwise**.

Therefore a feature documented on `main` may not yet exist in the most recent downloadable release.

If you installed a release binary and a documented feature is missing:

1. check the release version;
2. check the release notes/changelog;
3. check [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md);
4. if necessary, build current `main` from source or wait for the next tagged release.

This is normal for an actively developed public project, but the distinction should always be visible rather than implied.

## Version policy

Melodex keeps separate versions for separate contracts:

- **Melodex app version** — desktop/Android release line;
- **Provider SDK version** — Python SDK/tooling package;
- **MPP protocol version** — provider wire contract;
- **capability contract version** — enrichment contract;
- **plugin version** — extension author's package.

Do not assume matching-looking numbers refer to the same compatibility promise.

### App development versions

Between tagged releases, `main` uses a development version such as:

```text
0.3.0.dev0
```

Before tagging `v0.3.0`, the application version must be changed to:

```text
0.3.0
```

CI checks that the following agree:

```text
VERSION
desktop/melodex/__init__.py
desktop/pyproject.toml
Android versionName
```

Tagged release builds additionally check that the Git tag matches the application version.

## Why this matters

A public project should not make a user infer whether:

- a screenshot is from unreleased `main`;
- a tutorial requires a newer build;
- “1.0” means app version, SDK version or protocol version;
- a feature is implemented but not yet in a release.

When in doubt, the project should state the distinction explicitly.

## Release artefacts

Normal tagged releases currently build:

- macOS Apple Silicon DMG;
- macOS Intel DMG while a suitable runner remains available;
- Windows installer;
- Windows portable ZIP;
- Android APK;
- Android AAB;
- source archive.

Platform signing/notarisation may still vary by preview release. Installation guides call this out rather than assuming every build is signed.
