#!/usr/bin/env bash
set -euo pipefail

CERT_B64="${MACOS_CERTIFICATE_P12_BASE64:-}"
CERT_PASSWORD="${MACOS_CERTIFICATE_PASSWORD:-}"
IDENTITY="${MACOS_CODESIGN_IDENTITY:-}"
NOTARY_KEY_B64="${MACOS_NOTARY_PRIVATE_KEY_BASE64:-}"
NOTARY_KEY_ID="${MACOS_NOTARY_KEY_ID:-}"
NOTARY_ISSUER_ID="${MACOS_NOTARY_ISSUER_ID:-}"

values=(
  "$CERT_B64"
  "$CERT_PASSWORD"
  "$IDENTITY"
  "$NOTARY_KEY_B64"
  "$NOTARY_KEY_ID"
  "$NOTARY_ISSUER_ID"
)
configured=0
for value in "${values[@]}"; do
  if [[ -n "$value" ]]; then
    configured=$((configured + 1))
  fi
done

if [[ "$configured" -eq 0 ]]; then
  echo "Apple distribution credentials are not configured; preview signing will be used."
  exit 0
fi

if [[ "$configured" -ne "${#values[@]}" ]]; then
  echo "Apple distribution credentials are partially configured. Provide all six required secrets." >&2
  exit 2
fi

: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"

KEYCHAIN="$RUNNER_TEMP/melodex-signing.keychain-db"
CERT_FILE="$RUNNER_TEMP/melodex-signing.p12"
NOTARY_KEY_FILE="$RUNNER_TEMP/AuthKey_$NOTARY_KEY_ID.p8"
KEYCHAIN_PASSWORD="$(openssl rand -hex 24)"

decode_base64() {
  python3 -c 'import base64,sys; sys.stdout.buffer.write(base64.b64decode(sys.stdin.buffer.read()))'
}

printf '%s' "$CERT_B64" | decode_base64 > "$CERT_FILE"
printf '%s' "$NOTARY_KEY_B64" | decode_base64 > "$NOTARY_KEY_FILE"

security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security set-keychain-settings -lut 21600 "$KEYCHAIN"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security import "$CERT_FILE"   -k "$KEYCHAIN"   -P "$CERT_PASSWORD"   -T /usr/bin/codesign   -T /usr/bin/security
security set-key-partition-list   -S apple-tool:,apple:,codesign:   -s   -k "$KEYCHAIN_PASSWORD"   "$KEYCHAIN"
security list-keychains -d user -s "$KEYCHAIN" login.keychain-db

NOTARY_PROFILE="melodex-notary"
xcrun notarytool store-credentials "$NOTARY_PROFILE"   --key "$NOTARY_KEY_FILE"   --key-id "$NOTARY_KEY_ID"   --issuer "$NOTARY_ISSUER_ID"

rm -f "$CERT_FILE" "$NOTARY_KEY_FILE"

{
  echo "MELODEX_CODESIGN_IDENTITY=$IDENTITY"
  echo "MELODEX_NOTARY_PROFILE=$NOTARY_PROFILE"
} >> "$GITHUB_ENV"

echo "Apple Developer ID signing and notarization credentials are ready."
