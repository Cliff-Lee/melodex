#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "Linux release packages currently target x86_64; found $(uname -m)." >&2
  exit 2
fi

APPIMAGETOOL_VERSION="1.9.1"
APPIMAGETOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
RUNTIME_VERSION="20251108"
RUNTIME_SHA256="2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d"
TOOLS_DIR="${RUNNER_TEMP:-$(mktemp -d)}/melodex-appimage-tools"
mkdir -p "$TOOLS_DIR"

python3 -m venv .venv-build
source .venv-build/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt

rm -rf build dist
pyinstaller --noconfirm --name Melodex \
  --add-data "melodex/assets/melodex-mark.png:melodex/assets" \
  --add-data "melodex/bundled_providers:melodex/bundled_providers" \
  run.py
python check_bundled_provider_payload.py dist/Melodex
python tools/check_qt_bundle.py dist/Melodex
python tools/audit_runtime_bundle.py dist/Melodex \
  --json-out dist/Melodex-linux-runtime-audit.json \
  --markdown-out dist/Melodex-linux-runtime-audit.md
python tools/report_bundle_size.py dist/Melodex \
  --json-out dist/Melodex-linux-bundle-size.json \
  --markdown-out dist/Melodex-linux-bundle-size.md
python linux/check_glibc_abi.py "dist/Melodex"
python frozen_child_smoke.py "dist/Melodex/Melodex"

APPIMAGETOOL="$TOOLS_DIR/appimagetool-x86_64.AppImage"
RUNTIME_FILE="$TOOLS_DIR/runtime-x86_64"
curl --fail --location --retry 3 \
  "https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-x86_64.AppImage" \
  --output "$APPIMAGETOOL"
curl --fail --location --retry 3 \
  "https://github.com/AppImage/type2-runtime/releases/download/${RUNTIME_VERSION}/runtime-x86_64" \
  --output "$RUNTIME_FILE"
printf '%s  %s\n' "$APPIMAGETOOL_SHA256" "$APPIMAGETOOL" | sha256sum --check --status
printf '%s  %s\n' "$RUNTIME_SHA256" "$RUNTIME_FILE" | sha256sum --check --status
chmod +x "$APPIMAGETOOL"

python linux/build_packages.py "$@" \
  --appimagetool "$APPIMAGETOOL" \
  --runtime-file "$RUNTIME_FILE" \
  --output-dir dist

python tools/check_size_regression.py \
  --profile Linux-x86_64 \
  --bundle-report dist/Melodex-linux-bundle-size.json \
  --deb dist/Melodex-linux-x86_64.deb \
  --appimage dist/Melodex-linux-x86_64.AppImage \
  --json-out dist/Melodex-linux-size-regression.json \
  --markdown-out dist/Melodex-linux-size-regression.md
