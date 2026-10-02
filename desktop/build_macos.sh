#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv-build
source .venv-build/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-build.txt
rm -rf build dist
pyinstaller --noconfirm --windowed --name Melodex --icon ../assets/icon.png --add-data "melodex/assets/melodex-mark.png:melodex/assets" --add-data "melodex/bundled_providers:melodex/bundled_providers" run.py
python check_bundled_provider_payload.py dist/Melodex.app
python tools/audit_qt_dependencies.py dist/Melodex.app \
  --json-out dist/Melodex-qt-audit-before.json \
  --markdown-out dist/Melodex-qt-audit-before.md
python tools/prune_qt_bundle.py dist/Melodex.app \
  --json-out dist/Melodex-qt-prune.json \
  --markdown-out dist/Melodex-qt-prune.md
python tools/audit_qt_dependencies.py dist/Melodex.app \
  --json-out dist/Melodex-qt-audit.json \
  --markdown-out dist/Melodex-qt-audit.md
if command -v codesign >/dev/null; then
  codesign --force --deep --sign - dist/Melodex.app
fi
python tools/check_qt_bundle.py dist/Melodex.app
python frozen_child_smoke.py "dist/Melodex.app/Contents/MacOS/Melodex"
mkdir -p dist/release
cp -R dist/Melodex.app dist/release/ 2>/dev/null || true
if command -v hdiutil >/dev/null && [ -d dist/Melodex.app ]; then
  rm -f dist/Melodex.dmg
  for attempt in 1 2 3; do
    if hdiutil create -volname Melodex -srcfolder dist/Melodex.app -ov -format UDZO dist/Melodex.dmg; then
      break
    fi
    if [ "$attempt" -eq 3 ]; then
      echo "hdiutil failed after 3 attempts" >&2
      exit 1
    fi
    echo "hdiutil create failed (attempt $attempt); retrying…" >&2
    sleep $((attempt * 3))
  done
fi

if [ -f dist/Melodex.dmg ]; then
  python tools/report_bundle_size.py dist/Melodex.app \
    --archive dist/Melodex.dmg \
    --json-out dist/Melodex-bundle-size.json \
    --markdown-out dist/Melodex-bundle-size.md
else
  python tools/report_bundle_size.py dist/Melodex.app \
    --json-out dist/Melodex-bundle-size.json \
    --markdown-out dist/Melodex-bundle-size.md
fi
