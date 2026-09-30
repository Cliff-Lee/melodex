# Melodex <version>

**Don't shuffle. Flow.**

> Release tag, `VERSION`, desktop package metadata, Windows installer metadata and Android `versionName` must all match this release version.

## Downloads

| Platform | File |
| --- | --- |
| macOS — Apple Silicon | `Melodex-macOS-arm64.dmg` |
| macOS — Intel | `Melodex-macOS-intel.dmg` |
| Windows installer | `Melodex-Windows-x64-Setup.exe` |
| Windows portable | `Melodex-Windows-portable.zip` |
| Android | `Melodex-Android.apk` and `Melodex-Android.aab` |
| Ubuntu/Debian — x86_64 | `Melodex-linux-x86_64.deb` |
| Linux AppImage — x86_64 | `Melodex-linux-x86_64.AppImage` |
| Source | `Melodex-v<version>-source.zip` |

## What's new

- 
- 
- 

## Highlights

- Flow sequencing
- Local taste memory and rediscovery
- Familiar ↔ Surprising session control
- Moments
- Optional LLM integration
- Paste playlists from ChatGPT and other AI chats without connecting an AI
- Six optional desktop music sources bundled for first launch; users can remove them and restore them later
- Living Canvas visualizer modes and local visual memory
- Source-neutral provider architecture

## Verification

- [ ] `python scripts/version_check.py --release-tag v<version>` passed
- [ ] desktop tests passed
- [ ] Provider SDK tests passed
- [ ] documentation/ecosystem/release checks passed
- [ ] release asset filenames match the installation documentation

## Notes

Melodex is still early software. Please report reproducible bugs through GitHub Issues.

For installation help, see the [documentation](https://github.com/Cliff-Lee/melodex/blob/main/docs/START_HERE.md).

## Responsible use

Melodex is designed for music that the user is authorised to access. Public releases do not ship private credentials, copyrighted media, source-specific bypass logic or access-control circumvention.
