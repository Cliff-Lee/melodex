# P19 — Android Standalone Player

## Purpose

P19 makes Android useful without another computer. A first-time listener should
be able to open Melodex, choose music stored on the phone, allow audio access,
and play a track. Provider Bridge remains an optional way to reach sources
configured on another Melodex installation.

Android must not run downloaded provider code. Local playback uses Android's
media library and content URIs; Bridge requests use the existing authenticated
API. The phone path must not require a computer, developer setup, or an API key.

## Campaign stages

1. **P19a — Make phone music playable.** Add a clear local-first entry point,
   request the platform audio permission only when needed, list audio items
   indexed by Android, and start playback from their content URIs. Preserve the
   optional Bridge path.
2. **P19b — Make playback dependable in daily use.** Move playback into a
   MediaSession service with audio focus, notification and lock-screen controls,
   headset/Bluetooth actions, and playback that continues when the screen closes.
3. **P19c — Build a usable local library.** Add sorting and search, useful
   empty/error states, album artwork, metadata handling, and a persistent queue
   without requiring a full scan before first playback.
4. **P19d — Simplify optional Bridge setup.** Add safe connection persistence
   and QR or discovery pairing while keeping credentials protected and Bridge
   connectivity optional.
5. **P19e — Bring Melodex listening tools to Android.** Add queue steering,
   Flow and taste controls in small steps that reuse clear local product
   concepts without executing desktop or downloaded provider code.
6. **P19f — Qualify the app.** Test permission grant/denial, empty and populated
   phone libraries, playback interruption and restart, Bridge search/playback,
   supported Android versions, accessibility, and installable APK delivery.

Each stage needs focused verification before the next one begins.

## P19a progress

The first screen now opens on **On this phone**, with **Connect a Melodex** as
the optional second path. Melodex requests `READ_MEDIA_AUDIO` on Android 13 and
newer, and `READ_EXTERNAL_STORAGE` on older supported versions, only after the
listener chooses **Allow music access**.

The local library reads Android's indexed audio collections across attached
external volumes, displays title/artist/album, and plays the selected
`content://` URI directly. It does not scan filesystem paths, copy files, or
send local audio to the Bridge. A refresh action lets the listener query again
after adding music. **Play something** starts a randomly selected track from
the loaded phone library. Bridge URL and token fields remain available from
the second path and are blank on first launch.

Playback is still owned by `MainActivity` in this stage. Background service,
media notification, headset controls, persistent queue, local search, and
pairing are later P19 stages; this slice does not claim them.

## P19a verification

The local environment has Java 17, but no Gradle executable, wrapper, or
Android SDK. GitHub Actions builds `assembleDebug` and `bundleRelease`; this
release is being published so the flow can be checked on real devices. Test at
least one Android 12-or-older device and one Android 13-or-newer device,
including permission grant and denial, empty and populated libraries, and
direct track playback. P19f will add broader interruption, accessibility, and
Bridge qualification.

## Completion gates

P19 is complete when a new Android user can play music on the phone without a
computer or technical setup, ordinary playback survives app backgrounding,
Bridge remains an understandable optional source, and the Android package is
qualified on supported devices without executing downloaded provider code.
