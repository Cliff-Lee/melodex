#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:-dist/Melodex.app}"
IDENTITY="${MELODEX_CODESIGN_IDENTITY:--}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "macOS app bundle not found: $APP_PATH" >&2
  exit 2
fi

if ! command -v codesign >/dev/null 2>&1; then
  echo "codesign is required on macOS" >&2
  exit 2
fi

if [[ -z "$IDENTITY" || "$IDENTITY" == "-" ]]; then
  echo "Signing Melodex ad hoc for preview/test build."
  codesign --force --deep --sign - "$APP_PATH"
else
  echo "Signing Melodex with Developer ID identity: $IDENTITY"
  codesign     --force     --deep     --options runtime     --timestamp     --sign "$IDENTITY"     "$APP_PATH"
fi

codesign --verify --deep --strict --verbose=2 "$APP_PATH"
