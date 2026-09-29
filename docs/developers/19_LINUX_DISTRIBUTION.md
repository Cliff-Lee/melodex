# Linux Distribution Design

## Goal

Ship Melodex as a normal desktop application on Ubuntu and make a practical build available to users of other mainstream Linux distributions. The first Linux release targets x86_64 and GitHub Releases; it does not claim admission to Ubuntu, Debian, Snap or Flathub archives.

## Package choices

| Artifact | Initial audience | Install and update path |
| --- | --- | --- |
| `Melodex-linux-x86_64.deb` | Ubuntu 22.04 and newer; Debian 12 and newer, x86_64 | Install the downloaded package with APT. Download a newer release to update. |
| `Melodex-linux-x86_64.AppImage` | Other glibc-based desktop distributions, x86_64 | Mark executable and launch. Remove the file to uninstall. |

Ubuntu 22.04 is the build baseline for both packages. Building the AppImage on an older target base helps preserve compatibility with newer glibc-based systems; AppImage guidance also requires including non-base dependencies and testing the intended target systems. The published compatibility statement must be checked against the actual bundled binaries and the CI smoke matrix before release.

The AppImage bundles Melodex, Python, Qt and its multimedia backend through the existing PyInstaller build. It relies on the host for core graphics, display and audio integration libraries; the `.deb` declares those runtime dependencies so APT can install them. Do not bundle glibc, graphics drivers, or host audio daemons into either package.

## Desktop integration and files

- Use the stable application ID `io.github.cliff_lee.Melodex` in the desktop entry and AppStream metadata.
- The `.deb` installs the frozen application under `/opt/melodex`, a `melodex` command in `/usr/bin`, the desktop entry and icon, and a copy of the project licence.
- AppImage resources must resolve relative to the mounted AppDir. The application stores settings and library data in the normal XDG user data directory, outside the read-only AppImage.
- FFmpeg remains optional. It may be recommended for deeper local Flow analysis, but Melodex playback and metadata-based journeys must not depend on it.
- Removing the `.deb` removes application files but leaves the user's library and listening data in their home directory. Removing the AppImage removes only that file.

## Build and verification

The release workflow builds both formats on Ubuntu 22.04 from the exact release commit. It pins and verifies the AppImage tooling and runtime hashes. CI must:

1. inspect `.deb` metadata and contents;
2. exercise the frozen child-worker path;
3. install the `.deb` and launch the packaged GUI offscreen;
4. launch the AppImage payload offscreen;
5. test Ubuntu 22.04, 24.04 and 26.04, and Debian 12 for the `.deb` dependency set;
6. inspect required GLIBC symbol versions before documenting a wider AppImage target.

Package publishing remains inside GitHub Releases. A future stage may add Flatpak/Flathub, Snap, or community packaging once the application ID and store ownership are checked and their separate review and maintenance responsibilities are accepted.

## Compatibility boundary

Initial support is x86_64 only. The AppImage build checks that its ELF files require no symbol newer than GLIBC 2.35. Ubuntu 22.04/24.04/26.04 and Debian 12 are the first CI-tested targets. Fedora, Arch, openSUSE and derivative distributions can try the AppImage, but documentation must call them unverified until they are added to the smoke matrix. Do not describe AppImage as working on every Linux distribution.

The upstream AppImage guidance explains the older-build-baseline and target-system testing requirements: <https://docs.appimage.org/reference/best-practices.html>.
