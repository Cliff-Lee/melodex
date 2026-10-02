#!/usr/bin/env bash
set -euo pipefail

DMG_PATH="${1:-dist/Melodex.dmg}"
IDENTITY="${MELODEX_CODESIGN_IDENTITY:--}"
NOTARY_PROFILE="${MELODEX_NOTARY_PROFILE:-}"
REQUIRE_TRUST="${MELODEX_REQUIRE_DISTRIBUTION_TRUST:-0}"

if [[ ! -f "$DMG_PATH" ]]; then
  echo "DMG not found: $DMG_PATH" >&2
  exit 2
fi

if [[ -n "$IDENTITY" && "$IDENTITY" != "-" ]]; then
  echo "Signing DMG with Developer ID identity: $IDENTITY"
  codesign --force --timestamp --sign "$IDENTITY" "$DMG_PATH"
  codesign --verify --strict --verbose=2 "$DMG_PATH"
elif [[ "$REQUIRE_TRUST" == "1" ]]; then
  echo "Developer ID signing is required but MELODEX_CODESIGN_IDENTITY is not configured." >&2
  exit 3
else
  echo "Developer ID identity not configured; keeping preview DMG unsigned."
fi

if [[ -n "$NOTARY_PROFILE" ]]; then
  echo "Submitting DMG to Apple notarization service."
  xcrun notarytool submit "$DMG_PATH"     --keychain-profile "$NOTARY_PROFILE"     --wait
  xcrun stapler staple "$DMG_PATH"
  xcrun stapler validate "$DMG_PATH"
elif [[ "$REQUIRE_TRUST" == "1" ]]; then
  echo "Notarization is required but MELODEX_NOTARY_PROFILE is not configured." >&2
  exit 4
else
  echo "Notary profile not configured; skipping notarization for preview build."
fi
