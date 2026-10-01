# Melodex plugin and source audit

This document records the product-facing distinction between Melodex Core, sources included with the app, and optional registry plugins.

## Audit summary for v0.7.1

On a clean desktop install:

| Layer | Count | Installed automatically? | Product meaning |
| --- | ---: | --- | --- |
| Core sources | 3 | Yes | Local files, user streams, optional Jamendo connector |
| Included provider packages | 6 | Yes | Search/play sources carried with Melodex |
| Enrichment extensions | 0 | No | Artwork, lyrics, metadata, context and identity extensions are optional |
| Registry entries | 16 | No | All current registry entries are reference/example packages |

The six included provider packages are repository-tested for package identity, manifest validity, install/restore behaviour and their fixture-backed provider contracts. **That is not the same as a live upstream-service guarantee.** The end-user page therefore exposes **Check connections** to perform bounded runtime checks on the current computer/network.

The registry is currently a developer/reference ecosystem rather than a curated consumer app store: all 16 entries are marked `example`. The redesigned UI calls them optional/reference features rather than implying that every registry item is production-ready.

## What is available on a fresh install

### Built into Melodex Core

| Feature | Role | Default state |
| --- | --- | --- |
| This computer | Local music library | Built in |
| My streams | User-supplied radio/audio URLs | Built in |
| Jamendo reference source | Optional Jamendo catalogue connection | Built in, setup required |

These are Core integrations rather than separately installed plugin packages.

### Included with Melodex

The desktop app carries six audited provider packages and installs them automatically on first run unless the user has explicitly removed/disabled one:

| Included source | Package version | Main role |
| --- | ---: | --- |
| Internet Archive Audio | 0.1.0 | Search/play openly accessible archive audio |
| LibriVox | 0.1.4 | Public-domain audiobooks |
| Radio Browser | 0.1.2 | Internet radio directory |
| SomaFM | 0.1.1 | Curated internet radio |
| Wikimedia Commons Audio | 0.1.1 | Openly licensed/public-domain audio |
| ccMixter | 0.1.3 | Creative Commons music |

Bundled-package tests verify package identity/version, manifest structure, entrypoints and installation/restore behaviour. Live upstream availability is deliberately **not** inferred from fixture tests: use **Sources & plugins → Check installed** for a bounded health check on the current machine/network.

## Live bundled-provider verification — October 1, 2026

A manual network smoke test loaded the same six `.mdxprovider` packages carried by the desktop app. For each provider it performed a real search, resolved a returned item, then fetched the first 4096 bytes from the resolved media URL. Two consecutive clean runs passed all six providers:

| Included source | Live result | Media probe |
| --- | --- | --- |
| Internet Archive Audio 0.1.0 | Pass | HTTP 206, audio/mpeg |
| LibriVox 0.1.4 | Pass | HTTP 206, audio/mpeg |
| Radio Browser 0.1.2 | Pass | HTTP 200, audio/mpeg |
| SomaFM 0.1.1 | Pass | HTTP 206, audio/aac |
| Wikimedia Commons Audio 0.1.1 | Pass | HTTP 206, application/ogg |
| ccMixter 0.1.3 | Pass | HTTP 206, audio/mpeg |

This is a dated verification snapshot, not a guarantee that third-party services will always be reachable.

The audit also found that the previous LibriVox 0.1.2 package could exceed Melodex's provider RPC deadline while waiting on the official LibriVox API. LibriVox 0.1.4 now searches the Internet Archive `librivoxaudio` collection and resolves hosted MP3 files there. The checked-in provider source and bundled archive are regression-tested to match.

### Optional registry plugins

Registry entries are not automatically installed. The current registry is primarily a reference ecosystem demonstrating provider and extension contracts.

Examples include:

- MusicBrainz identity/metadata enrichment
- Wikimedia and Cover Art Archive artwork extensions
- ListenBrainz metadata/context extensions
- MusicBrainz song connections
- Wikimedia liner notes
- Openverse Audio
- Last.fm recommendations
- Sonic Neighbours
- Forgotten Favourites
- Bridge Builder
- Musical Detours
- Public Domain Lyrics Example

Entries marked **Reference** in the Plugin Centre are inspectable examples, not promises of production-grade upstream availability.

## Duplicate/reference capabilities

Some registry examples deliberately overlap with Core/bundled functionality:

- Radio Browser and LibriVox are already included sources.
- MusicBrainz identity/metadata is already part of Core enrichment.
- Cover Art Archive is already used by Core artwork enrichment.
- Wikimedia is already used by Core artist/artwork enrichment.

The Plugin Centre calls out these overlaps so a normal user does not install duplicates just because they appear in the catalogue.

## Lyrics audit

Core lyrics support is local-first:

1. lyrics explicitly added to Melodex;
2. synchronized or plain sidecars near the audio file;
3. embedded lyrics tags;
4. installed `lyrics` capability extensions.

v0.7.1 also adds an explicit **Find online** action backed by LRCLIB. By default it is user-initiated: Melodex sends the current track metadata to LRCLIB, displays a conservative match, and does not permanently cache LRCLIB lyric text. Users can optionally enable **Auto-find online** in the Lyrics tab; that preference is stored locally and only runs when local/plugin lyrics are unavailable. LRCLIB is a third-party community service; lyrics remain the work of their respective rights holders.

Melodex does not scrape commercial lyric websites.

The current registry's **Public Domain Lyrics Example** is intentionally a small API demonstration corpus. It is not a general modern-song lyrics service and is not preinstalled.

The Now Playing Lyrics tab therefore provides:

- **Add lyrics file…** for `.lrc` / `.txt`;
- **Paste lyrics…** for lyrics the user already has;
- automatic recognition of timestamped LRC text;
- persistent local caching without rewriting the audio file;
- **Find lyrics plugin…** to open the Plugin Centre filtered to Lyrics.

A future licensed lyrics extension can plug into the existing `lyrics.lookup` contract without changing the player UI.

## Status vocabulary

The GUI separates package presence from runtime confidence:

- **Ready** — a recent bounded check/capability call succeeded;
- **Not tested** — installed but not yet exercised in this session;
- **Setup needed** — required configuration is incomplete;
- **Needs attention** — recent runtime/upstream check failed;
- **Disabled** — installed extension is disabled.

This is intentional. Passing repository/fixture tests does not prove that a third-party internet service is currently reachable.
