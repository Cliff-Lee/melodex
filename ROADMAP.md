# Melodex Roadmap

Melodex is in public beta. The roadmap is intentionally short: it describes product direction rather than internal engineering campaigns.

## Now

The current priority is to make the desktop player dependable and pleasant for everyday use.

- reliability with small, large and network-hosted music libraries;
- responsive browsing, search, artwork and lyrics;
- consistent window behaviour across macOS, Windows and Linux;
- visual polish without changing the existing interaction model;
- playback correctness, queue behaviour and clear audio-state feedback;
- packaging and release checks on all supported desktop platforms;
- external beta testing with real collections and awkward metadata.

## Next

Once the desktop beta is stable enough that ordinary testing stops uncovering basic behavioural defects:

- make the Android app useful as a standalone local player while keeping Bridge connectivity optional;
- improve metadata and artwork recovery;
- strengthen playlist import/export and sharing;
- continue improving connected music-source reliability and extension tooling;
- make diagnostics and bug reporting easier for non-developers;
- expand installer/store availability where practical.

## Later

Longer-term possibilities include:

- optional encrypted multi-device state sync;
- iOS support;
- richer Android queue, Flow and taste-memory support;
- scrobbling and presence integrations;
- additional audio-analysis capabilities;
- optional advanced transition/stem-assisted features where hardware permits.

## What is already in place

Melodex already has:

- packaged desktop builds for macOS, Windows and Linux;
- local-library and NAS-oriented indexing;
- Flow listening sessions, rediscovery and taste memory;
- playlists, lyrics, listening history and visualisations;
- optional connected music sources;
- a provider/extension SDK and local control API;
- optional AI control rather than an AI requirement;
- automated responsiveness, large-library, packaging and release qualification.

Detailed implementation history remains available in the closed pull requests and repository documentation. The roadmap deliberately does not duplicate that history.
