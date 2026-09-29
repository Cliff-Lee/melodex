from __future__ import annotations

import os
import re
import shutil
import tempfile
import unicodedata
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

MAX_EXTRACTED_FILES = 2048
MAX_EXTRACTED_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 4096
_DRIVE_RE = re.compile(r"^[A-Za-z]:$")
_PLUGIN_ID_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?$")
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def validate_plugin_identifier(value: Any) -> str:
    """Return a portable plugin ID or raise ValueError."""

    if not isinstance(value, str):
        raise ValueError("Plugin identifier must be a string")
    identifier = value.strip()
    if (
        not _PLUGIN_ID_RE.fullmatch(identifier)
        or ".." in identifier
        or identifier.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES
    ):
        raise ValueError("Plugin identifier must be a safe 1–128 character ID")
    return identifier


def _portable_relative_path(value: Any) -> PurePosixPath:
    text = str(value or "").strip().replace("\\", "/")
    if not text or "\x00" in text:
        raise ValueError("Entrypoint path is empty or invalid")
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Entrypoint must stay inside the package: {text!r}")
    if path.parts and _DRIVE_RE.fullmatch(path.parts[0]):
        raise ValueError(f"Entrypoint must be relative: {text!r}")
    for part in path.parts:
        if (
            ":" in part
            or part.endswith((".", " "))
            or any(ord(char) < 32 or ord(char) == 127 for char in part)
            or any(char in '<>:"|?*' for char in part)
            or part.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES
        ):
            raise ValueError(f"Entrypoint contains a non-portable path component: {text!r}")
    cleaned = PurePosixPath(*[part for part in path.parts if part not in {"", "."}])
    if not cleaned.parts:
        raise ValueError("Entrypoint path is empty")
    return cleaned


def entrypoint_errors(entrypoints: Any) -> list[str]:
    if entrypoints is None:
        return []
    if not isinstance(entrypoints, dict):
        return ["entrypoints must be an object"]
    errors: list[str] = []
    for key, value in entrypoints.items():
        if not isinstance(value, str):
            errors.append(f"entrypoints.{key} must be a string")
            continue
        try:
            _portable_relative_path(value)
        except ValueError as exc:
            errors.append(f"entrypoints.{key}: {exc}")
    return errors


def resolve_entrypoint(root: Path, value: Any) -> Path:
    relative = _portable_relative_path(value)
    root = Path(root).resolve()
    target = (root / Path(*relative.parts)).resolve()
    if not target.is_relative_to(root):
        raise RuntimeError("Entrypoint resolves outside the installed package")
    if not target.is_file():
        raise RuntimeError(f"Plugin entrypoint is missing: {relative.as_posix()}")
    return target


def _relative_member(member_name: str, prefix: Path) -> PurePosixPath | None:
    source = PurePosixPath(member_name.replace("\\", "/"))
    portable_prefix = PurePosixPath(str(prefix).replace("\\", "/"))
    try:
        relative = source.relative_to(portable_prefix) if str(portable_prefix) != "." else source
    except ValueError:
        return None
    if not relative.parts or relative.name == "":
        return None
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unsafe path in plugin package")
    return relative


def extract_archive(
    archive: zipfile.ZipFile,
    *,
    prefix: Path,
    destination: Path,
) -> None:
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    files = 0
    total = 0
    entries = 0
    targets: set[str] = set()

    for member in archive.infolist():
        relative = _relative_member(member.filename, prefix)
        if relative is None:
            continue

        entries += 1
        if entries > MAX_ARCHIVE_ENTRIES:
            raise ValueError(
                f"Plugin package contains more than {MAX_ARCHIVE_ENTRIES} archive entries"
            )

        unix_type = (member.external_attr >> 16) & 0o170000
        if unix_type == 0o120000:
            raise ValueError("Symlinks are not allowed in plugin packages")
        if unix_type not in {0, 0o040000, 0o100000}:
            raise ValueError("Special files are not allowed in plugin packages")
        if member.flag_bits & 0x1:
            raise ValueError("Encrypted files are not allowed in plugin packages")

        target = (destination / relative).resolve()
        if not target.is_relative_to(destination):
            raise ValueError("Unsafe path in plugin package")
        key = unicodedata.normalize("NFC", relative.as_posix()).casefold()
        if key in targets:
            raise ValueError(f"Duplicate path in plugin package: {relative}")
        targets.add(key)

        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue

        files += 1
        if files > MAX_EXTRACTED_FILES:
            raise ValueError(
                f"Plugin package contains more than {MAX_EXTRACTED_FILES} files"
            )
        declared_size = int(member.file_size)
        if declared_size < 0 or declared_size > MAX_EXTRACTED_BYTES - total:
            raise ValueError(
                "Plugin package expands beyond the 100 MB safety limit"
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        actual_size = 0
        with archive.open(member) as source_file, target.open("wb") as output:
            while True:
                chunk = source_file.read(64 * 1024)
                if not chunk:
                    break
                actual_size += len(chunk)
                if actual_size > declared_size or actual_size > MAX_EXTRACTED_BYTES - total:
                    raise ValueError(
                        "Plugin package expands beyond the 100 MB safety limit"
                    )
                output.write(chunk)
        if actual_size != declared_size:
            raise ValueError("Plugin package member size does not match its ZIP directory")
        total += actual_size

        mode = (member.external_attr >> 16) & 0o777
        if mode and os.name != "nt":
            target.chmod(mode)


def staged_install_dir(parent: Path, identifier: str) -> Path:
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(identifier or "plugin"))[:80]
    return Path(tempfile.mkdtemp(prefix=f".{safe}-staging-", dir=str(parent)))


def replace_directory(staged: Path, destination: Path) -> None:
    staged = Path(staged)
    destination = Path(destination)
    backup: Path | None = None
    try:
        if destination.exists():
            backup = destination.with_name(
                destination.name + f".backup-{uuid.uuid4().hex}"
            )
            destination.rename(backup)
        staged.rename(destination)
    except Exception:
        if destination.exists() and backup is not None and backup.exists():
            shutil.rmtree(destination, ignore_errors=True)
        if backup is not None and backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    else:
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)


__all__ = [
    "MAX_EXTRACTED_FILES",
    "MAX_EXTRACTED_BYTES",
    "MAX_ARCHIVE_ENTRIES",
    "validate_plugin_identifier",
    "entrypoint_errors",
    "resolve_entrypoint",
    "extract_archive",
    "staged_install_dir",
    "replace_directory",
]
