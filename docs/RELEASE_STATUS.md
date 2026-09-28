# Release Status

**Last checked: 2026-09-28**

This page distinguishes the **current `main` branch** from the **latest packaged GitHub release**.

That distinction matters because Melodex is developing quickly.

## Current packaged release

The latest GitHub release is:

```text
v0.2.0
published 2026-09-27
```

Its release assets include:

- macOS ARM64 DMG;
- macOS Intel DMG;
- Windows x64 installer;
- Windows portable ZIP;
- Android APK;
- Android AAB;
- source ZIP.

The release is available from the repository's **Releases** page.

## Current development branch

`main` is ahead of v0.2.0.

The source tree is now identified as:

```text
Melodex app development version: 0.3.0.dev0
Provider SDK: 0.5.0
Local control API description: 0.2
MPP protocol identifier: 1.0 preview
Capability contracts: 0.1 experimental
```

These are **different version namespaces**. They should not be compared as though, for example, “SDK 0.5” meant “Melodex app 0.5”.

## Features on main that post-date v0.2.0

Current `main` contains ecosystem work newer than the v0.2.0 packaged builds, including:

- capability-extension runtime and `.mdxplugin` packaging;
- Plugin Directory and canonical registry;
- registry package SHA-256/size/identity verification;
- installation provenance;
- plugin update awareness;
- expanded REST/OpenAI trust metadata;
- Provider SDK 0.5 developer tooling/documentation.

Therefore:

> **Project documentation normally describes current `main` unless a page explicitly says it describes a packaged release.**

If you install the latest release and cannot find a feature documented from `main`, this version gap may be the reason.

## Historical packaging-version mismatch in v0.2.0

The v0.2.0 GitHub release was correctly tagged/published as `v0.2.0`, but its desktop and Android package metadata still reported `0.1.0`.

That was a release-engineering inconsistency, not a separate product release.

The v0.2.0 generated release notes also use the phrase **“host-permission enforcement for external providers.”** In context, that referred to Playback Gateway/redirect host validation around provider playback resources. It should **not** be read as a claim that third-party provider processes were placed in a universal OS-level network/filesystem sandbox. The current [Security](../SECURITY.md) and [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md) pages are authoritative on the present boundary.

The source tree now uses a single application development version and CI checks that the desktop/Android/installer version declarations stay synchronized.

## Signing status

Release artifacts are public preview/development builds.

The repository workflows do not currently guarantee that every published desktop artifact is code-signed/notarized with a trusted commercial/platform identity.

The installation guides therefore document the warnings users may see.

Do not treat “downloaded from the official GitHub release page” as equivalent to operating-system publisher signing.

## What should users read?

- Installation: [Install Melodex](INSTALL.md)
- Current source maturity: [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md)
- Releases/build process: [Releasing](RELEASING.md)
- Security: [Security](../SECURITY.md)

## Maintenance rule

Whenever a new packaged release is published, update this page in the same release-preparation change.

The release checklist and ecosystem consistency check should keep the version story explicit.
