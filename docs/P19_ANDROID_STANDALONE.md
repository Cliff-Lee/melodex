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

P19a playback was owned by `MainActivity`. P19b moves it into
`PlaybackService`, so the player can continue after the activity closes.

## P19a verification

The v0.7.21 APK passed the GitHub Android build. On-device checks remain useful
for permission grant/denial, empty and populated libraries, and direct track
playback on Android 12-or-older and Android 13-or-newer devices.

## P19b progress

The playback service owns ExoPlayer and a MediaSession. Android system media
controls, the playback notification, lock-screen actions, and headset/Bluetooth
play-pause actions use that session. ExoPlayer handles audio focus and pauses
when the audio output becomes noisy, such as when headphones are unplugged.
Track title, artist, and album metadata are included in the session item.

Playback is now independent of the Activity lifecycle. P19b still used one
current item; local search, sorting, artwork, metadata cleanup, and a persistent
queue are the focus of P19c. QR pairing and Flow/taste remain later work.

## P19b verification

GitHub Actions builds both `assembleDebug` and `bundleRelease`. On a device,
check that playback continues after leaving the app and locking the screen;
test notification/lock-screen and headset controls, audio interruptions, and
the optional Bridge path. P19f will add the broader supported-device and
accessibility matrix.

## P19c progress

The local library first loads a small MediaStore preview so tracks can be played
while the complete list loads in the background. Once loaded, listeners can
search title, artist, or album and sort by any of those fields. Missing metadata
gets clear fallbacks, duration is shown when available, and rows request album
thumbnails without blocking playback.

The local queue supports adding, removing, and clearing tracks. It is saved
across app restarts, including the current track position, and the playback
service updates that position when Android notification, lock-screen, or
headset controls skip tracks. Bridge stream URLs are not persisted because
they may expire.

## P19c verification

GitHub Actions must build the debug APK and release bundle and pass the
repository test/package gates. On a device, check that the first preview track
can play before the full list finishes, search and sorting work with missing
metadata, album art appears when available, empty/error states are understandable,
and the queue survives an app restart and system media-control skips.

## Completion gates

P19 is complete when a new Android user can play music on the phone without a
computer or technical setup, ordinary playback survives app backgrounding,
Bridge remains an understandable optional source, and the Android package is
qualified on supported devices without executing downloaded provider code.
