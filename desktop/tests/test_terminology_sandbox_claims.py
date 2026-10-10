from __future__ import annotations

import runpy
from pathlib import Path


def _checker():
    script = Path(__file__).resolve().parents[2] / "scripts" / "terminology_check.py"
    return runpy.run_path(str(script))["has_misleading_sandbox_claim"]


def test_security_warnings_about_unsandboxed_plugins_are_allowed():
    misleading = _checker()
    for text in (
        "Melodex's desktop plugins are not fully sandboxed from your user account.",
        "These plugins are not sandboxed.",
        "Extensions are not completely sandboxed from local files.",
        "Packages are not entirely sandboxed.",
    ):
        assert not misleading(text)


def test_misleading_plugin_sandbox_promises_remain_forbidden():
    misleading = _checker()
    for text in (
        "Desktop plugins are sandboxed.",
        "All packages are securely sandboxed.",
        "Third-party extensions are fully sandboxed.",
        "Plugins are sandboxed, although some packages are not fully sandboxed.",
    ):
        assert misleading(text)
