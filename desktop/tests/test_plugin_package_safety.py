from __future__ import annotations

import json
import os
import stat
import zipfile
from pathlib import Path

import pytest

from melodex.capabilities import ExtensionInstaller, validate_descriptor
from melodex.package_safety import extract_archive
from melodex.provider import ProviderInstaller
import melodex.package_safety as package_safety


def _write_provider_package(
    path: Path,
    *,
    entrypoint: str = "provider.py",
    extra: list[tuple[str, bytes | str | zipfile.ZipInfo]] | None = None,
) -> None:
    manifest = {
        "schema_version": 1,
        "id": "org.example.safe",
        "name": "Safe",
        "version": "1.0.0",
        "capabilities": ["search"],
        "permissions": {"network_hosts": []},
        "entrypoints": {"python": entrypoint},
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("provider.py", "print('worker')\n")
        for name, payload in extra or []:
            if isinstance(payload, zipfile.ZipInfo):
                archive.writestr(payload, name.encode("utf-8"))
            else:
                archive.writestr(name, payload)


def _write_extension_package(
    path: Path,
    *,
    entrypoint: str = "plugin.py",
) -> None:
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.safe-extension",
        "name": "Safe Extension",
        "version": "1.0.0",
        "entrypoints": {"python": entrypoint},
        "contracts": [
            {
                "capability": "metadata",
                "contract_version": "0.1",
                "method": "metadata.enrich",
            }
        ],
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("capabilities.json", json.dumps(descriptor))
        archive.writestr("plugin.py", "print('worker')\n")


@pytest.mark.parametrize(
    "value",
    [
        "../outside.py",
        "../../outside.py",
        "/tmp/outside.py",
        "C:\\outside.py",
    ],
)
def test_extension_descriptor_rejects_unsafe_entrypoints(value: str):
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.unsafe",
        "name": "Unsafe",
        "entrypoints": {"python": value},
        "contracts": [
            {
                "capability": "metadata",
                "contract_version": "0.1",
                "method": "metadata.enrich",
            }
        ],
    }
    errors = validate_descriptor(descriptor)
    assert any("entrypoints.python" in error for error in errors)


def test_provider_package_rejects_unsafe_entrypoint(tmp_path: Path):
    package = tmp_path / "unsafe.mdxprovider"
    _write_provider_package(package, entrypoint="../outside.py")
    with pytest.raises(ValueError, match="entrypoints"):
        ProviderInstaller(tmp_path / "providers").install(package)


def test_extension_package_rejects_unsafe_entrypoint(tmp_path: Path):
    package = tmp_path / "unsafe.mdxplugin"
    _write_extension_package(package, entrypoint="/tmp/outside.py")
    with pytest.raises(ValueError, match="entrypoints"):
        ExtensionInstaller(tmp_path / "extensions").install(package)


def test_provider_package_requires_exactly_one_manifest(tmp_path: Path):
    package = tmp_path / "duplicate.mdxprovider"
    manifest = {
        "id": "org.example.dupe",
        "name": "Dupe",
        "entrypoints": {"python": "provider.py"},
    }
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("nested/manifest.json", json.dumps(manifest))
        archive.writestr("provider.py", "pass\n")
    with pytest.raises(ValueError, match="exactly one manifest"):
        ProviderInstaller(tmp_path / "providers").install(package)


def test_extension_package_requires_exactly_one_descriptor(tmp_path: Path):
    package = tmp_path / "duplicate.mdxplugin"
    descriptor = {
        "schema_version": "0.1",
        "extension_id": "org.example.dupe",
        "name": "Dupe",
        "contracts": [
            {
                "capability": "metadata",
                "contract_version": "0.1",
                "method": "metadata.enrich",
            }
        ],
    }
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("capabilities.json", json.dumps(descriptor))
        archive.writestr("nested/capabilities.json", json.dumps(descriptor))
        archive.writestr("plugin.py", "pass\n")
    with pytest.raises(ValueError, match="exactly one capabilities"):
        ExtensionInstaller(tmp_path / "extensions").install(package)


def test_archive_rejects_symlink_member(tmp_path: Path):
    package = tmp_path / "symlink.zip"
    link = zipfile.ZipInfo("link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(link, "target")
    with zipfile.ZipFile(package) as archive:
        with pytest.raises(ValueError, match="Symlinks"):
            extract_archive(
                archive,
                prefix=Path("."),
                destination=tmp_path / "out",
            )


def test_archive_rejects_duplicate_target(tmp_path: Path):
    package = tmp_path / "duplicate-path.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("same.txt", "one")
        archive.writestr("same.txt", "two")
    with zipfile.ZipFile(package) as archive:
        with pytest.raises(ValueError, match="Duplicate path"):
            extract_archive(
                archive,
                prefix=Path("."),
                destination=tmp_path / "out",
            )


def test_archive_enforces_uncompressed_size_limit(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(package_safety, "MAX_EXTRACTED_BYTES", 10)
    package = tmp_path / "large.zip"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("large.txt", "x" * 64)
    with zipfile.ZipFile(package) as archive:
        with pytest.raises(ValueError, match="100 MB safety limit"):
            extract_archive(
                archive,
                prefix=Path("."),
                destination=tmp_path / "out",
            )


def test_failed_provider_update_keeps_previous_install(monkeypatch, tmp_path: Path):
    providers = tmp_path / "providers"
    old = providers / "org.example.safe"
    old.mkdir(parents=True)
    (old / "manifest.json").write_text('{"id":"org.example.safe"}', "utf-8")
    (old / "marker.txt").write_text("old-working-install", "utf-8")

    monkeypatch.setattr(package_safety, "MAX_EXTRACTED_BYTES", 40)
    package = tmp_path / "bad-update.mdxprovider"
    _write_provider_package(
        package,
        extra=[("large.dat", b"x" * 128)],
    )

    with pytest.raises(ValueError, match="100 MB safety limit"):
        ProviderInstaller(providers).install(package)

    assert (old / "marker.txt").read_text("utf-8") == "old-working-install"


@pytest.mark.skipif(os.name == "nt", reason="Unix executable bits are not meaningful on Windows")
def test_archive_preserves_executable_bits(tmp_path: Path):
    package = tmp_path / "native.zip"
    native = zipfile.ZipInfo("bin/worker")
    native.create_system = 3
    native.external_attr = (stat.S_IFREG | 0o755) << 16
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(native, "#!/bin/sh\nexit 0\n")
    out = tmp_path / "out"
    with zipfile.ZipFile(package) as archive:
        extract_archive(archive, prefix=Path("."), destination=out)
    assert os.access(out / "bin" / "worker", os.X_OK)
