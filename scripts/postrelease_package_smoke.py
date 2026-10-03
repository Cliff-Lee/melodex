from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from packaged_startup_probe import run_probe  # noqa: E402


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checksum_map(tag: str) -> dict[str, str]:
    version = tag.removeprefix("v")
    path = ROOT / "docs" / "releases" / f"v{version}-sha256.txt"
    if not path.is_file():
        raise FileNotFoundError(f"checksum manifest missing: {path}")
    result: dict[str, str] = {}
    for raw in path.read_text("utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        checksum, filename = line.split(maxsplit=1)
        result[filename.strip()] = checksum.lower()
    return result


def _download(tag: str, names: list[str], destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    command = [
        "gh",
        "release",
        "download",
        tag,
        "--repo",
        os.environ.get("GITHUB_REPOSITORY", "Cliff-Lee/melodex"),
        "--dir",
        str(destination),
    ]
    for name in names:
        command.extend(["--pattern", name])
    _run(command)
    paths = [destination / name for name in names]
    for path in paths:
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"published release asset missing after download: {path.name}")
    return paths


def _verify(paths: list[Path], expected: dict[str, str]) -> dict[str, str]:
    verified: dict[str, str] = {}
    for path in paths:
        wanted = expected.get(path.name)
        if not wanted:
            raise RuntimeError(f"no published checksum recorded for {path.name}")
        actual = _sha256(path)
        if actual != wanted:
            raise RuntimeError(
                f"checksum mismatch for {path.name}: expected {wanted}, got {actual}"
            )
        verified[path.name] = actual
    return verified


def _macos(tag: str, variant: str, work: Path, expected: dict[str, str]) -> dict[str, Any]:
    name = f"Melodex-macOS-{variant}.dmg"
    dmg = _download(tag, [name], work)[0]
    hashes = _verify([dmg], expected)

    plist_path = work / "mount.plist"
    with plist_path.open("wb") as handle:
        subprocess.run(
            ["hdiutil", "attach", "-nobrowse", "-readonly", "-plist", str(dmg)],
            check=True,
            stdout=handle,
        )
    mount_data = plistlib.loads(plist_path.read_bytes())
    mount_point = ""
    for entity in mount_data.get("system-entities", []):
        value = entity.get("mount-point")
        if value:
            mount_point = str(value)
            break
    if not mount_point:
        raise RuntimeError("published DMG mounted without a mount point")

    executable = Path(mount_point) / "Melodex.app" / "Contents" / "MacOS" / "Melodex"
    try:
        if not executable.is_file():
            raise RuntimeError(f"Melodex executable missing inside published DMG: {executable}")
        file_info = _run(["file", str(executable)]).stdout.strip()
        startup = run_probe(executable)
    finally:
        subprocess.run(["hdiutil", "detach", mount_point], check=False)

    return {
        "platform": "macos",
        "variant": variant,
        "tag": tag,
        "hashes": hashes,
        "binary": file_info,
        "startup": startup,
    }


def _windows(tag: str, work: Path, expected: dict[str, str]) -> dict[str, Any]:
    names = ["Melodex-Windows-portable.zip", "Melodex-Windows-x64-Setup.exe"]
    portable_zip, installer = _download(tag, names, work)
    hashes = _verify([portable_zip, installer], expected)

    portable_dir = work / "portable"
    with zipfile.ZipFile(portable_zip) as archive:
        archive.extractall(portable_dir)
    portable_candidates = list(portable_dir.rglob("Melodex.exe"))
    if not portable_candidates:
        raise RuntimeError("Melodex.exe missing from published portable ZIP")
    portable_startup = run_probe(portable_candidates[0])

    install_dir = work / "installed"
    install_dir.mkdir(parents=True, exist_ok=True)
    _run(
        [
            str(installer),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/SP-",
            f"/DIR={install_dir}",
        ]
    )
    installed_candidates = list(install_dir.rglob("Melodex.exe"))
    if not installed_candidates:
        raise RuntimeError("Melodex.exe missing after published installer completed")
    installed_startup = run_probe(installed_candidates[0])

    return {
        "platform": "windows",
        "tag": tag,
        "hashes": hashes,
        "portable_startup": portable_startup,
        "installed_startup": installed_startup,
    }


def _linux(tag: str, work: Path, expected: dict[str, str]) -> dict[str, Any]:
    names = ["Melodex-linux-x86_64.deb", "Melodex-linux-x86_64.AppImage"]
    deb, appimage = _download(tag, names, work)
    hashes = _verify([deb, appimage], expected)

    _run(["sudo", "apt-get", "update"])
    _run(["sudo", "apt-get", "install", "-y", str(deb)])
    appimage.chmod(appimage.stat().st_mode | 0o111)

    smoke = ROOT / "desktop" / "linux" / "smoke_launch.py"
    _run([sys.executable, str(smoke), "/usr/bin/melodex"])
    _run([sys.executable, str(smoke), str(appimage), "--appimage"])

    return {
        "platform": "linux",
        "tag": tag,
        "hashes": hashes,
        "deb_startup": run_probe(Path("/usr/bin/melodex")),
        "appimage_startup": run_probe(appimage, appimage=True),
    }


def _android(tag: str, work: Path, expected: dict[str, str]) -> dict[str, Any]:
    names = ["Melodex-Android.apk", "Melodex-Android.aab"]
    apk, aab = _download(tag, names, work)
    hashes = _verify([apk, aab], expected)

    for package in (apk, aab):
        with zipfile.ZipFile(package) as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError(f"corrupt entry in {package.name}: {bad}")

    android_home = Path(os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or "")
    aapt_candidates = sorted(android_home.glob("build-tools/*/aapt"))
    if not aapt_candidates:
        raise RuntimeError("Android aapt not found in runner SDK")
    badging = _run([str(aapt_candidates[-1]), "dump", "badging", str(apk)]).stdout
    required = (
        "package: name='com.melodex.app'",
        "versionCode='712'",
        "versionName='0.7.12'",
    )
    missing = [fragment for fragment in required if fragment not in badging]
    if missing:
        raise RuntimeError("published Android metadata mismatch: " + ", ".join(missing))

    return {
        "platform": "android-package",
        "tag": tag,
        "hashes": hashes,
        "badging": badging.splitlines()[0] if badging else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and smoke-test the actual assets attached to a Melodex release."
    )
    parser.add_argument("--tag", default="v0.7.12")
    parser.add_argument(
        "--mode",
        required=True,
        choices=("macos", "windows", "linux", "android"),
    )
    parser.add_argument("--variant", choices=("arm64", "intel"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    expected = _checksum_map(args.tag)
    with tempfile.TemporaryDirectory(prefix="melodex-published-smoke-") as temporary:
        work = Path(temporary)
        if args.mode == "macos":
            if not args.variant:
                parser.error("--variant is required for macos")
            result = _macos(args.tag, args.variant, work, expected)
        elif args.mode == "windows":
            result = _windows(args.tag, work, expected)
        elif args.mode == "linux":
            result = _linux(args.tag, work, expected)
        else:
            result = _android(args.tag, work, expected)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", "utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
