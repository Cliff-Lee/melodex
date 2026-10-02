from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_reporter():
    path = Path(__file__).resolve().parents[1] / "tools" / "report_macos_trust.py"
    spec = importlib.util.spec_from_file_location("report_macos_trust", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_signature_mode_detects_ad_hoc_and_developer_id():
    reporter = _load_reporter()

    assert reporter._signature_mode("Signature=adhoc") == "ad-hoc"
    assert (
        reporter._signature_mode(
            "Authority=Developer ID Application: Example Person (ABCDE12345)"
        )
        == "developer-id"
    )


def test_hardened_runtime_detects_runtime_flag():
    reporter = _load_reporter()

    assert reporter._hardened_runtime("CodeDirectory v=20500 size=123 flags=0x10000(runtime)") is True
    assert reporter._hardened_runtime("CodeDirectory v=20400 size=123 flags=0x2(adhoc)") is False


def test_distribution_ready_requires_signed_stapled_dmg(monkeypatch, tmp_path: Path):
    reporter = _load_reporter()
    app = tmp_path / "Melodex.app"
    app.mkdir()
    dmg = tmp_path / "Melodex.dmg"
    dmg.write_bytes(b"dmg")

    responses = {
        ("codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app.resolve())):
            (0, "valid on disk"),
        ("codesign", "-dv", "--verbose=4", str(app.resolve())):
            (
                0,
                "Authority=Developer ID Application: Example Person (ABCDE12345)\n"
                "CodeDirectory v=20500 size=123 flags=0x10000(runtime)",
            ),
        ("spctl", "--assess", "--type", "execute", "--verbose=4", str(app.resolve())):
            (0, "accepted"),
        ("codesign", "--verify", "--strict", "--verbose=2", str(dmg.resolve())):
            (0, "valid on disk"),
        ("xcrun", "stapler", "validate", str(dmg.resolve())):
            (0, "The validate action worked!"),
        (
            "spctl",
            "--assess",
            "--type",
            "open",
            "--context",
            "context:primary-signature",
            "--verbose=4",
            str(dmg.resolve()),
        ): (0, "accepted"),
    }

    monkeypatch.setattr(
        reporter,
        "_run",
        lambda command: responses[tuple(command)],
    )

    result = reporter.build_report(app, dmg)

    assert result["signature_mode"] == "developer-id"
    assert result["hardened_runtime"] is True
    assert result["dmg"]["stapled"] is True
    assert result["distribution_ready"] is True


def test_preview_ad_hoc_build_is_not_distribution_ready(monkeypatch, tmp_path: Path):
    reporter = _load_reporter()
    app = tmp_path / "Melodex.app"
    app.mkdir()

    def fake_run(command):
        if command[:2] == ["codesign", "-dv"]:
            return 0, "Signature=adhoc\nCodeDirectory flags=0x2(adhoc)"
        if command[0] == "codesign":
            return 0, "valid on disk"
        return 1, "rejected"

    monkeypatch.setattr(reporter, "_run", fake_run)

    result = reporter.build_report(app)

    assert result["signature_mode"] == "ad-hoc"
    assert result["distribution_ready"] is False
