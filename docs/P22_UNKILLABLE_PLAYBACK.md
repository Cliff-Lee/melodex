# P22 — Unkillable Playback

**Status: in progress. Current slice: P22b.** P21 shipped Android 16 and Google Play preparation in v0.7.24. P23 remains the follow-up for broader reference-class playback qualification.

## Goal

Keep listening understandable and recoverable when a track, storage device, network source, audio route, or app process fails.

> Slow infrastructure may slow Melodex down; it may never make Melodex feel broken.

The desktop player remains responsible for library scanning and discovery. Android supports local playback and optional Provider Bridge pairing. Native iPhone support remains deferred.

## Scope

P22 covers:

- desktop playback of local files, NAS-mounted libraries, and connected streams;
- Android local playback and optional desktop Bridge streams;
- dual-deck transition failures, decoder and file errors, temporary network loss, sleep/wake, and audio-device changes;
- queue and playback restoration without a full library rescan;
- bounded recovery work that does not block the interface.

P22 does not add a new provider, require an AI service, or begin iPhone development. Google Play publication remains outside this campaign until owner-managed Play signing and Console setup are available.

## Stages

1. **P22a — Isolate playback failures by deck.** Distinguish the active player deck, a speculative incoming deck, and stale inactive-deck errors. A failed incoming track must abort its transition, restore the active deck's volume, preserve the queue position, and explain that current playback continues. Diagnostics stay free of track names, paths, URLs, and credentials.
2. **P22b — Classify and recover source failures.** Retry remote network/resource failures at most twice with increasing delays; do not automatically retry corrupt, unsupported, local resource, permission, or service failures. Run provider refreshes on the bounded background scheduler, discard results after a track or queue change, and preserve the current queue item until the refreshed source reaches a loaded or buffered media state. Keep retry counters and status messages free of track names, paths, URLs, and credentials. *(Current slice.)*
3. **P22c — Protect playback through storage and network stalls.** Measure buffering and read-ahead, add bounded cache or retry behavior where measurements justify it, reconnect after NAS/network recovery, and cancel stale work. Never make a whole-library scan a prerequisite for resuming playback.
4. **P22d — Handle interruptions and output changes.** Qualify sleep/wake, Bluetooth/headphone changes, Android audio focus, and service lifecycle transitions while preserving the user's explicit pause/stop intent.
5. **P22e — Restore sessions safely.** Persist stable queue identities and a useful playback position. Resolve short-lived stream URLs again after restart rather than saving credentials or expired URLs.
6. **P22f — Fault-injection qualification and release.** Exercise corrupt and unsupported files, denied or missing files, temporary NAS/network loss, sleep/wake, output changes, and desktop/service restarts across the supported platforms.

## Success criteria

- A speculative deck failure cannot pause, replace, or advance the active track.
- An unrecoverable item is skipped at most once, with a clear reason available to the listener; transient failures use bounded recovery.
- Queue identity and playback state remain coherent after a recoverable failure, and normal network recovery does not trigger a full rescan.
- Recovery work stays off the UI thread and continues to satisfy the existing responsiveness contract.
- Diagnostics report recovery state without exposing collection content or provider secrets.
- CI fault-injection checks pass on supported desktop platforms. Physical Android checks remain a later owner test and will be recorded separately from CI evidence.
