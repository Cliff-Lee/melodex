from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_PARTS = {
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    "__pycache__",
    ".pytest_cache",
}

RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?<!registry-)\bverified packages?\b", re.IGNORECASE),
        "use the precise term 'registry-verified package/install'",
    ),
    (
        re.compile(r"\bhash[- ]verified packages?\b", re.IGNORECASE),
        "hash verification alone is not the full registry-verification definition",
    ),
    (
        re.compile(r"\bofficial providers?\b", re.IGNORECASE),
        "use 'project-maintained reference provider' for Melodex-maintained integrations",
    ),
    (
        re.compile(r"\bofficial reference\b", re.IGNORECASE),
        "use 'project-maintained reference' for Melodex-maintained integrations",
    ),
    (
        re.compile(r"\bMelodex-reviewed\b", re.IGNORECASE),
        "use 'reviewed registry entry/status'",
    ),
    (
        re.compile(r"\bnot reviewed by Melodex\b", re.IGNORECASE),
        "use 'not registry-reviewed'",
    ),
    (
        re.compile(
            r"\bstable (?:MPP|protocol|Provider SDK|provider manifest|API)\b",
            re.IGNORECASE,
        ),
        "do not imply a stable compatibility commitment while MPP/SDK remain preview/0.x",
    ),
    (
        re.compile(r"\bstable semantics\b", re.IGNORECASE),
        "use 'consistent high-level semantics' unless making a formal stability commitment",
    ),
    (
        re.compile(r"\bsafe descriptive fields\b", re.IGNORECASE),
        "name the property: 'allowlisted descriptive fields'",
    ),
    (
        re.compile(r"\bmetadata-safe\b", re.IGNORECASE),
        "name the property: 'metadata-only'",
    ),
    (
        re.compile(r"\bwhat sources ship with\b", re.IGNORECASE),
        "distinguish 'built into the app' from repository/registry availability",
    ),
)


def markdown_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.md"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def visible_lines(text: str):
    """Yield line number and text outside fenced code blocks."""
    fence: str | None = None
    backtick_fence = chr(96) * 3
    tilde_fence = "~" * 3
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if fence is None and (
            stripped.startswith(backtick_fence)
            or stripped.startswith(tilde_fence)
        ):
            fence = stripped[:3]
            continue
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        yield number, line


def main() -> int:
    errors: list[str] = []
    checked = markdown_files()

    for path in checked:
        text = path.read_text("utf-8", errors="replace")
        for number, line in visible_lines(text):
            for pattern, guidance in RULES:
                if pattern.search(line):
                    errors.append(
                        f"{path.relative_to(ROOT)}:{number}: {line.strip()} "
                        f"— {guidance}"
                    )

            lower = line.lower()
            if "sandboxed" in lower:
                negative_context = any(
                    phrase in lower
                    for phrase in (
                        "not sandboxed",
                        "not be described as sandboxed",
                        "do not describe",
                    )
                )
                if not negative_context:
                    errors.append(
                        f"{path.relative_to(ROOT)}:{number}: {line.strip()} "
                        "— current plugins must not be described as sandboxed"
                    )

    if errors:
        print("Terminology/claim check failed:")
        for error in sorted(set(errors)):
            print(f"  - {error}")
        return 1

    print(
        f"Terminology/claim check passed: {len(checked)} Markdown files "
        "use the canonical trust/maturity vocabulary"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
