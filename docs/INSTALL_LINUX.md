# Install Melodex on Linux

The first Linux release targets 64-bit x86 desktop systems. The `.deb` is the direct install for Ubuntu and Debian. The AppImage is a single-file option for other glibc-based desktop distributions.

## Ubuntu and Debian (`.deb`)

Download `Melodex-linux-x86_64.deb` from the [latest GitHub release](https://github.com/Cliff-Lee/melodex/releases/latest), then install it from the download folder:

```bash
sudo apt install ./Melodex-linux-x86_64.deb
```

The package adds Melodex to the application menu and installs the `melodex` command. APT installs the desktop libraries Melodex needs. The package is tested on Ubuntu 22.04, 24.04 and 26.04, and Debian 12, on x86_64.

To update, install the newer `.deb` the same way. To remove the application:

```bash
sudo apt remove melodex
```

Your music files and Melodex listening data in your home directory are kept when the package is removed.

## AppImage

Download `Melodex-linux-x86_64.AppImage` from the [latest GitHub release](https://github.com/Cliff-Lee/melodex/releases/latest), then make it executable and launch it:

```bash
chmod +x Melodex-linux-x86_64.AppImage
./Melodex-linux-x86_64.AppImage
```

If the desktop does not have AppImage FUSE support, launch it in extract-and-run mode:

```bash
./Melodex-linux-x86_64.AppImage --appimage-extract-and-run
```

The AppImage includes Melodex, Python, Qt and Qt Multimedia. It uses your desktop's graphics, display and audio libraries, and requires glibc 2.35 or newer. Ubuntu 22.04, 24.04 and 26.04, plus Debian 12, are smoke-tested. Fedora, Arch, openSUSE and their derivatives are not yet verified; requirements vary with the desktop environment and installed audio/display stack.

To update, download the latest AppImage and replace the old file. To remove it, delete the file. User data is stored outside the AppImage under `~/.local/share/melodex` (or your configured `XDG_DATA_HOME`).

## Optional audio analysis

FFmpeg is optional. Playback and regular Melodex use do not require it. Installing FFmpeg enables additional local audio analysis used by some Flow features:

```bash
sudo apt install ffmpeg
```

## Current package limits

- Linux packages currently target x86_64/amd64.
- Ubuntu/Debian `.deb` installs and AppImage launch have CI smoke checks on Ubuntu 22.04, Ubuntu 24.04, Ubuntu 26.04 and Debian 12.
- The first release is distributed through GitHub Releases; Snap, Flatpak/Flathub, AUR and distro archive packages are not included yet.
- For installation problems, see [Troubleshooting](TROUBLESHOOTING.md) or [report an issue](https://github.com/Cliff-Lee/melodex/issues).
