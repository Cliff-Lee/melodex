from __future__ import annotations

import json
import zipfile
from pathlib import Path

from melodex.bundled_sources import bundled_packages, bundled_provider_ids
from melodex.provider_manager import ProviderManager


EXPECTED = {
    "org.melodex.internetarchive.audio": "0.1.2",
    "org.melodex.librivox": "0.1.5",
    "org.melodex.nichedb.radio": "0.1.2",
    "org.melodex.radiobrowser": "0.1.2",
    "org.melodex.somafm": "0.1.1",
    "org.melodex.wikimedia.commons.audio": "0.1.1",
    "org.melodex.ccmixter": "0.1.3",
}


def test_expected_bundled_provider_ids_are_present():
    assert set(bundled_provider_ids()) == set(EXPECTED)


def test_every_bundled_provider_has_manifest_and_python_entrypoint():
    for pid, package, manifest in bundled_packages():
        assert package.suffix == ".mdxprovider"
        assert manifest["id"] == pid
        assert manifest.get("name")
        assert manifest.get("version") == EXPECTED[pid]
        assert manifest.get("entrypoints", {}).get("python") == "provider.py"
        with zipfile.ZipFile(package) as archive:
            compile(archive.read("provider.py"), f"{package.name}:provider.py", "exec")


def test_internetarchive_bundle_matches_checked_in_source():
    source = Path(__file__).resolve().parents[1] / "bundled_provider_sources" / "internetarchive_audio"
    package = next(
        package
        for pid, package, _manifest in bundled_packages()
        if pid == "org.melodex.internetarchive.audio"
    )
    with zipfile.ZipFile(package) as archive:
        packaged_manifest = json.loads(archive.read("manifest.json"))
        source_manifest = json.loads((source / "manifest.json").read_text("utf-8"))
        assert packaged_manifest == source_manifest
        for filename in ("provider.py", "README.md", "SOURCE_POLICY.md"):
            assert archive.read(filename) == (source / filename).read_bytes()


def test_librivox_bundle_matches_checked_in_source():
    source = Path(__file__).resolve().parents[1] / "bundled_provider_sources" / "librivox"
    package = next(
        package
        for pid, package, _manifest in bundled_packages()
        if pid == "org.melodex.librivox"
    )
    with zipfile.ZipFile(package) as archive:
        packaged_manifest = json.loads(archive.read("manifest.json"))
        source_manifest = json.loads((source / "manifest.json").read_text("utf-8"))
        assert packaged_manifest == source_manifest
        assert archive.read("provider.py") == (source / "provider.py").read_bytes()
        assert archive.read("README.md") == (source / "README.md").read_bytes()


def test_nichedb_radio_bundle_matches_checked_in_source():
    source = Path(__file__).resolve().parents[1] / "bundled_provider_sources" / "nichedb_radio"
    package = next(
        package
        for pid, package, _manifest in bundled_packages()
        if pid == "org.melodex.nichedb.radio"
    )
    with zipfile.ZipFile(package) as archive:
        packaged_manifest = json.loads(archive.read("manifest.json"))
        source_manifest = json.loads((source / "manifest.json").read_text("utf-8"))
        assert packaged_manifest == source_manifest
        for filename in ("provider.py", "README.md", "SOURCE_POLICY.md"):
            assert archive.read(filename) == (source / filename).read_bytes()


def _provider_package(
    path: Path,
    plugin_id: str,
    version: str,
    name: str = "Test provider",
) -> Path:
    manifest = {
        "schema_version": 1,
        "id": plugin_id,
        "name": name,
        "version": version,
        "capabilities": ["search", "track", "playback"],
        "permissions": {"network_hosts": []},
        "entrypoints": {"python": "provider.py"},
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("provider.py", "# test package\n")
    return path


def test_providers_install_on_first_run_and_restore_after_removal(tmp_path: Path):
    data_dir = tmp_path / "data"
    manager = ProviderManager(data_dir)
    try:
        assert set(EXPECTED).issubset(manager.providers)
        for plugin_id, version in EXPECTED.items():
            record = manager.installation_record(plugin_id)
            assert record["method"] == "bundled"
            assert record["version"] == version

        removed_id = "org.melodex.somafm"
        assert manager.remove_provider(removed_id) is True
        assert removed_id not in manager.providers
    finally:
        manager.close()

    second = ProviderManager(data_dir)
    try:
        assert "org.melodex.somafm" not in second.providers
        assert "org.melodex.radiobrowser" in second.providers
        restored = second.restore_bundled_providers()
        assert "org.melodex.somafm" in restored
        assert set(EXPECTED).issubset(second.providers)
    finally:
        second.close()


def test_newer_manual_provider_is_not_downgraded_by_bundle(tmp_path: Path):
    data_dir = tmp_path / "data"
    manager = ProviderManager(data_dir)
    try:
        package = _provider_package(
            tmp_path / "somafm-newer.mdxprovider", "org.melodex.somafm", "9.0.0"
        )
        manager.install_package(package)
    finally:
        manager.close()

    second = ProviderManager(data_dir)
    try:
        assert second.providers["org.melodex.somafm"].info.version == "9.0.0"
        assert second.installation_record("org.melodex.somafm")["method"] == "manual"
    finally:
        second.close()


def test_legacy_private_development_provider_is_quarantined_and_rejected(tmp_path: Path):
    data_dir = tmp_path / "data"
    legacy_name = "Music" + "MP3" + " (Experimental)"
    plugin_id = "org.example.legacy.private"
    package = _provider_package(
        tmp_path / "legacy-private.mdxprovider",
        plugin_id,
        "0.1.0",
        name=legacy_name,
    )

    manager = ProviderManager(data_dir)
    try:
        import pytest
        with pytest.raises(ValueError, match="legacy development provider"):
            manager.install_package(package)
        assert not (manager.installer.providers_dir / plugin_id).exists()

        # Simulate an old development build that had already installed the
        # provider before the public-release quarantine existed.
        manager.installer.install(package)
    finally:
        manager.close()

    reopened = ProviderManager(data_dir)
    try:
        assert plugin_id not in reopened.providers
        rows = reopened.quarantined_legacy_providers()
        assert any(row["id"] == plugin_id for row in rows)
        assert any(row["name"] == legacy_name for row in rows)
    finally:
        reopened.close()



def test_superseded_example_radio_and_librivox_are_hidden_when_real_sources_exist(
    tmp_path: Path,
):
    data_dir = tmp_path / "data"
    radio_example = _provider_package(
        tmp_path / "radio-example.mdxprovider",
        "org.melodex.example.radio-browser",
        "0.1.1",
        name="Radio Browser Example",
    )
    librivox_example = _provider_package(
        tmp_path / "librivox-example.mdxprovider",
        "org.melodex.example.librivox",
        "0.1.1",
        name="LibriVox Example",
    )

    manager = ProviderManager(data_dir)
    try:
        # Simulate an older Melodex install that already had the SDK examples.
        manager.installer.install(radio_example)
        manager.installer.install(librivox_example)
    finally:
        manager.close()

    reopened = ProviderManager(data_dir)
    try:
        assert "org.melodex.radiobrowser" in reopened.providers
        assert "org.melodex.librivox" in reopened.providers
        assert "org.melodex.example.radio-browser" not in reopened.providers
        assert "org.melodex.example.librivox" not in reopened.providers

        superseded = {
            row["id"]: row["replacement"]
            for row in reopened.superseded_providers()
        }
        assert superseded["org.melodex.example.radio-browser"] == "org.melodex.radiobrowser"
        assert superseded["org.melodex.example.librivox"] == "org.melodex.librivox"

        order = reopened.provider_order()
        assert "org.melodex.example.radio-browser" not in order
        assert "org.melodex.example.librivox" not in order
    finally:
        reopened.close()


def test_reinstalling_superseded_example_source_is_rejected(tmp_path: Path):
    import pytest

    manager = ProviderManager(tmp_path / "data")
    try:
        package = _provider_package(
            tmp_path / "radio-example.mdxprovider",
            "org.melodex.example.radio-browser",
            "0.1.1",
            name="Radio Browser Example",
        )
        with pytest.raises(ValueError, match="replaced by the included Radio Browser"):
            manager.install_package(package)
        assert "org.melodex.example.radio-browser" not in manager.providers
    finally:
        manager.close()
