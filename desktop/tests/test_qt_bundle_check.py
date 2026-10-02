from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


def _load_checker():
    path = Path(__file__).resolve().parents[1] / "tools" / "check_qt_bundle.py"
    spec = importlib.util.spec_from_file_location("check_qt_bundle", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _touch(root: Path, relative: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def test_minimal_qt_bundle_accepts_only_required_modules(tmp_path: Path):
    checker = _load_checker()
    root = tmp_path / "Melodex.app"
    for name in ("QtCore", "QtGui", "QtWidgets", "QtMultimedia"):
        _touch(root, f"Contents/Frameworks/PySide6/{name}.abi3.so")

    errors, findings = checker.validate_bundle(root)

    assert errors == []
    assert findings == []


def test_qt_bundle_rejects_webengine_and_qml_payload(tmp_path: Path):
    checker = _load_checker()
    root = tmp_path / "Melodex.app"
    for name in ("QtCore", "QtGui", "QtWidgets", "QtMultimedia"):
        _touch(root, f"Contents/Frameworks/PySide6/{name}.abi3.so")
    _touch(
        root,
        "Contents/Frameworks/PySide6/Qt/lib/"
        "QtWebEngineCore.framework/Versions/A/QtWebEngineCore",
    )
    _touch(
        root,
        "Contents/Frameworks/PySide6/Qt/qml/QtQuick/Controls/plugin.dylib",
    )

    errors, findings = checker.validate_bundle(root)

    assert any("qtwebengine" in error for error in errors)
    assert any("/qt/qml/" in error for error in errors)
    assert findings


def test_qt_bundle_rejects_missing_required_module(tmp_path: Path):
    checker = _load_checker()
    root = tmp_path / "Melodex"
    for name in ("QtCore", "QtGui", "QtWidgets"):
        _touch(root, f"_internal/PySide6/{name}.pyd")

    errors, _ = checker.validate_bundle(root)

    assert "required PySide6 module missing: qtmultimedia" in errors



def test_melodex_source_only_imports_expected_qt_families():
    root = Path(__file__).resolve().parents[1] / "melodex"
    families = set()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text("utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("PySide6.Qt"):
                    families.add(node.module.split(".", 1)[0].removeprefix("PySide6."))

    assert families <= {
        "QtCore",
        "QtGui",
        "QtWidgets",
        "QtMultimedia",
    }, f"Unexpected Qt families imported: {sorted(families)}"
