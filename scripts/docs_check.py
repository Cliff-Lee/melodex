from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

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

MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HTML_LINK = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
REFERENCE_LINK = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)")


def markdown_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.md"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def visible_markdown(text: str) -> str:
    """Remove fenced code blocks so example paths are not treated as links."""
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        stripped = line.lstrip()
        backtick_fence = chr(96) * 3
        tilde_fence = "~" * 3
        if fence is None and (
            stripped.startswith(backtick_fence) or stripped.startswith(tilde_fence)
        ):
            fence = stripped[:3]
            continue
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        out.append(line)
    return "\n".join(out)


def link_targets(text: str) -> list[str]:
    targets = [match.group(1).strip() for match in MARKDOWN_LINK.finditer(text)]
    targets.extend(match.group(1).strip() for match in HTML_LINK.finditer(text))
    targets.extend(
        match.group(1).strip()
        for line in text.splitlines()
        if (match := REFERENCE_LINK.match(line))
    )
    return targets


def clean_target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1].strip()
    if " " in value and not value.startswith(("http://", "https://")):
        value = value.split(" ", 1)[0]
    return value


def is_external(target: str) -> bool:
    lower = target.lower()
    return lower.startswith(
        (
            "http://",
            "https://",
            "mailto:",
            "tel:",
            "data:",
            "javascript:",
        )
    )


def resolve_target(source: Path, target: str) -> Path | None:
    target = clean_target(target)
    if not target or target.startswith("#") or is_external(target):
        return None
    parsed = urlsplit(target)
    path_text = unquote(parsed.path)
    if not path_text:
        return None
    if path_text.startswith("/"):
        return (ROOT / path_text.lstrip("/")).resolve()
    return (source.parent / path_text).resolve()


def main() -> int:
    errors: list[str] = []
    checked = 0
    root_resolved = ROOT.resolve()
    files = markdown_files()

    for source in files:
        text = visible_markdown(source.read_text("utf-8", errors="replace"))
        for raw in link_targets(text):
            target = resolve_target(source, raw)
            if target is None:
                continue
            checked += 1
            try:
                target.relative_to(root_resolved)
            except ValueError:
                errors.append(
                    f"{source.relative_to(ROOT)} -> {raw!r}: points outside repository"
                )
                continue
            if not target.exists():
                errors.append(
                    f"{source.relative_to(ROOT)} -> {raw!r}: target does not exist"
                )

    if errors:
        print("Documentation check failed:")
        for error in sorted(set(errors)):
            print(f"  - {error}")
        return 1

    print(
        f"Documentation check passed: {len(files)} Markdown files, "
        f"{checked} internal links checked"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
