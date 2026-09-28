# Install Melodex

You do **not** need Python, Git, Android Studio, or any developer tools if you install a release build.

> **Release note:** these installation filenames are produced by the tagged release workflows. Repository documentation follows `main`, which can contain newer features than the latest downloadable release. See [Releases, main, and version numbers](RELEASES_AND_MAIN.md).

Download the latest release from:

**https://github.com/Cliff-Lee/melodex/releases/latest**

Then choose your platform:

| Platform | Download this | Guide |
| --- | --- | --- |
| Apple Silicon Mac (M1/M2/M3/M4…) | `Melodex-macOS-arm64.dmg` | [macOS](INSTALL_MACOS.md) |
| Intel Mac | `Melodex-macOS-intel.dmg` | [macOS](INSTALL_MACOS.md) |
| Windows 10/11 | `Melodex-Windows-x64-Setup.exe` | [Windows](INSTALL_WINDOWS.md) |
| Windows portable | `Melodex-Windows-portable.zip` | [Windows](INSTALL_WINDOWS.md) |
| Android phone/tablet | `Melodex-Android.apk` | [Android](INSTALL_ANDROID.md) |

> **Android works differently.** The Android app is currently a client for a Melodex Provider Bridge running on a Mac, Windows PC, NAS, or home server. For the easiest Android setup, install Melodex on the computer first, add your music there, then pair the phone with that computer.

Do **not** download these unless you know you need them:

- `.aab` — intended for app-store publishing, not normal Android installation;
- `source.zip` — source code for developers;
- checksums or build artifacts — useful for verification/development, not required for a normal install.

## After installation

For the quickest first experience:

1. Open Melodex.
2. Choose **Sources**.
3. Select **Add local folder…** and choose a folder containing music you are allowed to play.
4. Return to **Home** or **Play for me**.
5. Start a track or press **Play for me**.
6. Use **Flow queue** when you want Melodex to resequence the upcoming tracks into a more coherent journey.

Everything involving Jamendo, third-party providers, or an LLM is optional.

## Need help?

- [Start Here](START_HERE.md)
- [User Guide](USER_GUIDE.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [FAQ](FAQ.md)
