# Melodex plugin and source audit

This document records the product-facing distinction between Melodex Core, sources included with the app, and optional registry plugins.

## Audit summary for v0.7.1

On a clean desktop install:

| Layer | Count | Installed automatically? | Product meaning |
| --- | ---: | --- | --- |
| Core sources | 3 | Yes | Local files, user streams, optional Jamendo connector |
| Included provider packages | 7 | Yes | Search/play sources carried with Melodex |
| Enrichment extensions | 0 | No | Artwork, lyrics, metadata, context and identity extensions are optional |
| Registry entries | 16 | No | All current registry entries are reference/example packages |

The seven included provider packages are repository-tested for package identity, manifest validity, install/restore behaviour and their fixture-backed provider contracts. A separate **per-source live-provider smoke workflow** performs real search → resolve → media-byte checks for provider-related changes, with one CI job per source so a failure identifies the affected integration immediately. The seven bundled providers passed that live verification during the v0.7.1 development cycle. The end-user page still exposes **Check connections** for bounded checks on the current computer/network.

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

The desktop app carries seven audited provider packages and installs them automatically on first run unless the user has explicitly removed/disabled one:

| Included source | Package version | Main role |
| --- | ---: | --- |
| Internet Archive Audio | 0.1.2 | Search/play openly accessible archive audio; lazy metadata resolution keeps search responsive |
| LibriVox | 0.1.4 | Public-domain audiobooks |
| NicheDB Radio | 0.1.2 | Rich daily-refreshed internet-radio discovery |
| Radio Browser | 0.1.2 | Internet radio directory |
| SomaFM | 0.1.1 | Curated internet radio |
| Wikimedia Commons Audio | 0.1.1 | Openly licensed/public-domain audio |
| ccMixter | 0.1.3 | Creative Commons music |

Bundled-package tests verify package identity/version, manifest structure, entrypoints and installation/restore behaviour. The live provider matrix goes further by probing real media bytes for each source independently; Openverse Audio is included in that audit even though it remains an optional registry provider. Use **Sources & plugins → Check connections** for a bounded health check on the current machine/network.

LibriVox 0.1.4 searches the official LibriVox collection hosted by Internet Archive and resolves public-domain audiobook media there. This avoids interactive search pressure on the volunteer-hosted LibriVox API while preserving LibriVox as the content/source identity. Its checked-in source is rebuilt deterministically into the bundled package.

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

## Artwork recovery audit

Artwork recovery remains local-first and deliberately avoids general web-image scraping.

### Album covers

The recovery order is:

1. artwork already supplied with the track, local sidecars, embedded art, or a current trusted cache entry;
2. provider-supplied artwork;
3. exact MusicBrainz release/release-group identity through Cover Art Archive;
4. installed artwork extensions whose cover/thumbnail result clears the confidence floor;
5. a conservative MusicBrainz release-group search using album, artist and year evidence, followed by Cover Art Archive only when the candidate clears the match threshold.

Release-group recovery rejects incompatible **Live** and **Remix** variants unless the user's album metadata indicates that variant. Match method/confidence are stored with new remote cache associations.

### Artist photos

Artist-photo recovery prefers:

1. a user-selected photo;
2. Wikidata's explicit image claim;
3. a free Wikipedia lead image;
4. installed portrait/thumbnail artwork extensions above the confidence floor;
5. a conservative Wikimedia Commons search.

MusicBrainz aliases and sort-name variants are now used as fallback search names, improving coverage for stage names and punctuation variants without lowering the identity threshold.

Legacy remote artwork cache associations created before the stricter matching policy are revalidated instead of being trusted indefinitely. User-selected artist photos remain authoritative.

Downloaded remote artwork must return an actual `image/*` response with non-trivial image content; HTML/error responses are rejected rather than cached as artwork.

### Artwork batch experience

Explicit missing-artwork recovery now runs as a bounded background job rather than one serial lookup at a time.

- up to **4** album or artist lookups are processed concurrently;
- MusicBrainz requests still obey the metadata service's existing rate limiter;
- the progress panel shows `completed / total` plus **Found / No match / Failed** counts;
- **Pause** lets the current in-flight requests finish, then stops launching new work;
- **Resume** continues the remaining queue;
- **Cancel** finishes only the requests already in flight and discards the rest of the current queue;
- **Retry failed** reruns only genuine failed requests, not conservative “no confident match” outcomes;
- changing tabs does not lose the active job or its progress;
- rescanning/replacing the library clears stale batch state;
- successful artwork is applied incrementally as each bounded batch finishes, keeping the interface responsive for large libraries.

The concurrency limit is deliberately small: the goal is to make hundreds or thousands of missing-image checks practical without flooding volunteer/public metadata services.

## Lyrics audit

Core lyrics support is local-first:

1. lyrics explicitly added to Melodex;
2. synchronized or plain sidecars near the audio file;
3. embedded lyrics tags;
4. installed `lyrics` capability extensions.

v0.7.1 also adds an explicit **Find online** action backed by LRCLIB. By default it is user-initiated. Melodex now tries an exact metadata lookup first, then a cleaned exact lookup for common library noise such as remaster/version suffixes and featured-artist text, then a structured LRCLIB search. Search candidates are still accepted conservatively using artist/title similarity plus album and duration evidence when available.

Third-party LRCLIB lyric text is **not persisted to disk**. Successful, instrumental and confident not-found outcomes may be kept in memory for the current Melodex session so replaying the same track does not immediately repeat a network request; **Try again** bypasses that temporary cache. Users can optionally enable **Auto-find online** in the Lyrics tab; that preference is stored locally and only runs when local/plugin lyrics are unavailable. LRCLIB is a third-party community service; lyrics remain the work of their respective rights holders.

Online lookup states are deliberately distinct: **found**, **instrumental**, **no confident match**, **missing artist/title metadata**, and **service/network error**. This prevents a temporary connection problem from looking like a genuine “no lyrics exist” result.

Melodex does not scrape commercial lyric websites.

The current registry's **Public Domain Lyrics Example** is intentionally a small API demonstration corpus. It is not a general modern-song lyrics service and is not preinstalled.

The Now Playing Lyrics tab therefore provides:

- **Add lyrics file…** for `.lrc` / `.txt`;
- **Paste lyrics…** for lyrics the user already has;
- automatic recognition of timestamped LRC text;
- persistent local caching without rewriting the audio file;
- **Manage lyrics sources…** / **Add lyrics source…** to open the Plugin Centre filtered to Lyrics.

A future licensed lyrics extension can plug into the existing `lyrics.lookup` contract without changing the player UI.

### Lyrics experience

The Lyrics tab now treats lyrics as an active listening surface rather than a static text box:

- synchronized LRC lines highlight with playback and can be clicked to seek;
- **Full screen** opens a distraction-free large-type lyrics view that stays synchronized;
- when both local/plugin and online lyrics exist, the user can explicitly switch sources;
- **Edit saved…** is only enabled for local/personal lyrics and saves a Melodex-owned correction copy without rewriting the source audio file;
- temporary LRCLIB/plugin text is not made editable through that action, preserving the non-persistent online-lyrics policy;
- an online miss/error never replaces valid local lyrics already on screen;
- **Translate…** is optional and explicit: it uses the user's configured LLM only after a target language is chosen and the user confirms sending the currently displayed lyric text to that endpoint;
- generated translations are temporary and are not stored by Melodex.


## Status vocabulary

The GUI separates package presence from runtime confidence:

- **Ready** — a recent bounded check/capability call succeeded;
- **Not tested** — installed but not yet exercised in this session;
- **Setup needed** — required configuration is incomplete;
- **Needs attention** — recent runtime/upstream check failed;
- **Disabled** — installed extension is disabled.

This is intentional. Passing repository/fixture tests does not prove that a third-party internet service is currently reachable.
