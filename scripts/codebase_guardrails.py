#!/usr/bin/env python3
"""Small structural ratchets for Campaign 12.

These are intentionally narrow. P12b prevents known hotspots from getting worse
without treating arbitrary line-count targets as architecture goals.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_MAIN_WINDOW_SNIPPETS = {
    "from .plugin_configuration_dialog import": "plugin configuration belongs to SourcesFeature",
    "from .plugin_directory import": "plugin directory belongs to SourcesFeature",
    "from .plugin_onboarding import": "plugin onboarding belongs to SourcesFeature",
    "def _build_sources": "Sources page construction belongs to SourcesFeature",
    "def _refresh_sources": "Sources rendering belongs to SourcesFeature",
    "self.sources_list": "Sources widgets belong to SourcesFeature",
    "self.source_primary_button": "Sources widgets belong to SourcesFeature",
    "self.source_power_panel": "Sources widgets belong to SourcesFeature",
}

# Baseline is the v0.7.11 main_window.py snapshot from P12a. Lower this number
# as P12c extracts responsibilities; never raise it to accommodate new work.
MAX_LINES = {
    "desktop/melodex/main_window.py": 6115,
}


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def main() -> int:
    failures: list[str] = []
    for relative, maximum in MAX_LINES.items():
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"{relative}: file is missing")
            continue

        current = line_count(path)
        direction = "OK" if current <= maximum else "FAIL"
        print(f"{direction}: {relative}: {current} lines (maximum {maximum})")
        if current > maximum:
            failures.append(
                f"{relative} grew to {current} lines; Campaign 12 baseline is {maximum}. "
                "Extract responsibility or reduce the file instead of raising the limit."
            )

    main_window = (ROOT / "desktop/melodex/main_window.py").read_text(
        encoding="utf-8"
    )
    for snippet, reason in FORBIDDEN_MAIN_WINDOW_SNIPPETS.items():
        if snippet in main_window:
            failures.append(
                f"desktop/melodex/main_window.py contains {snippet!r}; {reason}."
            )

    if failures:
        print("\nCodebase guardrail failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
