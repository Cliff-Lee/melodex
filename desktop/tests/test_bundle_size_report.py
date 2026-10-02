from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_reporter():
    path = Path(__file__).resolve().parents[1] / "tools" / "report_bundle_size.py"
    spec = importlib.util.spec_from_file_location("report_bundle_size", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bundle_size_report_counts_real_files_without_following_symlinks(tmp_path: Path):
    reporter = _load_reporter()
    bundle = tmp_path / "Melodex.app"
    frameworks = bundle / "Contents" / "Frameworks"
    resources = bundle / "Contents" / "Resources"
    frameworks.mkdir(parents=True)
    resources.mkdir(parents=True)

    (frameworks / "QtCore.dylib").write_bytes(b"x" * 100)
    (frameworks / "QtGui.dylib").write_bytes(b"x" * 200)
    (resources / "data.json").write_bytes(b"x" * 50)

    link = frameworks / "QtCore-current.dylib"
    try:
        link.symlink_to(frameworks / "QtCore.dylib")
    except OSError:
        link = None

    archive = tmp_path / "Melodex.dmg"
    archive.write_bytes(b"x" * 80)

    report = reporter.build_report(bundle, archive=archive, largest_count=10)

    assert report["total_bytes"] == 350
    assert report["file_count"] == 3
    assert report["archive"]["bytes"] == 80
    assert report["largest_files"][0]["path"].endswith("QtGui.dylib")
    assert report["largest_files"][0]["bytes"] == 200

    buckets = {
        row["name"]: row["bytes"]
        for row in report["directory_buckets_depth_2"]
    }
    assert buckets["Contents/Frameworks"] == 300
    assert buckets["Contents/Resources"] == 50

    if link is not None:
        assert all(
            row["path"] != "Contents/Frameworks/QtCore-current.dylib"
            for row in report["largest_files"]
        )


def test_bundle_size_markdown_surfaces_largest_areas(tmp_path: Path):
    reporter = _load_reporter()
    bundle = tmp_path / "Melodex.app"
    target = bundle / "Contents" / "Frameworks"
    target.mkdir(parents=True)
    (target / "huge.dylib").write_bytes(b"x" * 1024)

    report = reporter.build_report(bundle)
    rendered = reporter.markdown_report(report)

    assert "Melodex bundle size report" in rendered
    assert "Contents/Frameworks/huge.dylib" in rendered
    assert "1.0 KB" in rendered
