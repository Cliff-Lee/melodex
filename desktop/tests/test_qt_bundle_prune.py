from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_pruner():
    path = Path(__file__).resolve().parents[1] / "tools" / "prune_qt_bundle.py"
    spec = importlib.util.spec_from_file_location("prune_qt_bundle", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _touch(root: Path, relative: str, size: int = 1) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def test_pruner_removes_qpdf_and_orphaned_qtpdf(monkeypatch, tmp_path: Path):
    pruner = _load_pruner()
    root = tmp_path / "Melodex.app"
    plugin = _touch(
        root,
        "Contents/Frameworks/PySide6/Qt/plugins/imageformats/libqpdf.dylib",
        5,
    )
    framework = _touch(
        root,
        "Contents/Frameworks/PySide6/Qt/lib/QtPdf.framework/Versions/A/QtPdf",
        20,
    )

    monkeypatch.setattr(pruner.shutil, "which", lambda _name: "/usr/bin/otool")
    monkeypatch.setattr(pruner, "_dependencies", lambda _path: [])

    report = pruner.prune_bundle(root)

    assert not plugin.exists()
    assert not framework.exists()
    assert report["qt_pdf_pruned"] is True
    assert report["bytes_removed"] == 25


def test_pruner_keeps_qtpdf_when_another_binary_depends_on_it(monkeypatch, tmp_path: Path):
    pruner = _load_pruner()
    root = tmp_path / "Melodex.app"
    plugin = _touch(
        root,
        "Contents/Frameworks/PySide6/Qt/plugins/imageformats/libqpdf.dylib",
    )
    dependent = _touch(
        root,
        "Contents/Frameworks/something.dylib",
    )
    framework = _touch(
        root,
        "Contents/Frameworks/PySide6/Qt/lib/QtPdf.framework/Versions/A/QtPdf",
    )

    monkeypatch.setattr(pruner.shutil, "which", lambda _name: "/usr/bin/otool")
    monkeypatch.setattr(
        pruner,
        "_dependencies",
        lambda path: ["@rpath/QtPdf.framework/Versions/A/QtPdf"]
        if path == dependent
        else [],
    )

    report = pruner.prune_bundle(root)

    assert not plugin.exists()
    assert framework.exists()
    assert report["qt_pdf_pruned"] is False
    assert report["qt_pdf_dependents_after_plugin_removal"] == [
        "Contents/Frameworks/something.dylib"
    ]
