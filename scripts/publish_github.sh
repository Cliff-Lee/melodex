#!/usr/bin/env bash
set -euo pipefail

OWNER="${1:-Cliff-Lee}"
REPO="${2:-melodex}"
VISIBILITY="${MELODEX_VISIBILITY:-public}"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required." >&2
  exit 1
fi
if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required. Install it, then run: gh auth login" >&2
  exit 1
fi

echo "Running Melodex public-release audit..."
python3 scripts/release_check.py

if [[ ! -d .git ]]; then
  git init
fi

git add .
if ! git diff --cached --quiet; then
  git commit -m "Initial public Melodex release"
fi

git branch -M main

if gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "https://github.com/$OWNER/$REPO.git"
  fi
else
  gh repo create "$OWNER/$REPO" --"$VISIBILITY" --source=. --remote=origin --description "Source-neutral music player with Flow sequencing, optional LLM control, and an open provider protocol"
fi

git push -u origin main

echo "Published: https://github.com/$OWNER/$REPO"
