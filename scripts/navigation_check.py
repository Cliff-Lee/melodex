from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text("utf-8")


def main() -> int:
    errors: list[str] = []

    root_readme = read("README.md")
    docs_home = read("docs/README.md")
    start = read("docs/START_HERE.md")
    developer_gateway = read("docs/DEVELOPERS.md")
    developer_reference = read("docs/developers/README.md")
    complete_index = read("docs/ALL_DOCUMENTATION.md")
    first_contribution = read("docs/FIRST_CONTRIBUTION.md")
    support = read("SUPPORT.md")
    ui = (
        read("desktop/melodex/main_window.py")
        + "\n"
        + read("desktop/melodex/library_browser.py")
    )

    # One obvious docs front door from the project landing page.
    if '<a href="docs/README.md">Docs</a>' not in root_readme:
        errors.append("README top navigation must point Docs to docs/README.md")
    if "docs/FIRST_CONTRIBUTION.md" not in root_readme:
        errors.append("README must link to docs/FIRST_CONTRIBUTION.md")

    # Friendly docs home should route to the canonical audience entry points.
    for link in (
        "START_HERE.md",
        "DEVELOPERS.md",
        "ALL_DOCUMENTATION.md",
        "FIRST_CONTRIBUTION.md",
    ):
        if link not in docs_home:
            errors.append(f"docs/README.md must link to {link}")

    if "friendly documentation map" not in docs_home.lower():
        errors.append("docs/README.md must identify itself as the friendly documentation map")

    if "complete documentation index" not in complete_index.lower():
        errors.append(
            "docs/ALL_DOCUMENTATION.md must identify itself as the complete documentation index"
        )

    # Developer gateway and deep reference must have distinct, reciprocal roles.
    if "Developer Gateway" not in developer_gateway:
        errors.append("docs/DEVELOPERS.md must identify itself as the Developer Gateway")
    if "developers/README.md" not in developer_gateway:
        errors.append("Developer Gateway must link to the developer reference index")
    if "Developer Reference Index" not in developer_reference:
        errors.append(
            "docs/developers/README.md must identify itself as the Developer Reference Index"
        )
    if "../DEVELOPERS.md" not in developer_reference:
        errors.append("developer reference index must link back to the Developer Gateway")

    if "contribute **to the melodex repository**" not in first_contribution.lower():
        errors.append(
            "docs/FIRST_CONTRIBUTION.md must identify itself as repository contribution onboarding"
        )
    if "export diagnostics…" not in support.lower():
        errors.append("SUPPORT.md must document the redacted diagnostics export")

    # First-use instructions intentionally use the source-management route.
    canonical_first_use_labels = (
        "Home",
        "My Music",
        "+ Add music",
        "▶  Play something",
        "Tune it…",
    )
    for label in canonical_first_use_labels:
        if f"**{label}**" not in start:
            errors.append(f"docs/START_HERE.md is missing canonical UI label {label!r}")
        if label not in ui:
            errors.append(
                f"docs/START_HERE.md references {label!r}, but it is absent from main_window.py"
            )

    # Advanced source labels documented elsewhere should remain exact too.
    for label in (
        "Power tools",
        "Explore plugins",
        "Install .mdxprovider…",
        "Install .mdxplugin…",
        "Provider Bridge…",
        "Export diagnostics…",
    ):
        if label not in ui:
            errors.append(f"expected current Sources UI label is missing: {label!r}")

    if errors:
        print("Documentation navigation check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        "Documentation navigation check passed: "
        "landing page, friendly router, first-use path, developer gateway/reference, "
        "complete index, and canonical UI labels agree"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
