from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
blocked_extensions = {".pyc", ".p12", ".pfx", ".jks", ".keystore"}
secret_patterns = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:api[_-]?key|password|secret)\s*[=:]\s*['\"][^'\"]{10,}['\"]"),
]
# Construct these in fragments so the audit script does not contain the exact legacy markers it rejects.
blocked_source_markers = [
    ("mp3" + "streams").lower(),
    ("music" + "mp3").lower(),
]
errors=[]
for p in ROOT.rglob("*"):
    if any(
        part in {".git", ".venv", ".venv-build", "build", "dist", "__pycache__"}
        for part in p.parts
    ):
        continue
    if not p.is_file():
        continue
    if p.suffix.lower() in blocked_extensions:
        errors.append(f"blocked file: {p.relative_to(ROOT)}")
    if p.stat().st_size >= 2_000_000:
        continue
    try:
        text=p.read_text("utf-8", errors="ignore")
    except Exception:
        text=""
    for pat in secret_patterns:
        if pat.search(text):
            errors.append(f"possible secret in {p.relative_to(ROOT)}")
    low=text.lower()
    for marker in blocked_source_markers:
        if marker in low:
            errors.append(f"legacy private-source marker in {p.relative_to(ROOT)}")
if errors:
    print("Release check failed:\n" + "\n".join(sorted(set(errors))))
    sys.exit(1)
print("Release check passed")
