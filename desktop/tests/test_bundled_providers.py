from __future__ import annotations

from melodex.bundled_sources import bundled_packages, bundled_provider_ids


EXPECTED = {
    "org.melodex.internetarchive.audio",
    "org.melodex.librivox",
    "org.melodex.radiobrowser",
    "org.melodex.somafm",
    "org.melodex.wikimedia.commons.audio",
    "org.melodex.ccmixter",
}


def test_expected_bundled_provider_ids_are_present():
    assert EXPECTED.issubset(set(bundled_provider_ids()))


def test_every_bundled_provider_has_manifest_and_python_entrypoint():
    for pid, package, manifest in bundled_packages():
        assert package.suffix == ".mdxprovider"
        assert manifest["id"] == pid
        assert manifest.get("name")
        assert manifest.get("version")
        assert manifest.get("entrypoints", {}).get("python") == "provider.py"
