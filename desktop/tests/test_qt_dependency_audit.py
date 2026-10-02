from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_auditor():
    path = Path(__file__).resolve().parents[1] / "tools" / "audit_qt_dependencies.py"
    spec = importlib.util.spec_from_file_location("audit_qt_dependencies", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _touch(root: Path, relative: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def test_qt_audit_lists_target_payloads_without_otool(monkeypatch, tmp_path: Path):
    auditor = _load_auditor()
    root = tmp_path / "Melodex.app"
    _touch(
        root,
        "Contents/Frameworks/PySide6/Qt/lib/QtPdf.framework/Versions/A/QtPdf",
    )
    _touch(
        root,
        "Contents/Frameworks/PySide6/Qt/lib/QtQuick.framework/Versions/A/QtQuick",
    )
    _touch(
        root,
        "Contents/Frameworks/PySide6/Qt/plugins/imageformats/libqpdf.dylib",
    )

    monkeypatch.setattr(auditor.shutil, "which", lambda _name: None)

    report = auditor.audit_bundle(root)

    assert report["otool_available"] is False
    assert report["targets"]["QtPdf"]["payloads"]
    assert report["targets"]["QtQuick"]["payloads"]
    assert report["targets"]["QtQml"]["payloads"] == []
    assert any(
        "imageformats/libqpdf.dylib" in value
        for value in report["interesting_plugins"]
    )


def test_qt_audit_detects_direct_native_dependent(monkeypatch, tmp_path: Path):
    auditor = _load_auditor()
    root = tmp_path / "Melodex.app"
    plugin = (
        root
        / "Contents/Frameworks/PySide6/Qt/plugins/imageformats/libqpdf.dylib"
    )
    _touch(root, str(plugin.relative_to(root)))

    monkeypatch.setattr(auditor.shutil, "which", lambda _name: "/usr/bin/otool")
    monkeypatch.setattr(
        auditor,
        "_native_dependencies",
        lambda path: [
            "@rpath/QtPdf.framework/Versions/A/QtPdf"
        ] if path == plugin else [],
    )

    report = auditor.audit_bundle(root)

    assert report["targets"]["QtPdf"]["direct_dependents"] == [
        "Contents/Frameworks/PySide6/Qt/plugins/imageformats/libqpdf.dylib"
    ]
