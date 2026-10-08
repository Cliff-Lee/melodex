# P22 — Unkillable Playback

**Status: in progress. Current slice: P22f.** P21 shipped Android 16 and Google Play preparation in v0.7.24. P23 remains the follow-up for broader reference-class playback qualification.

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
2. **P22b — Classify and recover remote source failures.** Retry remote network/resource failures at most twice with increasing delays; do not automatically retry corrupt, unsupported, permission, or service failures. Run provider refreshes on the bounded background scheduler, discard results after a track or queue change, and preserve the current queue item until the refreshed source reaches a loaded or buffered media state. Keep retry counters and status messages free of track names, paths, URLs, and credentials.
3. **P22c — Protect playback through storage and network stalls.** Record buffer progress, stalled-media events, time without playback-position progress, and loopback gateway request/byte/failure counters without URLs, paths, or credentials. After a local ResourceError, check file reachability on the bounded background scheduler at most three times, then reopen the same local source and restore its position when the path returns. Preserve pause intent, cancel queued probes after a track or queue change, and fence any running stale result. Do not trigger a library scan or add a new playback cache; use the measurements to guide any later cache decision. Never make a whole-library scan a prerequisite for resuming playback.
4. **P22d — Handle interruptions and output changes.** On desktop, rebind both player decks to the current default output when Qt reports an output change and whenever the app returns to the active state, including after common sleep or lock transitions. Reassert explicit play/pause intent without replacing the source, queue item, or position. Keep route counters free of device names. The active-state callback is a recovery hook, not a guaranteed low-level system-suspend notification. Android already delegates audio focus and headset-removal behavior to Media3, with the player hosted in a MediaSessionService so playback is independent of the Activity; Bluetooth/focus and process-lifecycle checks on physical Android devices remain a later owner test.
5. **P22e — Restore sessions safely.** Desktop stores a bounded queue of local paths or stable provider identities and a useful playback position; queue, checkpoint, listening history, and saved moments keep only allowlisted metadata, never stream URLs, request headers, cookies, or expiry data. Restored queues stay paused; playback resolves provider identities again when the listener resumes, and Home Continue seeks to the saved position. Android stores only local MediaStore content URIs with the queue index and position, checkpoints from the playback service every five seconds and when playback pauses or the service stops, then prepares the saved item paused at its previous position.
6. **P22f — Fault-injection qualification and release.** Exercise corrupt and unsupported files, denied or missing files, temporary NAS/network loss, sleep/wake, output changes, and desktop/service restarts across the supported platforms.

## Success criteria

- A speculative deck failure cannot pause, replace, or advance the active track.
- An unrecoverable item is skipped at most once, with a clear reason available to the listener; transient failures use bounded recovery.
- Queue identity and playback state remain coherent after a recoverable failure, and normal network recovery does not trigger a full rescan.
- Recovery work stays off the UI thread and continues to satisfy the existing responsiveness contract.
- Local storage probes are bounded and do not trigger library refreshes.
- Diagnostics report recovery state without exposing collection content or provider secrets.
- An output change or return to the active state uses the current system output and never starts playback after the user paused or stopped.
- CI fault-injection checks pass on supported desktop platforms. Physical Android checks remain a later owner test and will be recorded separately from CI evidence.
