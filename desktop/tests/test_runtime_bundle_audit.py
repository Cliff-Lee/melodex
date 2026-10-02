from __future__ import annotations

import importlib.util
from pathlib import Path

from melodex.runtime_smoke import runtime_report


def _load_auditor():
    path = Path(__file__).resolve().parents[1] / "tools" / "audit_runtime_bundle.py"
    spec = importlib.util.spec_from_file_location("audit_runtime_bundle", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _touch(root: Path, relative: str, size: int) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_runtime_report_exercises_core_non_qt_dependencies():
    report = runtime_report()

    assert int(report["numpy_fft_bins"]) > 0
    assert bool(report["ca_bundle_exists"]) is True
    assert "OpenSSL" in str(report["openssl"])
    assert str(report["keyring_backend"])


def test_runtime_bundle_audit_groups_non_qt_payload(tmp_path: Path):
    auditor = _load_auditor()
    root = tmp_path / "Melodex.app"

    _touch(root, "Contents/Frameworks/numpy/core.so", 100)
    _touch(root, "Contents/Frameworks/Python.framework/Python", 200)
    _touch(root, "Contents/Frameworks/libcrypto.3.dylib", 300)
    _touch(root, "Contents/Resources/keyring/backend.py", 40)
    _touch(root, "Contents/Resources/certifi/cacert.pem", 50)
    _touch(root, "Contents/Frameworks/PySide6/QtCore.abi3.so", 999)

    report = auditor.audit_runtime_payload(root)
    categories = report["categories"]

    assert categories["numpy"]["bytes"] == 100
    assert categories["python_runtime"]["bytes"] == 200
    assert categories["openssl"]["bytes"] == 300
    assert categories["keyring"]["bytes"] == 40
    assert categories["requests_stack"]["bytes"] == 50
    # Qt payload is intentionally excluded from the non-Qt audit.
    assert report["uncategorized_non_qt_bytes"] == 0
