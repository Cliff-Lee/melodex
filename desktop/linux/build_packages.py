from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image


DESKTOP = Path(__file__).resolve().parents[1]
REPO = DESKTOP.parent
LINUX = DESKTOP / "linux"
APP_ID = "io.github.cliff_lee.Melodex"

DEBIAN_DEPENDS = [
    "libc6 (>= 2.35)",
    "libgcc-s1",
    "libstdc++6",
    "libglib2.0-0 | libglib2.0-0t64",
    "libdbus-1-3",
    "libx11-6",
    "libxext6",
    "libxrender1",
    "libxcb1",
    "libxcb-cursor0",
    "libxcb-icccm4",
    "libxcb-image0",
    "libxcb-keysyms1",
    "libxcb-randr0",
    "libxcb-render-util0",
    "libxcb-shape0",
    "libxcb-shm0",
    "libxcb-sync1",
    "libxcb-xfixes0",
    "libxcb-xinerama0",
    "libxcb-xinput0",
    "libxcb-xkb1",
    "libxcb-util1",
    "libxkbcommon0",
    "libxkbcommon-x11-0",
    "libwayland-client0",
    "libwayland-cursor0",
    "libwayland-egl1",
    "libgl1",
    "libegl1",
    "libfontconfig1",
    "libfreetype6",
    "libpulse0",
    "libasound2 | libasound2t64",
]

# The AppImage carries the XCB/XKB client libraries Qt needs when they are not
# part of a target desktop's minimal installation. Graphics drivers and core
# X11/Wayland/audio services remain host-provided.
BUNDLE_LIBRARY_PATTERN = re.compile(r"^(libxcb[^/]*|libxkbcommon[^/]*)\.so(?:\.|$)")
LDD_DEPENDENCY = re.compile(r"^\s*(\S+)\s+=>\s+(\S+)\s+\(0x[0-9a-fA-F]+\)")


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True, env=env)


def require_file(path: Path, description: str) -> None:
    if not path.is_file():
        raise SystemExit(f"{description} not found: {path}")


def copy_desktop_resources(target: Path, icon_source: Path) -> None:
    applications = target / "usr/share/applications"
    icons = target / f"usr/share/icons/hicolor/512x512/apps"
    metainfo = target / "usr/share/metainfo"
    applications.mkdir(parents=True, exist_ok=True)
    icons.mkdir(parents=True, exist_ok=True)
    metainfo.mkdir(parents=True, exist_ok=True)

    shutil.copy2(LINUX / f"{APP_ID}.desktop", applications / f"{APP_ID}.desktop")
    shutil.copy2(LINUX / f"{APP_ID}.metainfo.xml", metainfo / f"{APP_ID}.metainfo.xml")
    write_icon(icon_source, icons / f"{APP_ID}.png")


def write_icon(source: Path, target: Path) -> None:
    with Image.open(source) as image:
        image.convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS).save(target, "PNG")


def build_deb(version: str, output_dir: Path, frozen_app: Path, icon_source: Path) -> Path:
    root = output_dir / "package-deb"
    shutil.rmtree(root, ignore_errors=True)
    (root / "DEBIAN").mkdir(parents=True)
    app_destination = root / "opt/melodex"
    app_destination.parent.mkdir(parents=True)
    shutil.copytree(frozen_app, app_destination, symlinks=True)

    executable = app_destination / "Melodex"
    require_file(executable, "PyInstaller application executable")
    launcher = root / "usr/bin/melodex"
    launcher.parent.mkdir(parents=True)
    launcher.write_text(
        "#!/bin/sh\nexec /opt/melodex/Melodex \"$@\"\n", encoding="utf-8"
    )
    launcher.chmod(0o755)
    copy_desktop_resources(root, icon_source)

    copyright_path = root / "usr/share/doc/melodex/copyright"
    copyright_path.parent.mkdir(parents=True)
    shutil.copy2(REPO / "LICENSE", copyright_path)

    control = "\n".join(
        [
            "Package: melodex",
            f"Version: {version}",
            "Section: sound",
            "Priority: optional",
            "Architecture: amd64",
            "Maintainer: Melodex contributors <cliff-lee@users.noreply.github.com>",
            "Homepage: https://github.com/Cliff-Lee/melodex",
            "Depends: " + ",\n " .join(DEBIAN_DEPENDS),
            "Suggests: ffmpeg",
            "Description: local-first music player for thoughtful listening journeys",
            " Melodex combines local playback, Flow sequencing, journeys, and a music map.",
            " Optional extensions and AI control are available without being required.",
            "",
        ]
    )
    (root / "DEBIAN/control").write_text(control, encoding="utf-8")

    output = output_dir / "Melodex-linux-x86_64.deb"
    run(["dpkg-deb", "--build", "--root-owner-group", str(root), str(output)])
    return output


def appimage_external_libraries(frozen_app: Path, appdir: Path) -> None:
    candidates = [frozen_app / "Melodex"]
    candidates.extend(frozen_app.rglob("libqxcb.so"))
    candidates.extend(frozen_app.rglob("libqwayland*.so"))
    candidates.extend(frozen_app.rglob("libQt6XcbQpa.so*"))
    destination = appdir / "usr/lib"
    destination.mkdir(parents=True, exist_ok=True)
    copied: set[str] = set()

    for binary in candidates:
        if not binary.is_file():
            continue
        result = subprocess.run(
            ["ldd", str(binary)], text=True, capture_output=True, check=False
        )
        if result.returncode != 0:
            continue
        unresolved = [line.strip() for line in result.stdout.splitlines() if "not found" in line]
        if unresolved:
            raise SystemExit(
                f"AppImage build host is missing runtime libraries needed by {binary}: "
                + "; ".join(unresolved)
            )
        for line in result.stdout.splitlines():
            match = LDD_DEPENDENCY.match(line)
            if not match:
                continue
            soname, library_path = match.groups()
            if not BUNDLE_LIBRARY_PATTERN.match(soname):
                continue
            source = Path(library_path)
            target = destination / soname
            if soname in copied or not source.is_file():
                continue
            shutil.copy2(source, target)
            copied.add(soname)

    print("Bundled AppImage XCB/XKB libraries:", ", ".join(sorted(copied)) or "none")


def build_appimage(
    version: str,
    output_dir: Path,
    frozen_app: Path,
    icon_source: Path,
    appimagetool: Path,
    runtime_file: Path,
) -> Path:
    appdir = output_dir / "Melodex.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    library_dir = appdir / "usr/lib/melodex"
    library_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(frozen_app, library_dir, symlinks=True)
    executable = library_dir / "Melodex"
    require_file(executable, "PyInstaller application executable")

    launcher = appdir / "usr/bin/melodex"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(
        '#!/bin/sh\nset -eu\n'
        'HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
        'exec "$HERE/../lib/melodex/Melodex" "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    (appdir / "AppRun").write_text((LINUX / "AppRun").read_text("utf-8"), encoding="utf-8")
    (appdir / "AppRun").chmod(0o755)
    appimage_desktop = (LINUX / f"{APP_ID}.desktop").read_text("utf-8")
    appimage_desktop = appimage_desktop.replace("Exec=melodex", "Exec=AppRun")
    appimage_desktop = appimage_desktop.replace("TryExec=melodex", "TryExec=AppRun")
    (appdir / f"{APP_ID}.desktop").write_text(appimage_desktop, encoding="utf-8")
    write_icon(icon_source, appdir / f"{APP_ID}.png")
    copy_desktop_resources(appdir, icon_source)
    (appdir / f"usr/share/applications/{APP_ID}.desktop").write_text(
        appimage_desktop, encoding="utf-8"
    )
    appimage_external_libraries(frozen_app, appdir)

    output = output_dir / "Melodex-linux-x86_64.AppImage"
    env = os.environ.copy()
    env["ARCH"] = "x86_64"
    env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    run(
        [
            str(appimagetool),
            "--runtime-file",
            str(runtime_file),
            str(appdir),
            str(output),
        ],
        env=env,
    )
    output.chmod(0o755)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Melodex Linux release packages.")
    parser.add_argument("--appimagetool", type=Path, required=True)
    parser.add_argument("--runtime-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DESKTOP / "dist")
    args = parser.parse_args()

    if not sys.platform.startswith("linux") or os.uname().machine not in {"x86_64", "amd64"}:
        raise SystemExit("Linux release packages must be built on x86_64 Linux.")
    version = (REPO / "VERSION").read_text("utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"release packages require a strict application version, got {version!r}")

    frozen_app = DESKTOP / "dist/Melodex"
    icon_source = REPO / "assets/icon.png"
    require_file(frozen_app / "Melodex", "PyInstaller output")
    require_file(icon_source, "application icon")
    require_file(args.appimagetool, "appimagetool")
    require_file(args.runtime_file, "AppImage type 2 runtime")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    deb = build_deb(version, args.output_dir, frozen_app, icon_source)
    appimage = build_appimage(
        version,
        args.output_dir,
        frozen_app,
        icon_source,
        args.appimagetool,
        args.runtime_file,
    )
    print(f"Built Linux packages for Melodex {version}:\n  {deb}\n  {appimage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
