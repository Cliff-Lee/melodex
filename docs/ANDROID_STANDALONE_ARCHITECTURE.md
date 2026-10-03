# Android Standalone Architecture

Status: design contract for Campaign A13a  
Scope: architecture only; no production behaviour changes

## 1. Goal

Turn Melodex Android from a Provider Bridge preview into a useful standalone music player while preserving Bridge mode as an optional way to extend the phone with desktop, NAS, and remote-provider capabilities.

The product rule is:

> Android must be useful with no other Melodex instance running. Connecting another Melodex should add capabilities, not unlock the app.

This document deliberately defines contracts rather than importing desktop implementation details. The desktop codebase is being refactored, so Android should depend on stable concepts and protocol shapes instead of GUI classes or Python-only services.

## 2. Current baseline

The Android app is currently a very small Bridge client:

- one Compose activity owns UI, Bridge networking, and playback wiring;
- the app asks the user for a Bridge URL and bearer token;
- search calls `/v1/search`;
- playback resolves a result through `/v1/resolve` and hands the returned URL to ExoPlayer;
- Android has no local library database;
- Android does not query MediaStore;
- Android has no MediaSession/background playback service;
- Android has no persistent queue, playlists, favourites, recent history, or offline cache;
- Android does not run `.mdxprovider` packages.

This small baseline is an advantage: there is little Android architecture to preserve.

## 3. Architectural principles

### 3.1 Native where the platform already has the right primitive

Android should use Android APIs directly for:

- local media discovery: MediaStore;
- playback: AndroidX Media3;
- background playback and controls: MediaSessionService;
- persistence: Room;
- permissions and lifecycle: Android platform APIs;
- LAN discovery/pairing: Android networking APIs.

Do not recreate desktop filesystem scanning or desktop audio-player behaviour on Android.

### 3.2 Share contracts, not implementations

Desktop and Android should converge on the same concepts:

- track identity;
- source identity;
- source capabilities;
- search/browse semantics;
- queue entries;
- playable resolution;
- availability state;
- artwork/metadata references.

They do not need to share the same language, database, scanner, or playback engine.

### 3.3 Bridge is a source, not an app mode

The UI must not force the user to choose "standalone mode" versus "Bridge mode".

A connected Melodex host is another source beside the phone's own library.

Conceptually:

```text
Melodex Android
├── This phone
├── Connected Melodex: Desktop
├── Connected Melodex: NAS
└── Android-native online sources (later)
```

### 3.4 No dependency on desktop GUI ownership

No Android contract may require importing, mimicking, or exposing `MainWindow` or another desktop UI object.

If a capability can only be accessed through a desktop GUI callback, that is a desktop architectural concern to isolate behind a service/protocol boundary.

### 3.5 Offline-first local playback

Phone-local tracks must remain searchable and playable:

- with no network;
- with no Bridge;
- after the Android process is killed and recreated.

## 4. Target layers

The Android app should be split into these layers.

```text
UI / Compose
    ↓
Application state / ViewModels
    ↓
Unified music domain
    ├── LibrarySource
    ├── SearchSource
    ├── PlaybackResolver
    ├── QueueRepository
    └── PlaylistRepository
    ↓
Adapters
    ├── Local MediaStore source
    ├── Bridge source
    └── Android-native provider source (future)
    ↓
Platform services
    ├── Room
    ├── Media3 / MediaSessionService
    ├── MediaStore
    └── Network / discovery
```

The UI must not call MediaStore, HTTP, Room, or ExoPlayer directly.

## 5. Core domain contracts

Names below describe responsibilities, not mandatory Kotlin signatures.

### 5.1 MusicItem

A common immutable track representation:

```text
MusicItem
- itemId
- sourceId
- sourceItemId
- title
- artist
- album
- durationMs?
- artworkRef?
- mimeType?
- availability
- metadata
```

`itemId` must be stable enough for queue/history persistence.

For local Android media, a practical identity is derived from the MediaStore volume + media ID, with enough fallback metadata to survive reasonable rescans.

For Bridge/provider items, identity is source host + provider ID + provider track ID.

Do not assume a path is identity.

### 5.2 SourceDescriptor

```text
SourceDescriptor
- sourceId
- displayName
- kind
- capabilities
- availability
```

Kinds initially:

- `local_android`
- `melodex_bridge`

Future kinds may include Android-native online providers.

### 5.3 SourceCapabilities

Capabilities should be explicit rather than inferred from class type.

Initial flags:

- search
- browse
- resolve
- localPlayback
- remotePlayback
- artwork
- recommendations
- downloadable
- liveStream

This mirrors the direction already present in the provider ecosystem and allows the UI to adapt without special-casing every source.

### 5.4 LibrarySource

Responsibilities:

- expose library/browse collections;
- emit stable `MusicItem` values;
- expose source availability;
- refresh incrementally.

The local implementation is backed by MediaStore + Room cache.

A Bridge implementation maps Bridge responses into the same domain objects.

### 5.5 SearchSource

```text
search(query, limit) -> results
```

Unified search fans out across enabled sources and merges results without hiding their origin.

Search should preserve source labels so users understand whether a result is on the phone, on another Melodex, or online.

### 5.6 PlaybackResolver

Input: `MusicItem`

Output: a short-lived playable descriptor:

```text
Playable
- uri
- headers?
- mimeType?
- sourceItem
- expiresAt?
```

Examples:

- Android-local item -> content URI;
- Bridge local-file item -> authenticated Bridge media URL;
- Bridge online-provider item -> Bridge resolved stream URL.

The queue stores `MusicItem`, not ephemeral stream URLs.

### 5.7 QueueRepository

The queue is an application-level concept independent of the playback engine.

Required operations:

- replace queue;
- append;
- insert next;
- remove/reorder;
- move to item;
- restore last queue;
- expose current index;
- mark unavailable entries without deleting them.

Media3 consumes the queue; it does not own its durable identity.

### 5.8 PlaylistRepository

Playlists must be source-agnostic.

A playlist entry references a `MusicItem` identity, not a local filesystem path.

That permits a future playlist to mix:

- phone-local tracks;
- NAS/desktop tracks through Bridge;
- Android-native providers.

Unavailable remote entries remain visible and explain why they cannot currently play.

## 6. Local Android library

### 6.1 MediaStore is authoritative for discovery

Do not port the desktop scanner.

Android should query MediaStore for audio and capture at minimum:

- media ID;
- volume;
- title;
- artist;
- album;
- album ID;
- duration;
- MIME type;
- date modified where available;
- content URI.

Use scoped-storage-compatible APIs.

### 6.2 Room is the app cache/state store

Room should hold Melodex-specific state that MediaStore does not:

- stable Melodex item keys;
- favourites/loves;
- play counts/history;
- playlist membership;
- cached artwork metadata;
- source state;
- last-seen MediaStore revision data;
- queue state.

Do not duplicate full media files.

### 6.3 Incremental refresh

A library refresh should compare MediaStore change signals/IDs and update changed records in batches.

It must never require loading every media record into the Compose UI at once.

### 6.4 Library scale target

Design for at least 100k indexed tracks without UI-thread work proportional to total library size.

The first implementation should include synthetic/instrumented tests at:

- 1k;
- 10k;
- 50k;
- 100k tracks.

## 7. Playback architecture

Use Media3 with a `MediaSessionService`.

Required outcomes:

- playback continues with screen off;
- lock-screen controls;
- Bluetooth/headset transport controls;
- audio focus handling;
- interruption/call handling;
- notification controls;
- process/lifecycle recovery where Android permits;
- seek, repeat, shuffle;
- queue persistence.

The current activity-owned ExoPlayer must be treated as preview code, not expanded into the final architecture.

Compose observes playback state through a controller/ViewModel boundary.

## 8. Bridge integration

### 8.1 Preserve existing protocol compatibility initially

The existing Bridge already provides useful primitives:

- `/health`;
- `/v1/search`;
- `/v1/browse`;
- `/v1/resolve`;
- `/v1/media`;
- provider capability listing;
- queue/control endpoints.

A13 implementation should adapt these into the Android domain model rather than embedding HTTP calls in screens.

### 8.2 Bridge identity

A Bridge host needs a persistent client-side identity distinct from its IP address.

Store:

- friendly name;
- host identity/fingerprint once a protocol provides one;
- last-known LAN endpoint;
- auth credentials in Android secure storage;
- capability snapshot;
- last connected time.

Do not use `192.168.x.x:8766` as durable identity.

### 8.3 Pairing direction

Manual URL + bearer token remains a developer fallback.

Product flow should become:

1. desktop advertises a Melodex service on the LAN;
2. Android discovers it;
3. user taps the host;
4. desktop displays/approves a short pairing challenge or QR;
5. Android receives a scoped credential;
6. reconnects automatically on trusted LANs.

Do not expose raw bearer tokens in the normal UI.

### 8.4 Security

The present Bridge is documented for trusted LAN use and can use cleartext HTTP.

Standalone work must not silently turn that into an internet-facing remote-access design.

Remote access is a separate security project.

## 9. Provider strategy

Do not try to execute desktop Python provider packages on Android in the first standalone release.

Classify capabilities as:

### Native Android

Simple providers can later gain Android-native adapters when their protocol/licensing makes sense.

### Bridge-backed

Python-heavy providers and desktop plugins continue to run on another Melodex and are exposed through Bridge.

### Unsupported on Android

The UI should explicitly state that a capability requires another Melodex rather than failing mysteriously.

The provider manifest/protocol can later gain platform capability declarations, but A13a does not require changing the provider SDK.

## 10. UX contract

A fresh install with no pairing should open into a useful local-player experience.

Normal first-run path:

1. explain local music access;
2. request the minimum Android permission required;
3. index the phone's music;
4. show Library/Home;
5. allow immediate playback.

Connecting another Melodex is secondary:

```text
Sources
  This phone                 Available
  Cliff's Desktop            Nearby
  Home NAS                   Offline
  + Connect another Melodex
```

No screen should require a user to understand the term "Provider Bridge" to play music.

## 11. Compatibility with desktop refactoring

Android should consume stable boundaries only.

The ongoing desktop codebase campaign may freely reorganise:

- MainWindow;
- library scanning internals;
- provider manager internals;
- playback implementation;
- queue/UI orchestration.

A13 should remain unaffected provided these externally visible concepts stay coherent:

- track/source identity;
- provider capabilities;
- Bridge protocol;
- queue semantics;
- resolve-to-playable semantics.

A useful refactor test for desktop is:

> Can this capability be exposed to Android/Bridge without importing or driving the desktop UI?

If not, the capability probably still belongs behind a service boundary.

## 12. Explicit non-goals for the first standalone milestone

Do not block standalone Android on:

- full feature parity with desktop;
- running arbitrary Python providers on-device;
- Humanize;
- Journeys;
- social rooms;
- remote internet access to a home Melodex;
- offline downloading of Bridge media;
- cross-device state sync;
- advanced DSP/Lab features.

Those become follow-on campaigns once local library + local playback are solid.

## 13. Proposed implementation sequence

### A13b — Local library foundation

- split the one-file preview into domain/data/UI packages;
- add Room;
- add MediaStore adapter;
- permission flow;
- incremental refresh;
- local library browsing/search;
- no Bridge regression.

Exit criterion: install Android Melodex on a phone with music and browse/search the local collection with the desktop powered off.

### A13c — Standalone playback

- MediaSessionService;
- MediaController boundary;
- queue repository;
- background playback;
- notification/lock-screen/Bluetooth controls;
- persistence and restart behaviour.

Exit criterion: play a phone-local album for an extended period with the app backgrounded and control it from the system UI/headset.

### A13d — Unified sources UX

- local + Bridge adapters behind the common contracts;
- source-labelled unified search;
- local-first home/library UI;
- no manual architecture modes.

Exit criterion: local and connected results coexist in one UX and disconnecting the Bridge does not degrade local playback.

### A13e — Pairing/discovery

- LAN discovery;
- friendly device identity;
- QR/short-code approval;
- secure credential storage;
- automatic reconnect.

Exit criterion: a normal user connects Android to desktop without typing an IP address or bearer token.

## 14. Required architecture tests

Before expanding features, add tests around contracts rather than UI snapshots alone.

Minimum areas:

- MediaStore rows -> stable `MusicItem`;
- local item -> content URI resolution;
- Bridge JSON -> `MusicItem`;
- mixed-source search merge;
- queue persistence;
- unavailable remote entries;
- process recreation;
- Bridge disconnect while local item plays;
- Bridge disconnect while remote item plays;
- 100k-item data-layer pagination/performance;
- permission denied/revoked;
- media removed between indexing and playback.

## 15. Decision record

A13a makes these decisions:

1. Android becomes standalone.
2. Bridge remains and becomes an optional source.
3. Android local discovery uses MediaStore, not the desktop scanner.
4. Android playback uses Media3/MediaSessionService, not desktop playback code.
5. Room stores Melodex state; it does not duplicate music files.
6. Common domain contracts unify local and remote sources.
7. Queue and playlists store durable source/item identities, not stream URLs.
8. Desktop Python providers are not ported wholesale to Android.
9. Android must not depend on desktop GUI classes.
10. Manual Bridge URL/token entry is a fallback, not the intended user experience.

## 16. A13a exit criteria

A13a is complete when:

- this architecture contract is reviewed;
- no production Android behaviour was changed;
- the next implementation campaign can work in Android-owned code without colliding with current desktop refactors;
- A13b has clear interfaces and measurable exit criteria.
