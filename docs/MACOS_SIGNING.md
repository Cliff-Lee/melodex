# macOS signing and notarization

Melodex can build and test on macOS without Apple credentials. Those preview
builds are ad-hoc signed and may trigger Gatekeeper's developer-verification
warning.

For public distribution, the release build can use Apple's **Developer ID**
signing and notarization flow:

1. import a Developer ID Application certificate into a temporary CI keychain;
2. sign the final pruned `Melodex.app` with hardened runtime and timestamping;
3. create the DMG;
4. sign the DMG;
5. submit the DMG with `xcrun notarytool`;
6. wait for Apple to accept it;
7. staple the notarization ticket to the DMG;
8. verify the signature, staple and Gatekeeper assessment;
9. publish a machine-readable and human-readable trust report.

## GitHub Actions secrets

Campaign 9A prepares the workflow but does not require these secrets for normal
pull requests. To enable real distribution signing, configure all six repository
secrets:

| Secret | Purpose |
| --- | --- |
| `MACOS_CERTIFICATE_P12_BASE64` | Base64-encoded Developer ID Application certificate exported as `.p12` |
| `MACOS_CERTIFICATE_PASSWORD` | Password used when exporting the `.p12` |
| `MACOS_CODESIGN_IDENTITY` | Full Developer ID Application identity shown by `security find-identity -v -p codesigning` |
| `MACOS_NOTARY_PRIVATE_KEY_BASE64` | Base64-encoded App Store Connect API `.p8` private key |
| `MACOS_NOTARY_KEY_ID` | App Store Connect API key ID |
| `MACOS_NOTARY_ISSUER_ID` | App Store Connect issuer ID |

Do not commit certificate files, API private keys, passwords, or decoded secret
material to the repository.

## Build modes

### Preview / pull request

With no Apple credentials configured:

- the app is ad-hoc signed so the frozen app can be exercised normally;
- notarization is skipped;
- `Melodex-macos-trust.json` and `Melodex-macos-trust.md` clearly report that
  the build is **not distribution-trust ready**;
- CI still validates the internal code signature.

### Developer ID distribution

When all six secrets are configured for a release build:

- CI creates an ephemeral keychain;
- the certificate and notary key are decoded only on the runner;
- Melodex is signed with hardened runtime;
- the DMG is signed, notarized and stapled;
- the trust report verifies the resulting distribution.

Set `MELODEX_REQUIRE_DISTRIBUTION_TRUST=1` when the release pipeline should
fail rather than fall back to a preview build. Campaign 9B will turn that into a
release requirement after the Apple Developer credentials are live.

## Local verification

For a built app and DMG:

```bash
cd desktop
python tools/report_macos_trust.py dist/Melodex.app \
  --dmg dist/Melodex.dmg \
  --json-out dist/Melodex-macos-trust.json \
  --markdown-out dist/Melodex-macos-trust.md
```

For a distribution build that must be trusted:

```bash
python tools/report_macos_trust.py dist/Melodex.app \
  --dmg dist/Melodex.dmg \
  --require-distribution-trust
```

## Campaign 9A boundary

9A is infrastructure readiness. It does **not** claim current public builds are
notarized, and it deliberately does not make Apple credentials mandatory.

9B is the activation step: add the real Apple Developer credentials, run a
signed/notarized release candidate, verify it on a clean Mac, then require
distribution trust for release builds.
