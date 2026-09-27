#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv-build
source .venv-build/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-build.txt
rm -rf build dist
pyinstaller --noconfirm --windowed --name Melodex --icon ../assets/icon.png --add-data "melodex/assets/melodex-mark.png:melodex/assets" --add-data "melodex/bundled_providers:melodex/bundled_providers" --collect-all PySide6 run.py
mkdir -p dist/release
cp -R dist/Melodex.app dist/release/ 2>/dev/null || true
if command -v hdiutil >/dev/null && [ -d dist/Melodex.app ]; then
  rm -f dist/Melodex.dmg
  hdiutil create -volname Melodex -srcfolder dist/Melodex.app -ov -format UDZO dist/Melodex.dmg
fi
