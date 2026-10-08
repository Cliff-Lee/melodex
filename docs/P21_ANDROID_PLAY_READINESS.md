# P21 — Android 16 and Google Play preparation

**Status: in progress.** P20 shipped Android companion polish in v0.7.23.
iPhone support remains a later project, as requested.

## Goal

Keep Android useful as a standalone local player with optional Provider Bridge
pairing, and prepare a signed Android App Bundle for a Play Console internal
test. This campaign does not publish to Google Play.

Google Play requires new apps and app updates to target Android 16 (API 36) or
higher starting August 31, 2026. The current 0.7.23 build targets API 35, so
that must change before a first Play submission.

## P21 stages

1. **P21a — Target Android 16.** Upgrade the Android Gradle Plugin and Gradle,
   compile against API 36, target API 36, and build the APK and AAB in CI. Review
   the Android 16 target behavior changes against the Compose screen, system
   back behavior, and large-screen layout.
2. **P21b — Prepare upload signing.** Read an owner-managed Play upload key
   from environment variables in Gradle. Release builds accept the key from
   GitHub Actions secrets; no keystore or password is stored in the repository.
   Without all four secrets, CI intentionally produces an unsigned AAB and
   reports that it cannot be uploaded to Play Console.
3. **P21c — Make privacy information accessible.** Keep the Android data
   handling described in docs/PRIVACY.md and add a privacy-policy link in the
   app. Prepare a store data-safety review based on the shipped app and its
   bundled SDKs before making any Play Console declaration.
4. **P21d — Owner-controlled internal testing.** Create or select the
   developer account and app in Play Console, configure Play App Signing,
   provide the upload-key secrets, complete store listing and required forms,
   then upload to an internal test track. Production publication is a separate
   owner decision and is outside this campaign.

## Upload signing setup

When the owner is ready, create a dedicated upload key after setting up Play
App Signing. Store the keystore outside the repository and add these four
repository secrets:

- MELODEX_UPLOAD_KEYSTORE_BASE64 — base64-encoded upload keystore;
- MELODEX_UPLOAD_STORE_PASSWORD;
- MELODEX_UPLOAD_KEY_ALIAS;
- MELODEX_UPLOAD_KEY_PASSWORD.

The Android release workflow uses these secrets only for a version tag or an
explicit workflow dispatch with a release tag. Partial configuration fails
closed. A complete configuration signs and verifies the AAB. No signing
secrets means GitHub release APK builds still work, but the AAB remains
unsigned and is not a Play upload artifact.

## Remaining owner and device checks

- Play Console developer account, app ownership, Play App Signing, listing,
  content rating, and final Data safety answers.
- A publicly reachable store listing and any required screenshots or contact
  details.
- Physical checks on Android 16 for local playback, background playback, QR
  pairing, and privacy link; test layout on a tablet or foldable.
- Confirm that the upload-signed AAB is accepted by an internal Play testing
  track before calling the Android app store-ready.

## Verification

- python scripts/version_check.py matches version 0.7.24 across desktop,
  Windows installer, and Android (versionCode 724).
- Android CI builds assembleDebug and bundleRelease with compile and target
  API 36.
- Repository tests and release/documentation gates pass.
- A release AAB is treated as Play-uploadable only when the workflow verifies
  a signature from the configured upload key.

## Official references

- [Google Play target API requirements](https://support.google.com/googleplay/android-developer/answer/11926878)
- [Sign your app and configure Play App Signing](https://developer.android.com/studio/publish/app-signing)
- [Google Play user-data and privacy policy requirements](https://support.google.com/googleplay/android-developer/answer/10144311)
