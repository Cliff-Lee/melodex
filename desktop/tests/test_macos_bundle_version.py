from __future__ import annotations

import importlib.util
import plistlib
from pathlib import Path

import pytest


def _module():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "set_macos_bundle_version.py"
    spec = importlib.util.spec_from_file_location("set_macos_bundle_version", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bundle_versions_strip_dev_suffix_and_use_numeric_build() -> None:
    module = _module()
    assert module.bundle_versions("0.7.7") == ("0.7.7", "707")
    assert module.bundle_versions("0.7.8.dev0") == ("0.7.8", "708")
    assert module.bundle_versions("1.2.3.dev14") == ("1.2.3", "10203")


def test_bundle_versions_reject_invalid_version() -> None:
    module = _module()
    with pytest.raises(ValueError):
        module.bundle_versions("0.7")


def test_stamp_bundle_updates_info_plist(tmp_path: Path) -> None:
    module = _module()
    app = tmp_path / "Melodex.app"
    contents = app / "Contents"
    contents.mkdir(parents=True)
    plist_path = contents / "Info.plist"
    with plist_path.open("wb") as handle:
        plistlib.dump(
            {
                "CFBundleName": "Melodex",
                "CFBundleShortVersionString": "0.0.0",
                "CFBundleVersion": "0",
            },
            handle,
        )

    short_version, build_version = module.stamp_bundle(app, "0.7.8.dev0")

    assert (short_version, build_version) == ("0.7.8", "708")
    with plist_path.open("rb") as handle:
        payload = plistlib.load(handle)
    assert payload["CFBundleShortVersionString"] == "0.7.8"
    assert payload["CFBundleVersion"] == "708"
