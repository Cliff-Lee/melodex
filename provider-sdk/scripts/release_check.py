from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "dist", "build", "__pycache__", ".pytest_cache", ".ruff_cache"}
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".toml", ".txt", ".ini", ".cfg", ".sh"}

# High-signal patterns only. This is a guardrail, not a substitute for a proper secret scanner.
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    "generic bearer secret": re.compile(r"Authorization:\s*Bearer\s+(?!demo-token\b)[A-Za-z0-9._~+/-]{24,}", re.I),
}

FORBIDDEN_PUBLIC_TERMS = []


def iter_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        yield path, rel


def main() -> int:
    failures: list[str] = []
    for path, rel in iter_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{rel}: possible {label}")
        if rel.as_posix() != "scripts/release_check.py":
            lower = text.casefold()
            for term in FORBIDDEN_PUBLIC_TERMS:
                if term.casefold() in lower:
                    failures.append(f"{rel}: public-source-neutrality term found: {term}")
    if failures:
        print("Release check failed:")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("Release check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
