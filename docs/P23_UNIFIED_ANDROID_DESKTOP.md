# P23 — Unified Android & Desktop Listening

**Status: in progress. Current slice: P23d — explicit playback handoff.**

## Goal

Make Melodex one local-first listening system across desktop, NAS, and Android. Android must work as a useful player on its own and gain an optional desktop companion mode when paired.

## Product contract

- **On this phone:** Android plays its MediaStore library using its own Media3 session, queue, and controls. It remains useful without a desktop connection.
- **Connect a Melodex:** a phone can browse and stream supported desktop sources over the trusted local network. Playback stays on the phone unless the listener explicitly moves the active session to or from the desktop.
- **Multiple phones:** each paired phone has its own player and can request different music from the same desktop. Phone playback does not replace or pause the desktop queue unless the listener explicitly hands off that session.
- **Local first:** pairing uses the desktop QR code and a short-lived code on the same LAN. No external Melodex relay, cloud account, or subscription is required; remote providers may still use their source network.
- **Security:** pairing is explicit, each phone has its own revocable token, and tokens stay encrypted on Android. Queues and checkpoints must use stable identities; never persist expiring stream URLs or credentials.
- Native iPhone support remains deferred. Google Play publication is outside this campaign.

## Released baseline and gaps

v0.7.25 already includes Android local MediaStore playback and queue restoration, a phone-owned playback service, optional QR pairing, per-device Bridge tokens and revocation, and Bridge search/resolve/playback from desktop providers.

At the P23a baseline, Bridge search started one track at a time and Bridge source identities were not restored after an Android process restart. P23b closes that gap in the phone queue. Android CI builds the app; device playback checks remain owner-tested.

## Stages

1. **P23a — Prove independent phone streams.** Add an automated two-device Bridge test: pair two phones, stream different desktop tracks concurrently, prove the desktop queue is unchanged, and verify revoking one phone leaves the other connected.
2. **P23b — Unify the phone queue.** Let local and Bridge tracks share the phone-owned queue with add/remove/reorder and next/previous behavior. Preserve local playback while disconnected; store Bridge items by provider-qualified stable ID and resolve again on resume.
3. **P23c — Make pairing resilient on a home LAN.** Show connection state, retry the saved LAN address while Android is foregrounded, and recover when the desktop restarts. If its address changes, offer QR re-pairing as the clear trust step and keep advanced manual setup as a fallback.
4. **P23d — Add explicit playback handoff.** Let the listener move a selected session between desktop and phone only on request; never take over another phone or alter an unrelated queue.
5. **P23e — Complete the companion experience.** Make desktop library discovery, remote playback, queue state, and connection errors coherent from Android, while retaining full local playback when the Bridge is unavailable.
6. **P23f — Security and release qualification.** Verify device revocation, reconnect behavior, concurrent independent streams, local/Bridge queue restoration, network boundaries, Android builds, and owner device checks.

## P23b acceptance

- Local MediaStore and Bridge tracks share one phone-owned queue with add, remove, reorder, previous, next, and automatic advance.
- Queue identity includes source and provider IDs, so a desktop provider named “local” cannot collide with this phone’s MediaStore item.
- Bridge items persist only source/provider-qualified IDs and safe metadata. Expiring stream URLs and paired credentials are never written into queue storage.
- On resume, a saved Bridge item is resolved again through the paired Bridge. Local items remain available without a Bridge connection.
- Android CI confirms the application builds; process restart, audio focus, Bluetooth, and device playback remain owner checks.

## P23c acceptance

- Android checks the saved Bridge address on startup and retries it every 15 seconds while the app is foregrounded. Each check has a bounded timeout so an offline desktop does not stall the UI or keep a long network request open.
- A desktop restart at the same LAN address recovers automatically. The saved phone queue is retained, and a queued Bridge track can be resolved again after connectivity returns.
- If the saved address no longer works, Android marks the desktop unavailable, explains that it may be offline or have a new address, and keeps a **Scan new QR code** action available while paired.
- A successful QR re-pair saves the new address and token. Revoking the previous phone token is best effort, so an unreachable old address does not block recovery.
- Advanced manual address/token entry remains available as a fallback. Phone-local playback and the phone-owned queue remain usable while the Bridge is unavailable.
- Pairing and recovery stay on the trusted LAN without an external Melodex relay. Native iPhone support remains deferred.
- Android CI validates the build; LAN restart, changed-address QR recovery, Bluetooth/audio focus, and device playback remain owner checks.

## P23d acceptance

- From Android, the listener can request the desktop queue and move its current track, queue position, and playback position to this phone. Android starts the session first; it asks the desktop to stop only if the desktop queue and current index still match the original session.
- A failed phone start leaves desktop playback alone. If the desktop session changes while the phone starts, the guarded stop leaves the new desktop session alone.
- A playing Bridge-only phone queue can be handed to the desktop. Android waits for desktop playback confirmation before pausing and clearing its queue.
- The desktop refuses phone handoff while it is playing or when its paused queue contains a different session. It resolves all incoming Bridge identities before changing the queue.
- Phone-only MediaStore queues are excluded from desktop handoff. The handoff does not control another paired phone.
- Automated tests cover the desktop queue guards and guarded stop. Android CI validates the build; physical playback and LAN handoff remain owner checks. Native iPhone support remains deferred.

## P23a acceptance

- Two paired device tokens can resolve and stream different desktop tracks at the same time.
- The Bridge does not call desktop playback controls to serve a phone stream; the desktop queue remains unchanged.
- Revoking one paired phone invalidates its stream token while another paired phone continues to stream.
- Pairing and desktop-local media streaming do not depend on an external Melodex service.
- Android device playback, Bluetooth/audio-focus, and process-restart checks are recorded as owner tests, separate from CI build evidence.
