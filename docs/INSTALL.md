# Install Melodex

You do **not** need Python, Git, Android Studio, or any developer tools if you install a release build.

> **Tagged releases vs `main`:** the files below are produced by the release workflows. Documentation on `main` can describe newer development features than the latest downloadable release. See [Releases, `main`, and version numbers](RELEASES_AND_MAIN.md).

Download the latest release from:

**https://github.com/Cliff-Lee/melodex/releases/latest**

Then choose your platform:

| Platform | Download this | Guide |
| --- | --- | --- |
| Apple Silicon Mac (M1/M2/M3/M4…) | `Melodex-macOS-arm64.dmg` | [macOS](INSTALL_MACOS.md) |
| Intel Mac | `Melodex-macOS-intel.dmg` | [macOS](INSTALL_MACOS.md) |
| Windows 10/11 | `Melodex-Windows-x64-Setup.exe` | [Windows](INSTALL_WINDOWS.md) |
| Windows portable | `Melodex-Windows-portable.zip` | [Windows](INSTALL_WINDOWS.md) |
| Ubuntu/Debian x86_64 | `Melodex-linux-x86_64.deb` | [Linux](INSTALL_LINUX.md) |
| Other glibc Linux desktops x86_64 | `Melodex-linux-x86_64.AppImage` | [Linux](INSTALL_LINUX.md) |
| Android phone/tablet | `Melodex-Android.apk` | [Android](INSTALL_ANDROID.md) |

> **Android has two listening paths.** Choose **On this phone** to play audio stored locally without a computer. Choose **Connect a Melodex** to reach sources exposed by a desktop, NAS, or home server through Provider Bridge. This release includes the first local-playback preview; see the [Android guide](INSTALL_ANDROID.md) for its limits.

Do **not** download these unless you know you need them:

- `.aab` — intended for app-store publishing, not normal Android installation;
- `source.zip` — source code for developers;
- checksums or build artifacts — useful for verification/development, not required for a normal install.

## After installation

For the quickest first experience:

1. Open Melodex.
2. Open **My Music**.
3. Choose **+ Add music** and select a folder containing music you are allowed to play.
4. Browse the visual Albums view or return to **Home**.
5. Choose **Play something**.

That is enough to start.

Use **Find missing artwork** only when you explicitly want Melodex to look online for missing covers. Artist photos and metadata enrichment are also optional.

Provider configuration, Power tools, third-party plugins and LLM control are optional.

## Need help?

- [Start Here](START_HERE.md)
- [User Guide](USER_GUIDE.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [FAQ](FAQ.md)
