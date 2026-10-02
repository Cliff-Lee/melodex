# WinGet packaging

Melodex keeps a copy of its Windows Package Manager manifests here so release
metadata can be reviewed and updated alongside the app.

## Current package

- Package ID: `Melodex.Melodex`
- Version: `0.7.2`
- Installer: `Melodex-Windows-x64-Setup.exe`
- Installer type: Inno Setup
- Architecture: x64
- Install scope: machine

The installer URL is version-specific and points to the immutable GitHub release
asset. Its SHA-256 is copied from the GitHub release asset metadata.

## Submit to the WinGet community repository

The Microsoft community repository expects this directory layout:

```text
manifests/m/Melodex/Melodex/0.7.2/
  Melodex.Melodex.installer.yaml
  Melodex.Melodex.locale.en-US.yaml
  Melodex.Melodex.yaml
```

Copy the three manifest files from `packaging/winget/Melodex.Melodex/0.7.2/`
into that path in a fork of `microsoft/winget-pkgs`, then open a pull request
containing only this package version.

On Windows, validate before submission with:

```powershell
winget settings --enable LocalManifestFiles
winget validate --manifest .\manifests\m\Melodex\Melodex\0.7.2
winget install --manifest .\manifests\m\Melodex\Melodex\0.7.2
```

The upstream WinGet validation pipeline will also validate the manifests and
installer when the pull request is opened.

## Updating a future release

For a new Melodex version:

1. copy the previous version's three manifest files;
2. update `PackageVersion`;
3. update the installer URL;
4. replace `InstallerSha256` with the new release asset SHA-256;
5. update `ReleaseDate` and `ReleaseNotesUrl`;
6. submit only the new package-version directory upstream.
